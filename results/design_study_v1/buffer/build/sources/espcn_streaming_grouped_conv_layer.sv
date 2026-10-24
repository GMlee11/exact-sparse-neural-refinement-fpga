`timescale 1ns/1ps

import espcn_fpga_student_weights_pkg::*;

// Streaming grouped trained 3x3 convolution layer.
//
// A complete multi-channel 3x3 window bank is accepted for one LR pixel. The
// layer then walks output-channel groups and input channels through a small bank
// of `conv2d_3x3_multi_channel` lanes. This keeps DSP use bounded by
// OUTPUT_LANES*9 per layer while still producing a full packed feature vector
// for the next streaming stage.
module espcn_streaming_grouped_conv_layer #(
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
    parameter integer OUTPUT_GROUPS = (OUTPUT_CHANNELS + OUTPUT_LANES - 1) / OUTPUT_LANES,
    parameter integer GROUP_FIFO_DEPTH = OUTPUT_GROUPS + 8,
    parameter integer GROUP_BITS =
        (OUTPUT_GROUPS <= 1) ? 1 : $clog2(OUTPUT_GROUPS),
    parameter integer CHANNEL_BITS =
        (INPUT_CHANNELS <= 1) ? 1 : $clog2(INPUT_CHANNELS),
    parameter integer GROUP_FIFO_BITS =
        (GROUP_FIFO_DEPTH <= 1) ? 1 : $clog2(GROUP_FIFO_DEPTH),
    parameter integer GROUP_COUNT_BITS =
        (GROUP_FIFO_DEPTH + 1 <= 1) ? 1 : $clog2(GROUP_FIFO_DEPTH + 1),
    parameter integer RETIRED_COUNT_BITS =
        (OUTPUT_GROUPS + 1 <= 1) ? 1 : $clog2(OUTPUT_GROUPS + 1)
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
    typedef enum logic [2:0] {
        STATE_IDLE,
        STATE_PREFETCH,
        STATE_ISSUE,
        STATE_WAIT_RESULTS,
        STATE_OUTPUT
    } state_t;

    state_t state;
    logic signed [INPUT_CHANNELS*72-1:0] captured_windows;
    logic [ROW_BITS-1:0] captured_row;
    logic [COLUMN_BITS-1:0] captured_column;
    logic captured_last;

    logic [GROUP_BITS-1:0] issue_group;
    logic [CHANNEL_BITS-1:0] issue_channel;
    logic signed [7:0] issue_sample_window [0:8];
    logic lane_input_valid;
    logic lane_first_channel;
    logic lane_last_channel;
    logic group_last_channel;

    logic [GROUP_BITS-1:0] group_fifo [0:GROUP_FIFO_DEPTH-1];
    logic [GROUP_FIFO_BITS-1:0] group_head;
    logic [GROUP_FIFO_BITS-1:0] group_tail;
    logic [GROUP_COUNT_BITS-1:0] group_count;
    logic group_fifo_full;
    logic group_fifo_empty;
    logic group_fifo_push;
    logic group_fifo_pop;

    logic lane_output_valid [0:OUTPUT_LANES-1];
    logic signed [31:0] lane_output_accumulator [0:OUTPUT_LANES-1];
    logic signed [7:0] lane_output_value [0:OUTPUT_LANES-1];
    logic lane_protocol_error [0:OUTPUT_LANES-1];
    logic weight_rom_initialized [0:OUTPUT_LANES-1];
    logic all_lanes_output_valid;
    logic all_weight_roms_initialized;
    logic any_lane_protocol_error;
    logic [GROUP_BITS-1:0] retired_group;
    logic [RETIRED_COUNT_BITS-1:0] retired_group_count;
    logic signed [OUTPUT_CHANNELS*8-1:0] feature_value_register;

    genvar output_lane;
    genvar kernel_lane;
    integer sample_lane;
    integer pack_channel;
    integer reduce_lane;
    integer output_channel_index;

    assign window_ready =
        (state == STATE_IDLE) && all_weight_roms_initialized;
    assign lane_input_valid = (state == STATE_ISSUE);
    assign lane_first_channel =
        (state == STATE_ISSUE) && (issue_channel == {CHANNEL_BITS{1'b0}});
    assign lane_last_channel =
        (state == STATE_ISSUE) && (issue_channel == INPUT_CHANNELS - 1);
    assign group_last_channel = lane_last_channel;
    assign group_fifo_push = group_last_channel;
    assign group_fifo_pop = all_lanes_output_valid && !group_fifo_empty;
    assign group_fifo_full =
        (group_count == GROUP_FIFO_DEPTH[GROUP_COUNT_BITS-1:0]);
    assign group_fifo_empty = (group_count == {GROUP_COUNT_BITS{1'b0}});
    assign retired_group = group_fifo[group_head];
    assign feature_valid = (state == STATE_OUTPUT);
    assign feature_values = feature_value_register;
    assign feature_row = captured_row;
    assign feature_column = captured_column;
    assign feature_last = captured_last;

    initial begin
        if (OUTPUT_LANES < 1) begin
            $error("Streaming grouped convolution requires at least one output lane");
        end
        if (APPLY_RELU != 0 && APPLY_RELU != 1) begin
            $error("APPLY_RELU must be 0 or 1");
        end
    end

    always @* begin
        for (sample_lane = 0; sample_lane < 9; sample_lane = sample_lane + 1) begin
            issue_sample_window[sample_lane] =
                captured_windows[
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

            // The near-full-DSP ablation can use lane counts such as 6 or 8
            // even though Conv1/Conv2 have 16 output channels and Conv3 has
            // 12. The final group may therefore contain unused lanes; those
            // lanes receive zero weights and zero bias so they retire normally
            // without corrupting the packed feature vector.
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

            // The Gowin path stores rows in BSRAM and prefetches them.  Other
            // targets retain the established zero-wait combinational selector
            // so this portability work does not slow the Zybo implementation.
                if (USE_SYNC_WEIGHT_ROM != 0) begin : synchronized_weight_rom
                    gowin_trained_weight_row_rom #(
                        .LAYER_INDEX(LAYER_INDEX),
                        .INPUT_CHANNELS(INPUT_CHANNELS)
                    ) weight_rom (
                        .clk(clk),
                        .output_channel(selected_output_channel),
                        .input_channel({{(8-CHANNEL_BITS){1'b0}}, issue_channel}),
                        .weight_row(selected_weight_row),
                        .initialization_complete(
                            weight_initialization_complete
                        ),
                        .initialization_write_enable(
                            weight_initialization_write_enable
                        ),
                        .initialization_address(
                            weight_initialization_address
                        ),
                        .initialization_weight_row(
                            weight_initialization_row
                        ),
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

    // One pixel is processed at a time. Output groups may be in flight while
    // later groups are being issued, so a small FIFO tracks which group belongs
    // to each delayed lane result.
    always @(posedge clk) begin
        if (!reset_n) begin
            state <= STATE_IDLE;
            captured_windows <= {(INPUT_CHANNELS * 72){1'b0}};
            captured_row <= {ROW_BITS{1'b0}};
            captured_column <= {COLUMN_BITS{1'b0}};
            captured_last <= 1'b0;
            issue_group <= {GROUP_BITS{1'b0}};
            issue_channel <= {CHANNEL_BITS{1'b0}};
            group_head <= {GROUP_FIFO_BITS{1'b0}};
            group_tail <= {GROUP_FIFO_BITS{1'b0}};
            group_count <= {GROUP_COUNT_BITS{1'b0}};
            retired_group_count <= {RETIRED_COUNT_BITS{1'b0}};
            feature_value_register <= {(OUTPUT_CHANNELS * 8){1'b0}};
            protocol_error <= 1'b0;
        end else begin
            if (any_lane_protocol_error) begin
                protocol_error <= 1'b1;
            end
            if (group_fifo_push && group_fifo_full && !group_fifo_pop) begin
                protocol_error <= 1'b1;
            end
            if (all_lanes_output_valid && group_fifo_empty) begin
                protocol_error <= 1'b1;
            end

            if (group_fifo_push && !group_fifo_full) begin
                group_fifo[group_tail] <= issue_group;
                if (group_tail == GROUP_FIFO_DEPTH - 1) begin
                    group_tail <= {GROUP_FIFO_BITS{1'b0}};
                end else begin
                    group_tail <= group_tail + 1'b1;
                end
            end

                if (group_fifo_pop) begin
                    for (pack_channel = 0; pack_channel < OUTPUT_LANES;
                         pack_channel = pack_channel + 1) begin
                    output_channel_index =
                        retired_group * OUTPUT_LANES + pack_channel;
                    if (output_channel_index < OUTPUT_CHANNELS) begin
                        feature_value_register[
                            output_channel_index * 8 +: 8
                        ] <= lane_output_value[pack_channel];
                    end
                end

                if (group_head == GROUP_FIFO_DEPTH - 1) begin
                    group_head <= {GROUP_FIFO_BITS{1'b0}};
                end else begin
                    group_head <= group_head + 1'b1;
                end

                if (retired_group_count == OUTPUT_GROUPS - 1) begin
                    retired_group_count <= {RETIRED_COUNT_BITS{1'b0}};
                    state <= STATE_OUTPUT;
                end else begin
                    retired_group_count <= retired_group_count + 1'b1;
                end
            end

            case ({group_fifo_push && !group_fifo_full, group_fifo_pop})
                2'b10: group_count <= group_count + 1'b1;
                2'b01: group_count <= group_count - 1'b1;
                default: group_count <= group_count;
            endcase

            case (state)
                STATE_IDLE: begin
                    if (window_valid) begin
                        captured_windows <= feature_windows;
                        captured_row <= window_row;
                        captured_column <= window_column;
                        captured_last <= window_last;
                        issue_group <= {GROUP_BITS{1'b0}};
                        issue_channel <= {CHANNEL_BITS{1'b0}};
                        retired_group_count <= {RETIRED_COUNT_BITS{1'b0}};
                        feature_value_register <= {(OUTPUT_CHANNELS * 8){1'b0}};
                        // A masked position still emits a coordinate-aligned
                        // zero vector so downstream line buffers retain their
                        // raster schedule. No grouped MAC lane receives VALID.
                        if (!window_compute_enable)
                            state <= STATE_OUTPUT;
                        else if (USE_SYNC_WEIGHT_ROM != 0)
                            state <= STATE_PREFETCH;
                        else
                            state <= STATE_ISSUE;
                    end
                end

                // A synchronous block-RAM read issued during this state is
                // available to all nine MAC inputs in the following cycle.
                STATE_PREFETCH: begin
                    state <= STATE_ISSUE;
                end

                STATE_ISSUE: begin
                    if (issue_channel == INPUT_CHANNELS - 1) begin
                        issue_channel <= {CHANNEL_BITS{1'b0}};
                        if (issue_group == OUTPUT_GROUPS - 1) begin
                            state <= STATE_WAIT_RESULTS;
                        end else begin
                            issue_group <= issue_group + 1'b1;
                            if (USE_SYNC_WEIGHT_ROM != 0)
                                state <= STATE_PREFETCH;
                        end
                    end else begin
                        issue_channel <= issue_channel + 1'b1;
                        if (USE_SYNC_WEIGHT_ROM != 0)
                            state <= STATE_PREFETCH;
                    end
                end

                STATE_WAIT_RESULTS: begin
                    // The result FIFO pop path above moves to STATE_OUTPUT after
                    // the final output group has been written into the packed
                    // feature vector.
                end

                STATE_OUTPUT: begin
                    if (feature_ready) begin
                        state <= STATE_IDLE;
                    end
                end

                default: begin
                    protocol_error <= 1'b1;
                    state <= STATE_IDLE;
                end
            endcase
        end
    end
endmodule
