`timescale 1ns/1ps

// Stallable signed-INT8 3x3 line buffer with centered zero padding.
//
// The older `line_buffer_3x3` emits one window whenever its internal scan reaches
// a valid output position, but it cannot wait for a slower downstream stage.
// This version adds a standard ready/valid boundary on the window output. When
// `window_valid` is high and `window_ready` is low, the buffer holds the current
// 3x3 window, row, and column, and it also deasserts `pixel_ready` so upstream
// raw pixels do not outrun the convolution lane.
module line_buffer_3x3_stallable #(
    parameter integer IMAGE_WIDTH = 640,
    parameter integer IMAGE_HEIGHT = 360,
    parameter integer RUNTIME_GEOMETRY = 0,
    parameter integer COLUMN_BITS =
        (IMAGE_WIDTH <= 1) ? 1 : $clog2(IMAGE_WIDTH),
    parameter integer ROW_BITS =
        (IMAGE_HEIGHT <= 1) ? 1 : $clog2(IMAGE_HEIGHT),
    parameter integer GEOMETRY_COLUMN_BITS =
        (IMAGE_WIDTH + 1 <= 2) ? 1 : $clog2(IMAGE_WIDTH + 1),
    parameter integer GEOMETRY_ROW_BITS =
        (IMAGE_HEIGHT + 1 <= 2) ? 1 : $clog2(IMAGE_HEIGHT + 1),
    parameter integer PAD_COLUMN_BITS =
        (IMAGE_WIDTH + 1 <= 2) ? 1 : $clog2(IMAGE_WIDTH + 1)
) (
    input  logic                          clk,
    input  logic                          reset_n,
    input  logic [GEOMETRY_COLUMN_BITS-1:0] active_image_width,
    input  logic [GEOMETRY_ROW_BITS-1:0] active_image_height,
    input  logic                          pixel_valid,
    output logic                          pixel_ready,
    input  logic signed [7:0]             pixel_value,
    output logic                          window_valid,
    input  logic                          window_ready,
    output wire [71:0]                    sample_window_flat,
    output logic [ROW_BITS-1:0]           output_row,
    output logic [COLUMN_BITS-1:0]        output_column,
    output logic                          frame_done
);
    localparam logic [1:0] STATE_INPUT = 2'd0;
    localparam logic [1:0] STATE_RIGHT_PAD = 2'd1;
    localparam logic [1:0] STATE_BOTTOM_PAD = 2'd2;

    logic [1:0] state;
    logic [ROW_BITS-1:0] input_row;
    logic [COLUMN_BITS-1:0] input_column;
    logic [PAD_COLUMN_BITS-1:0] bottom_column;

`ifdef UPSCALING_TARGET_GOWIN
    // The verified centered-window schedule uses asynchronous row reads.  A
    // small Tang smoke frame therefore uses distributed storage; future
    // full-width Tang engines must insert a synchronous Gowin BSRAM boundary.
    (* ram_style = "distributed" *) logic signed [7:0]
`else
    (* ram_style = "block" *) logic signed [7:0]
`endif
        previous_row [0:IMAGE_WIDTH-1];
`ifdef UPSCALING_TARGET_GOWIN
    (* ram_style = "distributed" *) logic signed [7:0]
`else
    (* ram_style = "block" *) logic signed [7:0]
