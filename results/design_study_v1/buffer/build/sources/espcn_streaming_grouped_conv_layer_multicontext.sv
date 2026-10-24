`timescale 1ns/1ps

import espcn_fpga_student_weights_pkg::*;

// Two-context streaming grouped trained 3x3 convolution layer.
//
// The original grouped layer accepts one pixel, issues every output group, and
// then leaves its MAC lanes idle while delayed results retire. This candidate
// stores two pixel contexts and tags every in-flight output group with its
// owner. Once all channels for one pixel have been issued, the same MAC lanes
// can begin the next pixel while the prior result is still in the pipeline.
// Results remain visible in original raster order, and masked pixels still
// produce an aligned all-zero feature token without issuing neural MAC work.
module espcn_streaming_grouped_conv_layer_multicontext #(
    parameter integer LAYER_INDEX = 1,
    parameter integer INPUT_CHANNELS = 16,
    parameter integer OUTPUT_CHANNELS = 16,
    parameter integer OUTPUT_LANES = 4,
    parameter integer APPLY_RELU = 1,
    parameter integer RIGHT_SHIFT_BITS = TRAINED_DEFAULT_RIGHT_SHIFT_BITS,
    parameter integer DSP_MULTIPLIER_LANES = 9,
    parameter integer USE_SYNC_WEIGHT_ROM = 0,
    parameter integer COLUMN_BITS = 10,
    parameter integer ROW_BITS = 10,
    parameter integer OUTPUT_GROUPS =
        (OUTPUT_CHANNELS + OUTPUT_LANES - 1) / OUTPUT_LANES,
    parameter integer GROUP_BITS =
        (OUTPUT_GROUPS <= 1) ? 1 : $clog2(OUTPUT_GROUPS),
    parameter integer CHANNEL_BITS =
        (INPUT_CHANNELS <= 1) ? 1 : $clog2(INPUT_CHANNELS),
    parameter integer TAG_FIFO_DEPTH = OUTPUT_GROUPS * 2 + 8,
    parameter integer TAG_FIFO_BITS =
        (TAG_FIFO_DEPTH <= 1) ? 1 : $clog2(TAG_FIFO_DEPTH),
    parameter integer TAG_COUNT_BITS =
        (TAG_FIFO_DEPTH + 1 <= 1) ? 1 : $clog2(TAG_FIFO_DEPTH + 1)
) (
    input  logic                                      clk,
    input  logic                                      reset_n,

    input  logic                                      weight_initialization_complete,
    input  logic                                      weight_initialization_write_enable,
    input  logic [7:0]                                weight_initialization_address,
    input  logic signed [71:0]                        weight_initialization_row,

    input  logic                                      window_valid,
    output logic                                      window_ready,
    input  logic                                      window_compute_enable,
    input  logic signed [INPUT_CHANNELS*72-1:0]       feature_windows,
    input  logic [ROW_BITS-1:0]                       window_row,
    input  logic [COLUMN_BITS-1:0]                    window_column,
    input  logic                                      window_last,

    output logic                                      feature_valid,
    input  logic                                      feature_ready,
    output logic signed [OUTPUT_CHANNELS*8-1:0]       feature_values,
    output logic [ROW_BITS-1:0]                       feature_row,
    output logic [COLUMN_BITS-1:0]                    feature_column,
    output logic                                      feature_last,
    output logic                                      protocol_error
);
    typedef enum logic [1:0] {
        ISSUE_IDLE,
        ISSUE_PREFETCH,
        ISSUE_CHANNELS
    } issue_state_t;

    issue_state_t issue_state;

    // Two circular slots decouple acceptance, MAC issue, result retirement,
    // and ordered output without duplicating any multiplier lane.
    logic [1:0] context_occupied;
    logic [1:0] context_issue_complete;
    logic [1:0] context_result_complete;
    logic [1:0] context_count;
    logic input_tail;
    logic output_head;
    logic issue_slot;
    logic signed [INPUT_CHANNELS*72-1:0] context_windows [0:1];
    logic signed [OUTPUT_CHANNELS*8-1:0] context_values [0:1];
    logic [ROW_BITS-1:0] context_row [0:1];
    logic [COLUMN_BITS-1:0] context_column [0:1];
    logic context_last [0:1];

    logic accept_window;
    logic retire_output;
    logic [GROUP_BITS-1:0] issue_group;
    logic [CHANNEL_BITS-1:0] issue_channel;
    logic signed [7:0] issue_sample_window [0:8];
    logic lane_input_valid;
    logic lane_first_channel;
    logic lane_last_channel;

    // Every final input channel pushes the context/group identity that will
    // emerge from the fixed-latency MAC pipeline several cycles later.
    logic tag_context_fifo [0:TAG_FIFO_DEPTH-1];
    logic [GROUP_BITS-1:0] tag_group_fifo [0:TAG_FIFO_DEPTH-1];
    logic [TAG_FIFO_BITS-1:0] tag_head;
    logic [TAG_FIFO_BITS-1:0] tag_tail;
    logic [TAG_COUNT_BITS-1:0] tag_count;
    logic tag_fifo_full;
    logic tag_fifo_empty;
    logic tag_fifo_push;
    logic tag_fifo_pop;
    logic retired_context;
    logic [GROUP_BITS-1:0] retired_group;

    logic lane_output_valid [0:OUTPUT_LANES-1];
    logic signed [31:0] lane_output_accumulator [0:OUTPUT_LANES-1];
    logic signed [7:0] lane_output_value [0:OUTPUT_LANES-1];
    logic lane_protocol_error [0:OUTPUT_LANES-1];
    logic weight_rom_initialized [0:OUTPUT_LANES-1];
    logic all_lanes_output_valid;
    logic all_weight_roms_initialized;
    logic any_lane_protocol_error;

    genvar output_lane;
    genvar kernel_lane;
    integer sample_lane;
    integer reduce_lane;
    integer pack_channel;
    integer output_channel_index;

    assign window_ready =
        (context_count < 2) && all_weight_roms_initialized;
    assign accept_window = window_valid && window_ready;
    assign feature_valid =
        (context_count != 0) && context_result_complete[output_head];
    assign retire_output = feature_valid && feature_ready;
    assign feature_values = context_values[output_head];
    assign feature_row = context_row[output_head];
    assign feature_column = context_column[output_head];
    assign feature_last = context_last[output_head];

    assign lane_input_valid = (issue_state == ISSUE_CHANNELS);
    assign lane_first_channel =
        lane_input_valid && (issue_channel == {CHANNEL_BITS{1'b0}});
    assign lane_last_channel =
        lane_input_valid && (issue_channel == INPUT_CHANNELS - 1);
    assign tag_fifo_push = lane_last_channel;
    assign tag_fifo_pop = all_lanes_output_valid && !tag_fifo_empty;
    assign tag_fifo_full =
        (tag_count == TAG_FIFO_DEPTH[TAG_COUNT_BITS-1:0]);
    assign tag_fifo_empty = (tag_count == {TAG_COUNT_BITS{1'b0}});
    assign retired_context = tag_context_fifo[tag_head];
    assign retired_group = tag_group_fifo[tag_head];

    initial begin
        if (OUTPUT_LANES < 1)
            $error("Multi-context grouped convolution requires output lanes");
        if (APPLY_RELU != 0 && APPLY_RELU != 1)
            $error("APPLY_RELU must be zero or one");
    end

    always @* begin
        for (sample_lane = 0; sample_lane < 9; sample_lane = sample_lane + 1) begin
            issue_sample_window[sample_lane] =
                context_windows[issue_slot][
                    issue_channel * 72 + sample_lane * 8 +: 8
                ];
        end
    end

    generate
        for (output_lane = 0; output_lane < OUTPUT_LANES;
             output_lane = output_lane + 1) begin : grouped_output_lanes
            logic signed [7:0] selected_weights [0:8];
            logic signed [71:0] selected_weight_row;
            logic output_lane_is_valid;
            logic signed [31:0] selected_bias;
            logic [4:0] selected_right_shift_bits;
            logic [7:0] selected_output_channel;

            assign selected_output_channel =
                issue_group * OUTPUT_LANES + output_lane;

            always @* begin
                output_lane_is_valid =
                    (issue_group * OUTPUT_LANES + output_lane) <
                    OUTPUT_CHANNELS;
                if (output_lane_is_valid) begin
                    selected_bias = trained_bias(
                        LAYER_INDEX,
                        issue_group * OUTPUT_LANES + output_lane
                    );
                    selected_right_shift_bits = trained_right_shift(
                        LAYER_INDEX,
                        issue_group * OUTPUT_LANES + output_lane
                    );
                end else begin
                    selected_bias = 32'sd0;
                    selected_right_shift_bits = RIGHT_SHIFT_BITS[4:0];
                end
            end

            if (USE_SYNC_WEIGHT_ROM != 0) begin : synchronized_weight_rom
                gowin_trained_weight_row_rom #(
                    .LAYER_INDEX(LAYER_INDEX),
                    .INPUT_CHANNELS(INPUT_CHANNELS)
                ) weight_rom (
                    .clk(clk),
                    .output_channel(selected_output_channel),
                    .input_channel({{(8-CHANNEL_BITS){1'b0}}, issue_channel}),
                    .weight_row(selected_weight_row),
                    .initialization_complete(weight_initialization_complete),
                    .initialization_write_enable(
                        weight_initialization_write_enable
                    ),
                    .initialization_address(weight_initialization_address),
                    .initialization_weight_row(weight_initialization_row),
                    .initialized(weight_rom_initialized[output_lane])
                );
            end else begin : combinational_weight_rom
                assign weight_rom_initialized[output_lane] = 1'b1;

                always @* begin
                    if (output_lane_is_valid) begin
                        selected_weight_row = trained_weight_row(
                            trained_weight_row_index(
                                LAYER_INDEX,
                                selected_output_channel,
                                issue_channel
                            )
                        );
                    end else begin
                        selected_weight_row = 72'sd0;
                    end
                end
            end

            for (kernel_lane = 0; kernel_lane < 9;
                 kernel_lane = kernel_lane + 1) begin : grouped_weight_select
                always @* begin
                    selected_weights[kernel_lane] =
                        selected_weight_row[kernel_lane * 8 +: 8];
                end
            end

            conv2d_3x3_multi_channel #(
                .RIGHT_SHIFT_BITS(RIGHT_SHIFT_BITS),
                .DSP_MULTIPLIER_LANES(DSP_MULTIPLIER_LANES)
            ) grouped_conv_lane (
                .clk(clk),
                .reset_n(reset_n),
                .input_valid(lane_input_valid),
                .input_ready(),
                .input_first_channel(lane_first_channel),
                .input_last_channel(lane_last_channel),
                .sample_window(issue_sample_window),
                .weights(selected_weights),
                .bias(selected_bias),
                .apply_relu(APPLY_RELU != 0),
                .right_shift_bits(selected_right_shift_bits),
                .partial_valid(),
                .partial_accumulator(),
                .output_valid(lane_output_valid[output_lane]),
                .output_accumulator(lane_output_accumulator[output_lane]),
                .output_value(lane_output_value[output_lane]),
                .protocol_error(lane_protocol_error[output_lane])
            );
        end
    endgenerate

    always @* begin
        all_lanes_output_valid = 1'b1;
        all_weight_roms_initialized = 1'b1;
        any_lane_protocol_error = 1'b0;
        for (reduce_lane = 0; reduce_lane < OUTPUT_LANES;
             reduce_lane = reduce_lane + 1) begin
            all_lanes_output_valid =
                all_lanes_output_valid && lane_output_valid[reduce_lane];
            all_weight_roms_initialized =
                all_weight_roms_initialized &&
                weight_rom_initialized[reduce_lane];
            any_lane_protocol_error =
                any_lane_protocol_error || lane_protocol_error[reduce_lane];
        end
    end

    // Context ownership, grouped issue, delayed retirement, and ordered output
    // all update in one clocked block so slot reuse cannot race an old result.
    always @(posedge clk) begin
        if (!reset_n) begin
            context_occupied <= 2'b00;
            context_issue_complete <= 2'b00;
            context_result_complete <= 2'b00;
            context_count <= 2'd0;
            input_tail <= 1'b0;
            output_head <= 1'b0;
            issue_slot <= 1'b0;
            issue_state <= ISSUE_IDLE;
            issue_group <= {GROUP_BITS{1'b0}};
            issue_channel <= {CHANNEL_BITS{1'b0}};
            tag_head <= {TAG_FIFO_BITS{1'b0}};
            tag_tail <= {TAG_FIFO_BITS{1'b0}};
            tag_count <= {TAG_COUNT_BITS{1'b0}};
            context_windows[0] <= {(INPUT_CHANNELS * 72){1'b0}};
            context_windows[1] <= {(INPUT_CHANNELS * 72){1'b0}};
            context_values[0] <= {(OUTPUT_CHANNELS * 8){1'b0}};
            context_values[1] <= {(OUTPUT_CHANNELS * 8){1'b0}};
            context_row[0] <= {ROW_BITS{1'b0}};
            context_row[1] <= {ROW_BITS{1'b0}};
            context_column[0] <= {COLUMN_BITS{1'b0}};
            context_column[1] <= {COLUMN_BITS{1'b0}};
            context_last[0] <= 1'b0;
            context_last[1] <= 1'b0;
            protocol_error <= 1'b0;
        end else begin
            if (any_lane_protocol_error)
                protocol_error <= 1'b1;
            if (tag_fifo_push && tag_fifo_full && !tag_fifo_pop)
                protocol_error <= 1'b1;
            if (all_lanes_output_valid && tag_fifo_empty)
                protocol_error <= 1'b1;

            if (accept_window) begin
                context_occupied[input_tail] <= 1'b1;
                context_issue_complete[input_tail] <=
                    !window_compute_enable;
                context_result_complete[input_tail] <=
                    !window_compute_enable;
                context_windows[input_tail] <= feature_windows;
                context_values[input_tail] <=
                    {(OUTPUT_CHANNELS * 8){1'b0}};
                context_row[input_tail] <= window_row;
                context_column[input_tail] <= window_column;
                context_last[input_tail] <= window_last;
                input_tail <= !input_tail;
            end

            if (retire_output) begin
                context_occupied[output_head] <= 1'b0;
                context_issue_complete[output_head] <= 1'b0;
                context_result_complete[output_head] <= 1'b0;
                output_head <= !output_head;
            end

            case ({accept_window, retire_output})
                2'b10: context_count <= context_count + 1'b1;
                2'b01: context_count <= context_count - 1'b1;
                default: context_count <= context_count;
            endcase

            if (tag_fifo_push && !tag_fifo_full) begin
                tag_context_fifo[tag_tail] <= issue_slot;
                tag_group_fifo[tag_tail] <= issue_group;
                if (tag_tail == TAG_FIFO_DEPTH - 1)
                    tag_tail <= {TAG_FIFO_BITS{1'b0}};
                else
                    tag_tail <= tag_tail + 1'b1;
            end

            if (tag_fifo_pop) begin
                for (pack_channel = 0; pack_channel < OUTPUT_LANES;
                     pack_channel = pack_channel + 1) begin
                    output_channel_index =
                        retired_group * OUTPUT_LANES + pack_channel;
                    if (output_channel_index < OUTPUT_CHANNELS) begin
                        context_values[retired_context][
                            output_channel_index * 8 +: 8
                        ] <= lane_output_value[pack_channel];
                    end
                end
                if (retired_group == OUTPUT_GROUPS - 1)
                    context_result_complete[retired_context] <= 1'b1;
                if (tag_head == TAG_FIFO_DEPTH - 1)
                    tag_head <= {TAG_FIFO_BITS{1'b0}};
                else
                    tag_head <= tag_head + 1'b1;
            end

            case ({tag_fifo_push && !tag_fifo_full, tag_fifo_pop})
                2'b10: tag_count <= tag_count + 1'b1;
                2'b01: tag_count <= tag_count - 1'b1;
                default: tag_count <= tag_count;
            endcase

            case (issue_state)
                ISSUE_IDLE: begin
                    if (context_occupied[issue_slot]) begin
                        if (context_issue_complete[issue_slot]) begin
                            issue_slot <= !issue_slot;
                        end else begin
                            issue_group <= {GROUP_BITS{1'b0}};
                            issue_channel <= {CHANNEL_BITS{1'b0}};
                            if (USE_SYNC_WEIGHT_ROM != 0)
                                issue_state <= ISSUE_PREFETCH;
                            else
                                issue_state <= ISSUE_CHANNELS;
                        end
                    end
                end

                ISSUE_PREFETCH: begin
                    issue_state <= ISSUE_CHANNELS;
                end

                ISSUE_CHANNELS: begin
                    if (issue_channel == INPUT_CHANNELS - 1) begin
                        issue_channel <= {CHANNEL_BITS{1'b0}};
                        if (issue_group == OUTPUT_GROUPS - 1) begin
                            context_issue_complete[issue_slot] <= 1'b1;
                            issue_slot <= !issue_slot;
                            issue_group <= {GROUP_BITS{1'b0}};
                            issue_state <= ISSUE_IDLE;
                        end else begin
                            issue_group <= issue_group + 1'b1;
                            if (USE_SYNC_WEIGHT_ROM != 0)
                                issue_state <= ISSUE_PREFETCH;
                        end
                    end else begin
                        issue_channel <= issue_channel + 1'b1;
                        if (USE_SYNC_WEIGHT_ROM != 0)
                            issue_state <= ISSUE_PREFETCH;
                    end
                end

                default: begin
                    protocol_error <= 1'b1;
                    issue_state <= ISSUE_IDLE;
                end
            endcase
        end
    end
endmodule
