`timescale 1ns/1ps
// Experimental exact centered 3x3 window buffer. One packed-channel synchronous
// read stage replaces per-channel asynchronous row reads. Rows are NOT reset:
// row-valid coordinates suppress stale contents on every frame/region reuse.
module paper2_packed_bram_window #(
    parameter integer IMAGE_WIDTH=640, IMAGE_HEIGHT=360, INPUT_CHANNELS=24,
    parameter integer COLUMN_BITS=$clog2(IMAGE_WIDTH),
    parameter integer ROW_BITS=$clog2(IMAGE_HEIGHT),
    parameter integer GEOMETRY_COLUMN_BITS=$clog2(IMAGE_WIDTH+1),
    parameter integer GEOMETRY_ROW_BITS=$clog2(IMAGE_HEIGHT+1),
    parameter integer VECTOR_BITS=INPUT_CHANNELS*8,
    parameter MEMORY_STYLE="block"
) (
    input wire clk, reset_n,
    input wire [GEOMETRY_COLUMN_BITS-1:0] active_image_width,
    input wire [GEOMETRY_ROW_BITS-1:0] active_image_height,
    input wire feature_valid,
    output wire feature_ready,
    input wire [VECTOR_BITS-1:0] feature_values,
    output reg window_valid,
    input wire window_ready,
    output reg [INPUT_CHANNELS*72-1:0] feature_windows,
    output reg [ROW_BITS-1:0] window_row,
    output reg [COLUMN_BITS-1:0] window_column,
    output wire window_last,
    output reg protocol_error
);
    (* ram_style=MEMORY_STYLE *) reg [VECTOR_BITS-1:0] previous_row[0:IMAGE_WIDTH-1];
    (* ram_style=MEMORY_STYLE *) reg [VECTOR_BITS-1:0] two_rows_back[0:IMAGE_WIDTH-1];
    reg [VECTOR_BITS-1:0] previous_q, two_back_q, pending_values;
    reg [VECTOR_BITS-1:0] top_left,top_center,middle_left,middle_center,bottom_left,bottom_center;
    reg [GEOMETRY_ROW_BITS-1:0] scan_row,pending_row;
    reg [GEOMETRY_COLUMN_BITS-1:0] scan_column,pending_column;
    reg pending;
    wire advance=!window_valid || window_ready;
    wire actual_position=(scan_row<active_image_height && scan_column<active_image_width);
    wire launch=reset_n && advance && (!actual_position || feature_valid);
    wire consume=reset_n && advance && pending;
    wire pending_actual=pending_row<active_image_height && pending_column<active_image_width;
    wire [VECTOR_BITS-1:0] top=(pending_row>=2 && pending_column<active_image_width)?two_back_q:0;
    wire [VECTOR_BITS-1:0] middle=(pending_row>=1 && pending_column<active_image_width)?previous_q:0;
    wire [VECTOR_BITS-1:0] bottom=pending_actual?pending_values:0;
    assign feature_ready=reset_n && advance && actual_position;
    assign window_last=window_valid && window_row+1==active_image_height && window_column+1==active_image_width;
    integer channel;

    // Both memory outputs are registered. A write uses the prior synchronous
    // read result, not an asynchronous cross-memory read. Adjacent positions
    // access distinct addresses; explicit right padding separates row wraps.
    always @(posedge clk) begin
        if(launch && scan_column<active_image_width) begin
            previous_q<=previous_row[scan_column];
            two_back_q<=two_rows_back[scan_column];
        end
        if(consume && pending_actual) begin
            previous_row[pending_column]<=pending_values;
            two_rows_back[pending_column]<=previous_q;
        end
    end

    always @(posedge clk) begin
        if(!reset_n) begin
            scan_row<=0;scan_column<=0;pending_row<=0;pending_column<=0;
            pending<=0;pending_values<=0;window_valid<=0;feature_windows<=0;
            window_row<=0;window_column<=0;protocol_error<=0;
            top_left<=0;top_center<=0;middle_left<=0;middle_center<=0;bottom_left<=0;bottom_center<=0;
        end else begin
            if(active_image_width==0 || active_image_width>IMAGE_WIDTH ||
               active_image_height==0 || active_image_height>IMAGE_HEIGHT) protocol_error<=1;
            if(advance) begin
                window_valid<=0;
                pending<=launch;
                if(consume) begin
                    top_left<=top_center;top_center<=top;
                    middle_left<=middle_center;middle_center<=middle;
                    bottom_left<=bottom_center;bottom_center<=bottom;
                    // The padded first column starts a fresh horizontal state.
                    if(pending_column==0) begin
                        top_left<=0;middle_left<=0;bottom_left<=0;
                    end
                    if(pending_row>=1 && pending_column>=1) begin
                        for(channel=0;channel<INPUT_CHANNELS;channel=channel+1) begin
                            feature_windows[channel*72+:72]<={
                                bottom[channel*8+:8],bottom_center[channel*8+:8],bottom_left[channel*8+:8],
                                middle[channel*8+:8],middle_center[channel*8+:8],middle_left[channel*8+:8],
                                top[channel*8+:8],top_center[channel*8+:8],top_left[channel*8+:8]};
                        end
                        window_valid<=1;
                        window_row<=pending_row-1'b1;
                        window_column<=pending_column-1'b1;
                    end
                end
                if(launch) begin
                    pending_row<=scan_row;pending_column<=scan_column;pending_values<=feature_values;
                    if(scan_column==active_image_width) begin
                        scan_column<=0;
                        if(scan_row==active_image_height) scan_row<=0;
                        else scan_row<=scan_row+1'b1;
                    end else scan_column<=scan_column+1'b1;
                end
            end
        end
    end
endmodule
