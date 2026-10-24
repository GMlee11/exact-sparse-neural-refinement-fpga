`timescale 1ns/1ps

// Streaming ESPCN PixelShuffle drain for RGB 2x output.
//
// Conv3 produces 12 channels per LR pixel: RGB times four 2x subpixel slots.
// To emit standard HR row-major order, top-row subpixels are streamed
// immediately while bottom-row subpixels are stored for one LR row and drained
// after the top row completes.
module espcn_streaming_pixel_shuffle_rgb #(
    parameter integer IMAGE_WIDTH = 640,
    parameter integer IMAGE_HEIGHT = 360,
    parameter integer RUNTIME_GEOMETRY = 0,
    parameter integer LR_COLUMN_BITS =
        (IMAGE_WIDTH <= 1) ? 1 : $clog2(IMAGE_WIDTH),
    parameter integer LR_ROW_BITS =
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
    input  logic [GEOMETRY_COLUMN_BITS-1:0]     active_image_width,
    input  logic [GEOMETRY_ROW_BITS-1:0]        active_image_height,

    input logic [63:0] selected_tile_mask,
    input logic [LR_ROW_BITS-1:0] mask_origin_row,
    input logic [LR_COLUMN_BITS-1:0] mask_origin_column,
    input  logic                                conv3_valid,
    output logic                                conv3_ready,
    input  logic signed [12*8-1:0]              conv3_values,
    input  logic                                conv3_last,

    output logic                                rgb_valid,
    input  logic                                rgb_ready,
    output logic signed [23:0]                  rgb_data,
    output logic [HR_ROW_BITS-1:0]              rgb_row,
    output logic [HR_COLUMN_BITS-1:0]           rgb_column,
    output logic                                frame_done,
    output logic                                protocol_error
);
    typedef enum logic [2:0] {
        STATE_IDLE,
        STATE_EMIT_TOP,
        STATE_DRAIN_BOTTOM_READ,
        STATE_DRAIN_BOTTOM_LEFT,
        STATE_DRAIN_BOTTOM_RIGHT
    } state_t;

    state_t state;
`ifdef UPSCALING_TARGET_GOWIN
    // The 16-pixel Tang portability frame is deliberately kept in LUT-backed
    // storage because this buffer exposes an asynchronous read port.
    (* ram_style = "distributed" *) logic signed [47:0]
