`timescale 1ns/1ps
// Interface-compatible experimental replacement. Only window storage/control
// changes; grouped arithmetic, trained weights, sparse masks and ownership do not.
module espcn_streaming_feature_window_buffer #(
    parameter integer IMAGE_WIDTH=640, IMAGE_HEIGHT=360, INPUT_CHANNELS=16,
    parameter integer RUNTIME_GEOMETRY=0,
    parameter integer COLUMN_BITS=(IMAGE_WIDTH<=1)?1:$clog2(IMAGE_WIDTH),
    parameter integer ROW_BITS=(IMAGE_HEIGHT<=1)?1:$clog2(IMAGE_HEIGHT),
    parameter integer GEOMETRY_COLUMN_BITS=(IMAGE_WIDTH+1<=2)?1:$clog2(IMAGE_WIDTH+1),
    parameter integer GEOMETRY_ROW_BITS=(IMAGE_HEIGHT+1<=2)?1:$clog2(IMAGE_HEIGHT+1)
) (
    input wire clk,reset_n,
    input wire [GEOMETRY_COLUMN_BITS-1:0] active_image_width,
    input wire [GEOMETRY_ROW_BITS-1:0] active_image_height,
    input wire feature_valid,
    output wire feature_ready,
    input wire signed [INPUT_CHANNELS*8-1:0] feature_values,
    output wire window_valid,
    input wire window_ready,
    output wire signed [INPUT_CHANNELS*72-1:0] feature_windows,
    output wire [ROW_BITS-1:0] window_row,
    output wire [COLUMN_BITS-1:0] window_column,
    output wire window_last,protocol_error
);
    wire [GEOMETRY_COLUMN_BITS-1:0] width=RUNTIME_GEOMETRY?active_image_width:IMAGE_WIDTH;
    wire [GEOMETRY_ROW_BITS-1:0] height=RUNTIME_GEOMETRY?active_image_height:IMAGE_HEIGHT;
    paper2_packed_bram_window #(.IMAGE_WIDTH(IMAGE_WIDTH),.IMAGE_HEIGHT(IMAGE_HEIGHT),
        .INPUT_CHANNELS(INPUT_CHANNELS),.COLUMN_BITS(COLUMN_BITS),.ROW_BITS(ROW_BITS),
        .GEOMETRY_COLUMN_BITS(GEOMETRY_COLUMN_BITS),.GEOMETRY_ROW_BITS(GEOMETRY_ROW_BITS)) packed_window(
        .clk(clk),.reset_n(reset_n),.active_image_width(width),.active_image_height(height),
        .feature_valid(feature_valid),.feature_ready(feature_ready),.feature_values(feature_values),
        .window_valid(window_valid),.window_ready(window_ready),.feature_windows(feature_windows),
        .window_row(window_row),.window_column(window_column),.window_last(window_last),.protocol_error(protocol_error));
endmodule
