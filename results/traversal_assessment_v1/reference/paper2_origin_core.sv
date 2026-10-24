`timescale 1ns/1ps

import espcn_fpga_student_weights_pkg::*;

// End-to-end line-buffered ESPCN INT8 core for small simulation and synthesis.
//
// This is the first true streaming version of the learned branch: raw RGB
// pixels feed line-buffer windows, Conv1/Conv2/Conv3 consume grouped windows,
// and PixelShuffle emits the learned HR RGB correction. A surrounding
// reconstruction stage adds this signed Q7 correction to an exact bicubic
// baseline; the latest board wrapper owns that stage in PL, while historical
// captures used ARM. The arithmetic is intentionally grouped to keep DSP use
// bounded; throughput is therefore measured honestly rather than hidden behind
// full parallelism that the Zybo Z7-20 cannot afford.
module paper2_origin_core #(
    parameter integer IMAGE_WIDTH = 640,
    parameter integer IMAGE_HEIGHT = 360,
    parameter integer RUNTIME_GEOMETRY = 0,
    parameter integer OUTPUT_LANES = 4,
    // OUTPUT_LANES remains the compatibility default.  The per-layer values
    // let a physical design move DSPs toward its measured bottleneck without
    // changing weights, arithmetic, or the external streaming contract.
    parameter integer CONV1_OUTPUT_LANES = OUTPUT_LANES,
    parameter integer CONV2_OUTPUT_LANES = OUTPUT_LANES,
    parameter integer CONV3_OUTPUT_LANES = OUTPUT_LANES,
    // The frozen pipeline uses one context. Paper 2 experiments opt into two
    // contexts to issue the next pixel while the prior MAC result retires.
    parameter integer GROUPED_CONTEXTS = 1,
    parameter integer ENABLE_HIERARCHICAL_MASK = 0,
    parameter integer MASK_TILE_WIDTH = 64,
    parameter integer MASK_TILE_HEIGHT = 60,
    parameter integer FEATURE_CHANNELS = TRAINED_FEATURE_CHANNELS,
    parameter integer RIGHT_SHIFT_BITS = TRAINED_DEFAULT_RIGHT_SHIFT_BITS,
    parameter integer DSP_MULTIPLIER_LANES = 9,
    parameter integer COLUMN_BITS =
        (IMAGE_WIDTH <= 1) ? 1 : $clog2(IMAGE_WIDTH),
    parameter integer ROW_BITS =
        (IMAGE_HEIGHT <= 1) ? 1 : $clog2(IMAGE_HEIGHT),
    parameter integer HR_WIDTH = IMAGE_WIDTH * 2,
    parameter integer HR_HEIGHT = IMAGE_HEIGHT * 2,
    parameter integer HR_COLUMN_BITS =
        (HR_WIDTH <= 1) ? 1 : $clog2(HR_WIDTH),
    parameter integer HR_ROW_BITS =
        (HR_HEIGHT <= 1) ? 1 : $clog2(HR_HEIGHT),
    parameter integer GEOMETRY_COLUMN_BITS =
        (IMAGE_WIDTH + 1 <= 2) ? 1 : $clog2(IMAGE_WIDTH + 1),
    parameter integer GEOMETRY_ROW_BITS =
        (IMAGE_HEIGHT + 1 <= 2) ? 1 : $clog2(IMAGE_HEIGHT + 1)
) (
    input  logic                                clk,
    input  logic                                reset_n,
    input logic zero_compaction_enable,
    input  logic [GEOMETRY_COLUMN_BITS-1:0]     active_image_width,
    input  logic [GEOMETRY_ROW_BITS-1:0]        active_image_height,

    input logic [ROW_BITS-1:0] mask_origin_row,
    input logic [COLUMN_BITS-1:0] mask_origin_column,
    input  logic                                pixel_valid,
    output logic                                pixel_ready,
    input  logic signed [23:0]                  pixel_rgb,
    input  logic [63:0]                         selected_tile_mask,

    output logic                                rgb_valid,
    input  logic                                rgb_ready,
    output logic signed [23:0]                  rgb_data,
    output logic [HR_ROW_BITS-1:0]              rgb_row,
    output logic [HR_COLUMN_BITS-1:0]           rgb_column,
    output logic                                frame_done,
    output logic                                protocol_error,
    output logic [31:0]                         conv1_active_positions,
    output logic [31:0]                         conv2_active_positions,
    output logic [31:0]                         conv3_active_positions,
    output logic [31:0]                         conv1_bypassed_positions,
    output logic [31:0]                         conv2_bypassed_positions,
    output logic [31:0]                         conv3_bypassed_positions,
    output logic [31:0]                         raw_input_wait_cycles,
    output logic [31:0]                         conv1_window_wait_cycles,
    output logic [31:0]                         conv1_output_wait_cycles,
    output logic [31:0]                         conv2_window_wait_cycles,
    output logic [31:0]                         conv2_output_wait_cycles,
    output logic [31:0]                         conv3_window_wait_cycles,
    output logic [31:0]                         conv3_output_wait_cycles
);
`ifdef UPSCALING_TARGET_GOWIN
    localparam integer USE_SYNC_WEIGHT_ROM = 1;