`else
    (* ram_style = "block" *) logic signed [47:0]
`endif
        bottom_pair_buffer [0:IMAGE_WIDTH-1];
    logic signed [47:0] bottom_pair_read_data;
    logic signed [12*8-1:0] staged_conv3;
    logic [LR_ROW_BITS-1:0] lr_row;
    logic [LR_COLUMN_BITS-1:0] lr_column;
    logic [LR_COLUMN_BITS-1:0] bottom_drain_column;
    logic top_phase;
    logic accepted_final_lr_pixel;
    logic signed [23:0] top_left_rgb;
    logic signed [23:0] top_right_rgb;
    logic signed [23:0] bottom_left_rgb;
    logic signed [23:0] bottom_right_rgb;
    logic [GEOMETRY_COLUMN_BITS-1:0] effective_image_width;
    logic [GEOMETRY_ROW_BITS-1:0] effective_image_height;

    wire top_selected, bottom_selected;
    sparse_hierarchical_mask_lookup #(.IMAGE_WIDTH(IMAGE_WIDTH),
        .IMAGE_HEIGHT(IMAGE_HEIGHT),.RADIUS(0),
        .COLUMN_BITS(LR_COLUMN_BITS),.ROW_BITS(LR_ROW_BITS)) top_mask (
        .selected_tile_mask(selected_tile_mask),.row(lr_row+mask_origin_row),
        .column(lr_column+mask_origin_column),.selected(top_selected));
    sparse_hierarchical_mask_lookup #(.IMAGE_WIDTH(IMAGE_WIDTH),
        .IMAGE_HEIGHT(IMAGE_HEIGHT),.RADIUS(0),
        .COLUMN_BITS(LR_COLUMN_BITS),.ROW_BITS(LR_ROW_BITS)) bottom_mask (
        .selected_tile_mask(selected_tile_mask),.row(lr_row+mask_origin_row),
        .column(bottom_drain_column+mask_origin_column),.selected(bottom_selected));
    assign conv3_ready = (state == STATE_IDLE);
    assign effective_image_width = RUNTIME_GEOMETRY != 0 ?
        active_image_width : IMAGE_WIDTH;
    assign effective_image_height = RUNTIME_GEOMETRY != 0 ?
        active_image_height : IMAGE_HEIGHT;
    assign rgb_valid =
        (state == STATE_EMIT_TOP) ||
        (state == STATE_DRAIN_BOTTOM_LEFT) ||
        (state == STATE_DRAIN_BOTTOM_RIGHT);

    // Decode PixelShuffle channels explicitly:
    // channel = rgb_channel*4 + subpixel_row*2 + subpixel_column.
    always @* begin
        top_left_rgb = {
            staged_conv3[8 * 8 +: 8],
            staged_conv3[4 * 8 +: 8],
            staged_conv3[0 * 8 +: 8]
        };
        top_right_rgb = {
            staged_conv3[9 * 8 +: 8],
            staged_conv3[5 * 8 +: 8],
            staged_conv3[1 * 8 +: 8]
        };
        bottom_left_rgb = {
            staged_conv3[10 * 8 +: 8],
            staged_conv3[6 * 8 +: 8],
            staged_conv3[2 * 8 +: 8]
        };
        bottom_right_rgb = {
            staged_conv3[11 * 8 +: 8],
            staged_conv3[7 * 8 +: 8],
            staged_conv3[3 * 8 +: 8]
        };

        if (state == STATE_EMIT_TOP) begin
            rgb_data = top_phase ? top_right_rgb : top_left_rgb;
            rgb_row = lr_row * 2;
            rgb_column = lr_column * 2 + top_phase;
        end else if (state == STATE_DRAIN_BOTTOM_LEFT) begin
            rgb_data = bottom_pair_read_data[23:0];
            rgb_row = lr_row * 2 + 1'b1;
            rgb_column = bottom_drain_column * 2;
        end else begin
            rgb_data = bottom_pair_read_data[47:24];
            rgb_row = lr_row * 2 + 1'b1;
            rgb_column = bottom_drain_column * 2 + 1'b1;
        end
    end

    always @(posedge clk) begin
        if (!reset_n) begin
            state <= STATE_IDLE;
            staged_conv3 <= 96'sd0;
            lr_row <= {LR_ROW_BITS{1'b0}};
            lr_column <= {LR_COLUMN_BITS{1'b0}};
            bottom_drain_column <= {LR_COLUMN_BITS{1'b0}};
            bottom_pair_read_data <= 48'sd0;
            top_phase <= 1'b0;
            accepted_final_lr_pixel <= 1'b0;
            frame_done <= 1'b0;
            protocol_error <= 1'b0;
        end else begin
            frame_done <= 1'b0;

            if (state == STATE_IDLE && conv3_valid) begin
                staged_conv3 <= conv3_values;
                bottom_pair_buffer[lr_column] <= {
                    conv3_values[11 * 8 +: 8],
                    conv3_values[7 * 8 +: 8],
                    conv3_values[3 * 8 +: 8],
                    conv3_values[10 * 8 +: 8],
                    conv3_values[6 * 8 +: 8],
                    conv3_values[2 * 8 +: 8]
                };
                accepted_final_lr_pixel <=
                    (lr_row == effective_image_height - 1'b1) &&
                    (lr_column == effective_image_width - 1'b1);
                if (conv3_last !=
                    ((lr_row == effective_image_height - 1'b1) &&
                     (lr_column == effective_image_width - 1'b1))) begin
                    protocol_error <= 1'b1;
                end
                top_phase <= 1'b0;
                if (top_selected) state <= STATE_EMIT_TOP;
                else if (lr_column == effective_image_width-1'b1) begin
                    bottom_drain_column <= 0;
                    state <= STATE_DRAIN_BOTTOM_READ;
                end else begin
                    lr_column <= lr_column+1'b1;
                    state <= STATE_IDLE;
                end
            end

            if (state == STATE_EMIT_TOP && rgb_ready) begin
                if (!top_phase) begin
                    top_phase <= 1'b1;
                end else begin
                    top_phase <= 1'b0;
                    if (lr_column == effective_image_width - 1'b1) begin
                        bottom_drain_column <= {LR_COLUMN_BITS{1'b0}};
                        state <= STATE_DRAIN_BOTTOM_READ;
                    end else begin
                        lr_column <= lr_column + 1'b1;
                        state <= STATE_IDLE;
                    end
                end
            end

            if (state == STATE_DRAIN_BOTTOM_READ) begin
                if (bottom_selected) begin
                    bottom_pair_read_data <= bottom_pair_buffer[bottom_drain_column];
                    state <= STATE_DRAIN_BOTTOM_LEFT;
                end else if (bottom_drain_column == effective_image_width-1'b1) begin
                    bottom_drain_column <= 0;
                    lr_column <= 0;
                    if (accepted_final_lr_pixel) begin
                        lr_row <= 0;
                        frame_done <= 1'b1;
                    end else lr_row <= lr_row+1'b1;
                    state <= STATE_IDLE;
                end else bottom_drain_column <= bottom_drain_column+1'b1;
            end

            if (state == STATE_DRAIN_BOTTOM_LEFT && rgb_ready) begin
                state <= STATE_DRAIN_BOTTOM_RIGHT;
            end

            if (state == STATE_DRAIN_BOTTOM_RIGHT && rgb_ready) begin
                if (bottom_drain_column == effective_image_width - 1'b1) begin
                    bottom_drain_column <= {LR_COLUMN_BITS{1'b0}};
                    lr_column <= {LR_COLUMN_BITS{1'b0}};
                    if (accepted_final_lr_pixel) begin
                        lr_row <= {LR_ROW_BITS{1'b0}};
                        frame_done <= 1'b1;
                    end else begin
                        lr_row <= lr_row + 1'b1;
                    end
                    state <= STATE_IDLE;
                end else begin
                    bottom_drain_column <= bottom_drain_column + 1'b1;
                    state <= STATE_DRAIN_BOTTOM_READ;
                end
            end
        end
    end
endmodule
