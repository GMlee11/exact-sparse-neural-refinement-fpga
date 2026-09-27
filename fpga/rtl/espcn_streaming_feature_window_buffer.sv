`timescale 1ns/1ps

// Multi-channel stallable 3x3 window buffer for streaming feature maps.
//
// Conv2 and Conv3 need a 3x3 neighborhood for every feature channel. This
// module turns one packed feature vector per LR pixel into one packed bank of
// channel windows. It is built from the same stallable line buffer used by the
// Conv1 prototype, so downstream convolution can take many cycles per window
// without losing alignment or dropping border-padding windows.
module espcn_streaming_feature_window_buffer #(
    parameter integer IMAGE_WIDTH = 640,
    parameter integer IMAGE_HEIGHT = 360,
    parameter integer INPUT_CHANNELS = 16,
    parameter integer RUNTIME_GEOMETRY = 0,
    parameter integer COLUMN_BITS =
        (IMAGE_WIDTH <= 1) ? 1 : $clog2(IMAGE_WIDTH),
    parameter integer ROW_BITS =
        (IMAGE_HEIGHT <= 1) ? 1 : $clog2(IMAGE_HEIGHT),
    parameter integer GEOMETRY_COLUMN_BITS =
        (IMAGE_WIDTH + 1 <= 2) ? 1 : $clog2(IMAGE_WIDTH + 1),
    parameter integer GEOMETRY_ROW_BITS =
        (IMAGE_HEIGHT + 1 <= 2) ? 1 : $clog2(IMAGE_HEIGHT + 1)
) (
    input  logic                                      clk,
    input  logic                                      reset_n,
    input  logic [GEOMETRY_COLUMN_BITS-1:0]           active_image_width,
    input  logic [GEOMETRY_ROW_BITS-1:0]              active_image_height,

    input  logic                                      feature_valid,
    output logic                                      feature_ready,
    input  logic signed [INPUT_CHANNELS*8-1:0]        feature_values,

    output logic                                      window_valid,
    input  logic                                      window_ready,
    output logic signed [INPUT_CHANNELS*72-1:0]       feature_windows,
    output logic [ROW_BITS-1:0]                       window_row,
    output logic [COLUMN_BITS-1:0]                    window_column,
    output logic                                      window_last,
    output logic                                      protocol_error
);
    logic [INPUT_CHANNELS-1:0] channel_pixel_ready;
    logic [INPUT_CHANNELS-1:0] channel_window_valid;
    logic [INPUT_CHANNELS-1:0] channel_frame_done;
    logic [71:0] channel_window_flat [0:INPUT_CHANNELS-1];
    logic [ROW_BITS-1:0] channel_window_row [0:INPUT_CHANNELS-1];
    logic [COLUMN_BITS-1:0] channel_window_column [0:INPUT_CHANNELS-1];
    logic line_feature_valid;
    logic all_channels_ready;
    logic all_channels_valid;
    logic any_channel_done;
    logic all_channel_done;
    logic alignment_error;
    logic [GEOMETRY_COLUMN_BITS-1:0] effective_image_width;
    logic [GEOMETRY_ROW_BITS-1:0] effective_image_height;

    genvar channel_index;
    integer pack_channel;
    integer reduce_channel;

    assign line_feature_valid = feature_valid && feature_ready;
    assign feature_ready = all_channels_ready;
    assign window_valid = all_channels_valid;
    assign window_row = channel_window_row[0];
    assign window_column = channel_window_column[0];
    assign effective_image_width = RUNTIME_GEOMETRY != 0 ?
        active_image_width : IMAGE_WIDTH;
    assign effective_image_height = RUNTIME_GEOMETRY != 0 ?
        active_image_height : IMAGE_HEIGHT;
    assign window_last =
        window_valid &&
        (window_row == effective_image_height - 1'b1) &&
        (window_column == effective_image_width - 1'b1);

    generate
        for (channel_index = 0; channel_index < INPUT_CHANNELS;
             channel_index = channel_index + 1) begin : feature_channel_buffers
            line_buffer_3x3_stallable #(
                .IMAGE_WIDTH(IMAGE_WIDTH),
                .IMAGE_HEIGHT(IMAGE_HEIGHT),
                .RUNTIME_GEOMETRY(RUNTIME_GEOMETRY)
            ) channel_line_buffer (
                .clk(clk),
                .reset_n(reset_n),
                .active_image_width(active_image_width),
                .active_image_height(active_image_height),
                .pixel_valid(line_feature_valid),
                .pixel_ready(channel_pixel_ready[channel_index]),
                .pixel_value(feature_values[channel_index * 8 +: 8]),
                .window_valid(channel_window_valid[channel_index]),
                .window_ready(window_ready),
                .sample_window_flat(channel_window_flat[channel_index]),
                .output_row(channel_window_row[channel_index]),
                .output_column(channel_window_column[channel_index]),
                .frame_done(channel_frame_done[channel_index])
            );
        end
    endgenerate

    // Pack every channel's 72-bit window into one wide bus so the grouped
    // convolution stage can select channel windows by simple fixed slices.
    always @* begin
        feature_windows = {(INPUT_CHANNELS * 72){1'b0}};
        for (pack_channel = 0; pack_channel < INPUT_CHANNELS;
             pack_channel = pack_channel + 1) begin
            feature_windows[pack_channel * 72 +: 72] =
                channel_window_flat[pack_channel];
        end
    end

    // Reduction and alignment checks are kept explicit for Vivado 2020.2.
    // Every channel should have the same ready/valid and row/column behavior
    // because all line buffers see the same pixel stream.
    always @* begin
        all_channels_ready = 1'b1;
        all_channels_valid = 1'b1;
        any_channel_done = 1'b0;
        all_channel_done = 1'b1;
        alignment_error = 1'b0;

        for (reduce_channel = 0; reduce_channel < INPUT_CHANNELS;
             reduce_channel = reduce_channel + 1) begin
            all_channels_ready =
                all_channels_ready && channel_pixel_ready[reduce_channel];
            all_channels_valid =
                all_channels_valid && channel_window_valid[reduce_channel];
            any_channel_done =
                any_channel_done || channel_frame_done[reduce_channel];
            all_channel_done =
                all_channel_done && channel_frame_done[reduce_channel];

            if (channel_window_valid[reduce_channel] !=
                channel_window_valid[0]) begin
                alignment_error = 1'b1;
            end
            if (channel_window_valid[reduce_channel] &&
                ((channel_window_row[reduce_channel] != channel_window_row[0]) ||
                 (channel_window_column[reduce_channel] !=
                  channel_window_column[0]))) begin
                alignment_error = 1'b1;
            end
        end

        if (any_channel_done && !all_channel_done) begin
            alignment_error = 1'b1;
        end
    end

    always @(posedge clk) begin
        if (!reset_n) begin
            protocol_error <= 1'b0;
        end else if (alignment_error) begin
            protocol_error <= 1'b1;
        end
    end
endmodule