`else
    localparam integer USE_SYNC_WEIGHT_ROM = 0;
`endif
    logic weight_initialization_complete;
    logic [2:0] weight_layer_write_enable;
    logic [7:0] weight_layer_write_address;
    logic signed [71:0] weight_initialization_row;
    logic raw_window_valid;
    logic raw_window_ready;
    logic signed [3*72-1:0] raw_windows;
    logic [ROW_BITS-1:0] raw_window_row;
    logic [COLUMN_BITS-1:0] raw_window_column;
    logic raw_window_last;
    logic raw_window_protocol_error;

    logic conv1_valid;
    logic conv1_ready;
    logic signed [FEATURE_CHANNELS*8-1:0] conv1_values;
    logic [ROW_BITS-1:0] conv1_row;
    logic [COLUMN_BITS-1:0] conv1_column;
    logic conv1_last;
    logic conv1_protocol_error;

    logic conv2_window_valid;
    logic conv2_window_ready;
    logic signed [FEATURE_CHANNELS*72-1:0] conv2_windows;
    logic [ROW_BITS-1:0] conv2_window_row;
    logic [COLUMN_BITS-1:0] conv2_window_column;
    logic conv2_window_last;
    logic conv2_window_protocol_error;

    logic conv2_valid;
    logic conv2_ready;
    logic signed [FEATURE_CHANNELS*8-1:0] conv2_values;
    logic [ROW_BITS-1:0] conv2_row;
    logic [COLUMN_BITS-1:0] conv2_column;
    logic conv2_last;
    logic conv2_protocol_error;

    logic conv3_window_valid;
    logic conv3_window_ready;
    logic signed [FEATURE_CHANNELS*72-1:0] conv3_windows;
    logic [ROW_BITS-1:0] conv3_window_row;
    logic [COLUMN_BITS-1:0] conv3_window_column;
    logic conv3_window_last;
    logic conv3_window_protocol_error;

    logic conv3_valid;
    logic conv3_ready;
    logic signed [12*8-1:0] conv3_values;
    logic [ROW_BITS-1:0] conv3_row;
    logic [COLUMN_BITS-1:0] conv3_column;
    logic conv3_last;
    logic conv3_protocol_error;
    logic pixel_shuffle_protocol_error;
    logic conv1_compute_enable;
    logic conv2_compute_enable;
    logic conv3_compute_enable;

    logic conv1_mask_selected;
    logic conv2_mask_selected;
    logic conv3_mask_selected;

    // Each layer receives the exact backward receptive-field dilation needed
    // for selected Conv3 outputs. The lookup inspects at most nine neighboring
    // tiles instead of comparing each coordinate against the full 10x6 grid.
    sparse_hierarchical_mask_lookup #(
        .IMAGE_WIDTH(IMAGE_WIDTH),
        .IMAGE_HEIGHT(IMAGE_HEIGHT),
        .MASK_TILE_WIDTH(MASK_TILE_WIDTH),
        .MASK_TILE_HEIGHT(MASK_TILE_HEIGHT),
        .RADIUS(2),
        .COLUMN_BITS(COLUMN_BITS),
        .ROW_BITS(ROW_BITS)
    ) conv1_mask_lookup (
        .selected_tile_mask(selected_tile_mask),
        .row(raw_window_row+mask_origin_row),
        .column(raw_window_column+mask_origin_column),
        .selected(conv1_mask_selected)
    );

    sparse_hierarchical_mask_lookup #(
        .IMAGE_WIDTH(IMAGE_WIDTH),
        .IMAGE_HEIGHT(IMAGE_HEIGHT),
        .MASK_TILE_WIDTH(MASK_TILE_WIDTH),
        .MASK_TILE_HEIGHT(MASK_TILE_HEIGHT),
        .RADIUS(1),
        .COLUMN_BITS(COLUMN_BITS),
        .ROW_BITS(ROW_BITS)
    ) conv2_mask_lookup (
        .selected_tile_mask(selected_tile_mask),
        .row(conv2_window_row+mask_origin_row),
        .column(conv2_window_column+mask_origin_column),
        .selected(conv2_mask_selected)
    );

    sparse_hierarchical_mask_lookup #(
        .IMAGE_WIDTH(IMAGE_WIDTH),
        .IMAGE_HEIGHT(IMAGE_HEIGHT),
        .MASK_TILE_WIDTH(MASK_TILE_WIDTH),
        .MASK_TILE_HEIGHT(MASK_TILE_HEIGHT),
        .RADIUS(0),
        .COLUMN_BITS(COLUMN_BITS),
        .ROW_BITS(ROW_BITS)
    ) conv3_mask_lookup (
        .selected_tile_mask(selected_tile_mask),
        .row(conv3_window_row+mask_origin_row),
        .column(conv3_window_column+mask_origin_column),
        .selected(conv3_mask_selected)
    );

    always @* begin
        conv1_compute_enable =
            (ENABLE_HIERARCHICAL_MASK == 0) || conv1_mask_selected;
        conv2_compute_enable =
            (ENABLE_HIERARCHICAL_MASK == 0) || conv2_mask_selected;
        conv3_compute_enable =
            (ENABLE_HIERARCHICAL_MASK == 0) || conv3_mask_selected;
    end

    // Count accepted windows at the exact MAC issue boundary. These counters
    // are causal evidence that cycle savings came from real layer bypass.
    always @(posedge clk) begin
        if (!reset_n) begin
            conv1_active_positions <= 32'd0;
            conv2_active_positions <= 32'd0;
            conv3_active_positions <= 32'd0;
            conv1_bypassed_positions <= 32'd0;
            conv2_bypassed_positions <= 32'd0;
            conv3_bypassed_positions <= 32'd0;
        end else begin
            if (raw_window_valid && raw_window_ready) begin
                if (conv1_compute_enable)
                    conv1_active_positions <= conv1_active_positions + 1'b1;
                else
                    conv1_bypassed_positions <= conv1_bypassed_positions + 1'b1;
            end
            if (conv2_window_valid && conv2_window_ready) begin
                if (conv2_compute_enable)
                    conv2_active_positions <= conv2_active_positions + 1'b1;
                else
                    conv2_bypassed_positions <= conv2_bypassed_positions + 1'b1;
            end
            if (conv3_window_valid && conv3_window_ready) begin
                if (conv3_compute_enable)
                    conv3_active_positions <= conv3_active_positions + 1'b1;
                else
                    conv3_bypassed_positions <= conv3_bypassed_positions + 1'b1;
            end
        end
    end

    // Count backpressure at every pipeline boundary. These counters overlap
    // intentionally: two stages may be blocked in the same cycle. They expose
    // where service time originates without changing any valid/ready signal.
    always @(posedge clk) begin
        if (!reset_n) begin
            raw_input_wait_cycles <= 32'd0;
            conv1_window_wait_cycles <= 32'd0;
            conv1_output_wait_cycles <= 32'd0;
            conv2_window_wait_cycles <= 32'd0;
            conv2_output_wait_cycles <= 32'd0;
            conv3_window_wait_cycles <= 32'd0;
            conv3_output_wait_cycles <= 32'd0;
        end else begin
            if (pixel_valid && !pixel_ready)
                raw_input_wait_cycles <= raw_input_wait_cycles + 1'b1;
            if (raw_window_valid && !raw_window_ready)
                conv1_window_wait_cycles <= conv1_window_wait_cycles + 1'b1;
            if (conv1_valid && !conv1_ready)
                conv1_output_wait_cycles <= conv1_output_wait_cycles + 1'b1;
            if (conv2_window_valid && !conv2_window_ready)
                conv2_window_wait_cycles <= conv2_window_wait_cycles + 1'b1;
            if (conv2_valid && !conv2_ready)
                conv2_output_wait_cycles <= conv2_output_wait_cycles + 1'b1;
            if (conv3_window_valid && !conv3_window_ready)
                conv3_window_wait_cycles <= conv3_window_wait_cycles + 1'b1;
            if (conv3_valid && !conv3_ready)
                conv3_output_wait_cycles <= conv3_output_wait_cycles + 1'b1;
        end
    end