`endif
        two_rows_back [0:IMAGE_WIDTH-1];

    logic signed [7:0] top_left;
    logic signed [7:0] top_center;
    logic signed [7:0] middle_left;
    logic signed [7:0] middle_center;
    logic signed [7:0] bottom_left;
    logic signed [7:0] bottom_center;

    logic signed [7:0] vertical_top;
    logic signed [7:0] vertical_middle;
    logic signed [7:0] vertical_bottom;
    logic [71:0] sample_window_register;
    logic process_position;
    logic position_produces_window;
    logic can_advance;
    logic [GEOMETRY_COLUMN_BITS-1:0] effective_image_width;
    logic [GEOMETRY_ROW_BITS-1:0] effective_image_height;

    assign sample_window_flat = sample_window_register;
    assign can_advance = !window_valid || window_ready;
    assign effective_image_width = RUNTIME_GEOMETRY != 0 ?
        active_image_width : IMAGE_WIDTH;
    assign effective_image_height = RUNTIME_GEOMETRY != 0 ?
        active_image_height : IMAGE_HEIGHT;

    // The input stream is backpressured whenever the currently registered output
    // window has not been consumed. Padding positions use the same `can_advance`
    // guard, which prevents right/bottom padding windows from slipping past a
    // busy convolution stage.
    always @* begin
        pixel_ready = (state == STATE_INPUT) && can_advance;
        process_position = 1'b0;
        position_produces_window = 1'b0;
        vertical_top = 8'sd0;
        vertical_middle = 8'sd0;
        vertical_bottom = 8'sd0;

        if (can_advance && state == STATE_INPUT && pixel_valid) begin
            process_position = 1'b1;
            if (input_row >= 2) begin
                vertical_top = two_rows_back[input_column];
            end
            if (input_row >= 1) begin
                vertical_middle = previous_row[input_column];
            end
            vertical_bottom = pixel_value;
            position_produces_window =
                (input_row >= 1) && (input_column >= 1);
        end else if (can_advance && state == STATE_RIGHT_PAD) begin
            process_position = 1'b1;
            position_produces_window = (input_row >= 1);
        end else if (can_advance && state == STATE_BOTTOM_PAD) begin
            process_position = 1'b1;
            if (bottom_column < effective_image_width) begin
                if (effective_image_height >= 2) begin
                    vertical_top = two_rows_back[bottom_column];
                end
                vertical_middle = previous_row[bottom_column];
            end
            position_produces_window = (bottom_column >= 1);
        end
    end

    // Row memories are not reset so Vivado can infer block RAM. The row and
    // column counters suppress stale memory locations until real pixels have
    // overwritten them in the current frame.
    always @(posedge clk) begin
        if (!reset_n) begin
            state <= STATE_INPUT;
            input_row <= {ROW_BITS{1'b0}};
            input_column <= {COLUMN_BITS{1'b0}};
            bottom_column <= {PAD_COLUMN_BITS{1'b0}};
            top_left <= 8'sd0;
            top_center <= 8'sd0;
            middle_left <= 8'sd0;
            middle_center <= 8'sd0;
            bottom_left <= 8'sd0;
            bottom_center <= 8'sd0;
            window_valid <= 1'b0;
            output_row <= {ROW_BITS{1'b0}};
            output_column <= {COLUMN_BITS{1'b0}};
            frame_done <= 1'b0;
            sample_window_register <= 72'd0;
        end else begin
            frame_done <= 1'b0;

            if (can_advance) begin
                window_valid <= 1'b0;
            end

            if (process_position) begin
                top_left <= top_center;
                top_center <= vertical_top;
                middle_left <= middle_center;
                middle_center <= vertical_middle;
                bottom_left <= bottom_center;
                bottom_center <= vertical_bottom;

                if (position_produces_window) begin
                    sample_window_register[7:0] <= top_left;
                    sample_window_register[15:8] <= top_center;
                    sample_window_register[23:16] <= vertical_top;
                    sample_window_register[31:24] <= middle_left;
                    sample_window_register[39:32] <= middle_center;
                    sample_window_register[47:40] <= vertical_middle;
                    sample_window_register[55:48] <= bottom_left;
                    sample_window_register[63:56] <= bottom_center;
                    sample_window_register[71:64] <= vertical_bottom;
                    window_valid <= 1'b1;

                    if (state == STATE_BOTTOM_PAD) begin
                        output_row <= effective_image_height - 1'b1;
                        output_column <= bottom_column - 1'b1;
                    end else begin
                        output_row <= input_row - 1'b1;
                        if (state == STATE_RIGHT_PAD) begin
                            output_column <= effective_image_width - 1'b1;
                        end else begin
                            output_column <= input_column - 1'b1;
                        end
                    end
                end
            end

            if (can_advance && state == STATE_INPUT && pixel_valid) begin
                two_rows_back[input_column] <= previous_row[input_column];
                previous_row[input_column] <= pixel_value;

                if (input_column == effective_image_width - 1'b1) begin
                    state <= STATE_RIGHT_PAD;
                end else begin
                    input_column <= input_column + 1'b1;
                end
            end else if (can_advance && state == STATE_RIGHT_PAD) begin
                top_left <= 8'sd0;
                top_center <= 8'sd0;
                middle_left <= 8'sd0;
                middle_center <= 8'sd0;
                bottom_left <= 8'sd0;
                bottom_center <= 8'sd0;
                input_column <= {COLUMN_BITS{1'b0}};

                if (input_row == effective_image_height - 1'b1) begin
                    state <= STATE_BOTTOM_PAD;
                    bottom_column <= {PAD_COLUMN_BITS{1'b0}};
                end else begin
                    state <= STATE_INPUT;
                    input_row <= input_row + 1'b1;
                end
            end else if (can_advance && state == STATE_BOTTOM_PAD) begin
                if (bottom_column == effective_image_width) begin
                    state <= STATE_INPUT;
                    input_row <= {ROW_BITS{1'b0}};
                    input_column <= {COLUMN_BITS{1'b0}};
                    bottom_column <= {PAD_COLUMN_BITS{1'b0}};
                    top_left <= 8'sd0;
                    top_center <= 8'sd0;
                    middle_left <= 8'sd0;
                    middle_center <= 8'sd0;
                    bottom_left <= 8'sd0;
                    bottom_center <= 8'sd0;
                    frame_done <= 1'b1;
                end else begin
                    bottom_column <= bottom_column + 1'b1;
                end
            end
        end
    end
endmodule