`ifdef UPSCALING_TARGET_GOWIN
    // One decoder loads all three trained layers into their Gowin BSRAM banks
    // before any layer accepts a feature window.
    gowin_trained_weight_loader #(
        .FEATURE_CHANNELS(FEATURE_CHANNELS)
    ) trained_weight_loader (
        .clk(clk),
        .initialization_complete(weight_initialization_complete),
        .layer_write_enable(weight_layer_write_enable),
        .layer_write_address(weight_layer_write_address),
        .layer_weight_row(weight_initialization_row)
    );
`else
    assign weight_initialization_complete = 1'b1;
    assign weight_layer_write_enable = 3'b000;
    assign weight_layer_write_address = 8'd0;
    assign weight_initialization_row = 72'sd0;
`endif

    assign protocol_error =
        raw_window_protocol_error ||
        conv1_protocol_error ||
        conv2_window_protocol_error ||
        conv2_protocol_error ||
        conv3_window_protocol_error ||
        conv3_protocol_error ||
        pixel_shuffle_protocol_error;

    espcn_streaming_feature_window_buffer #(
        .IMAGE_WIDTH(IMAGE_WIDTH),
        .IMAGE_HEIGHT(IMAGE_HEIGHT),
        .INPUT_CHANNELS(3),
        .RUNTIME_GEOMETRY(RUNTIME_GEOMETRY)
    ) raw_window_buffer (
        .clk(clk),
        .reset_n(reset_n),
        .active_image_width(active_image_width),
        .active_image_height(active_image_height),
        .feature_valid(pixel_valid),
        .feature_ready(pixel_ready),
        .feature_values(pixel_rgb),
        .window_valid(raw_window_valid),
        .window_ready(raw_window_ready),
        .feature_windows(raw_windows),
        .window_row(raw_window_row),
        .window_column(raw_window_column),
        .window_last(raw_window_last),
        .protocol_error(raw_window_protocol_error)
    );

    espcn_streaming_grouped_conv_layer_selectable #(
        .USE_TWO_CONTEXTS(GROUPED_CONTEXTS >= 2),
        .LAYER_INDEX(0),
        .INPUT_CHANNELS(3),
        .OUTPUT_CHANNELS(FEATURE_CHANNELS),
        .OUTPUT_LANES(CONV1_OUTPUT_LANES),
        .APPLY_RELU(1),
        .RIGHT_SHIFT_BITS(RIGHT_SHIFT_BITS),
        .DSP_MULTIPLIER_LANES(DSP_MULTIPLIER_LANES),
        .USE_SYNC_WEIGHT_ROM(USE_SYNC_WEIGHT_ROM),
        .COLUMN_BITS(COLUMN_BITS),
        .ROW_BITS(ROW_BITS)
    ) conv1_layer (
        .clk(clk),
        .reset_n(reset_n),
        .weight_initialization_complete(weight_initialization_complete),
        .weight_initialization_write_enable(weight_layer_write_enable[0]),
        .weight_initialization_address(weight_layer_write_address),
        .weight_initialization_row(weight_initialization_row),
        .window_valid(raw_window_valid),
        .window_ready(raw_window_ready),
        .zero_compaction_enable(zero_compaction_enable),
        .window_compute_enable(conv1_compute_enable),
        .feature_windows(raw_windows),
        .window_row(raw_window_row),
        .window_column(raw_window_column),
        .window_last(raw_window_last),
        .feature_valid(conv1_valid),
        .feature_ready(conv1_ready),
        .feature_values(conv1_values),
        .feature_row(conv1_row),
        .feature_column(conv1_column),
        .feature_last(conv1_last),
        .protocol_error(conv1_protocol_error)
    );

    espcn_streaming_feature_window_buffer #(
        .IMAGE_WIDTH(IMAGE_WIDTH),
        .IMAGE_HEIGHT(IMAGE_HEIGHT),
        .INPUT_CHANNELS(FEATURE_CHANNELS),
        .RUNTIME_GEOMETRY(RUNTIME_GEOMETRY)
    ) conv2_window_buffer (
        .clk(clk),
        .reset_n(reset_n),
        .active_image_width(active_image_width),
        .active_image_height(active_image_height),
        .feature_valid(conv1_valid),
        .feature_ready(conv1_ready),
        .feature_values(conv1_values),
        .window_valid(conv2_window_valid),
        .window_ready(conv2_window_ready),
        .feature_windows(conv2_windows),
        .window_row(conv2_window_row),
        .window_column(conv2_window_column),
        .window_last(conv2_window_last),
        .protocol_error(conv2_window_protocol_error)
    );

    espcn_streaming_grouped_conv_layer_selectable #(
        .USE_TWO_CONTEXTS(GROUPED_CONTEXTS >= 2),
        .LAYER_INDEX(1),
        .INPUT_CHANNELS(FEATURE_CHANNELS),
        .OUTPUT_CHANNELS(FEATURE_CHANNELS),
        .OUTPUT_LANES(CONV2_OUTPUT_LANES),
        .APPLY_RELU(1),
        .RIGHT_SHIFT_BITS(RIGHT_SHIFT_BITS),
        .DSP_MULTIPLIER_LANES(DSP_MULTIPLIER_LANES),
        .USE_SYNC_WEIGHT_ROM(USE_SYNC_WEIGHT_ROM),
        .COLUMN_BITS(COLUMN_BITS),
        .ROW_BITS(ROW_BITS)
    ) conv2_layer (
        .clk(clk),
        .reset_n(reset_n),
        .weight_initialization_complete(weight_initialization_complete),
        .weight_initialization_write_enable(weight_layer_write_enable[1]),
        .weight_initialization_address(weight_layer_write_address),
        .weight_initialization_row(weight_initialization_row),
        .window_valid(conv2_window_valid),
        .window_ready(conv2_window_ready),
        .zero_compaction_enable(zero_compaction_enable),
        .window_compute_enable(conv2_compute_enable),
        .feature_windows(conv2_windows),
        .window_row(conv2_window_row),
        .window_column(conv2_window_column),
        .window_last(conv2_window_last),
        .feature_valid(conv2_valid),
        .feature_ready(conv2_ready),
        .feature_values(conv2_values),
        .feature_row(conv2_row),
        .feature_column(conv2_column),
        .feature_last(conv2_last),
        .protocol_error(conv2_protocol_error)
    );

    espcn_streaming_feature_window_buffer #(
        .IMAGE_WIDTH(IMAGE_WIDTH),
        .IMAGE_HEIGHT(IMAGE_HEIGHT),
        .INPUT_CHANNELS(FEATURE_CHANNELS),
        .RUNTIME_GEOMETRY(RUNTIME_GEOMETRY)
    ) conv3_window_buffer (
        .clk(clk),
        .reset_n(reset_n),
        .active_image_width(active_image_width),
        .active_image_height(active_image_height),
        .feature_valid(conv2_valid),
        .feature_ready(conv2_ready),
        .feature_values(conv2_values),
        .window_valid(conv3_window_valid),
        .window_ready(conv3_window_ready),
        .feature_windows(conv3_windows),
        .window_row(conv3_window_row),
        .window_column(conv3_window_column),
        .window_last(conv3_window_last),
        .protocol_error(conv3_window_protocol_error)
    );

    espcn_streaming_grouped_conv_layer_selectable #(
        .USE_TWO_CONTEXTS(GROUPED_CONTEXTS >= 2),
        .LAYER_INDEX(2),
        .INPUT_CHANNELS(FEATURE_CHANNELS),
        .OUTPUT_CHANNELS(12),
        .OUTPUT_LANES(CONV3_OUTPUT_LANES),
        .APPLY_RELU(0),
        .RIGHT_SHIFT_BITS(RIGHT_SHIFT_BITS),
        .DSP_MULTIPLIER_LANES(DSP_MULTIPLIER_LANES),
        .USE_SYNC_WEIGHT_ROM(USE_SYNC_WEIGHT_ROM),
        .COLUMN_BITS(COLUMN_BITS),
        .ROW_BITS(ROW_BITS)
    ) conv3_layer (
        .clk(clk),
        .reset_n(reset_n),
        .weight_initialization_complete(weight_initialization_complete),
        .weight_initialization_write_enable(weight_layer_write_enable[2]),
        .weight_initialization_address(weight_layer_write_address),
        .weight_initialization_row(weight_initialization_row),
        .window_valid(conv3_window_valid),
        .window_ready(conv3_window_ready),
        .zero_compaction_enable(zero_compaction_enable),
        .window_compute_enable(conv3_compute_enable),
        .feature_windows(conv3_windows),
        .window_row(conv3_window_row),
        .window_column(conv3_window_column),
        .window_last(conv3_window_last),
        .feature_valid(conv3_valid),
        .feature_ready(conv3_ready),
        .feature_values(conv3_values),
        .feature_row(conv3_row),
        .feature_column(conv3_column),
        .feature_last(conv3_last),
        .protocol_error(conv3_protocol_error)
    );

    espcn_streaming_pixel_shuffle_rgb #(
        .IMAGE_WIDTH(IMAGE_WIDTH),
        .IMAGE_HEIGHT(IMAGE_HEIGHT),
        .RUNTIME_GEOMETRY(RUNTIME_GEOMETRY)
    ) pixel_shuffle (
        .clk(clk),
        .reset_n(reset_n),
        .active_image_width(active_image_width),
        .active_image_height(active_image_height),
        .conv3_valid(conv3_valid),
        .conv3_ready(conv3_ready),
        .conv3_values(conv3_values),
        .conv3_last(conv3_last),
        .rgb_valid(rgb_valid),
        .rgb_ready(rgb_ready),
        .rgb_data(rgb_data),
        .rgb_row(rgb_row),
        .rgb_column(rgb_column),
        .frame_done(frame_done),
        .protocol_error(pixel_shuffle_protocol_error)
    );
endmodule

