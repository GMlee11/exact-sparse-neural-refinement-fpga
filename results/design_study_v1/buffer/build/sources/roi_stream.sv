`timescale 1ns/1ps
// Compact AXI payloads surround the ordinary cropped runtime-geometry core.
// Only internal traversal changes. Input/output are still dependency pixels
// and selected residual words, not a transfer of the entire cropped image.
module paper2_roi_stream (
    input wire clk, reset_n,
    input wire [63:0] region_mask,
    input wire [9:0] origin_x, active_width,
    input wire [8:0] origin_y, active_height,
    input wire [31:0] expected_input_words,
    input wire [31:0] s_data,
    input wire [3:0] s_keep,
    input wire s_valid,s_last,
    output wire s_ready,
    output wire [31:0] m_data,
    output wire [3:0] m_keep,
    output wire m_valid,m_last,
    input wire m_ready,
    output reg done,error,
    output reg [31:0] input_words, output_words, zero_positions, discarded_outputs,
    output reg [31:0] output_checksum,
    output wire [31:0] conv1_active,conv2_active,conv3_active
);
    reg [9:0] x;
    reg [8:0] y;
    wire [9:0] global_x=x+origin_x;
    wire [8:0] global_y=y+origin_y;
    wire needs_input,needs_output;
    reg input_finished,core_finished,reported;
    wire pixel_ready;
    wire pixel_valid=reset_n && !input_finished && (!needs_input || s_valid);
    wire [23:0] pixel_data=needs_input?s_data[23:0]:24'd0;
    wire pixel_accept=pixel_valid && pixel_ready;
    wire out_valid,out_ready,core_done,core_error;
    wire [23:0] out_data;
    wire [9:0] out_row;
    wire [10:0] out_col;
    wire [9:0] output_global_x=(out_col>>1)+origin_x;
    wire [8:0] output_global_y=(out_row>>1)+origin_y;
    integer j;
    reg [31:0] expected_output_words;
    always @* begin
        expected_output_words=0;
        for(j=0;j<60;j=j+1) if(region_mask[j]) expected_output_words=expected_output_words+15360;
    end
    sparse_hierarchical_mask_lookup #(.IMAGE_WIDTH(640),.IMAGE_HEIGHT(360),.RADIUS(3)) input_support (
        .selected_tile_mask(region_mask),.row(global_y),.column(global_x),.selected(needs_input));
    sparse_hierarchical_mask_lookup #(.IMAGE_WIDTH(640),.IMAGE_HEIGHT(360),.RADIUS(0)) output_support (
        .selected_tile_mask(region_mask),.row(output_global_y),.column(output_global_x),.selected(needs_output));
    assign s_ready=reset_n && !input_finished && needs_input && pixel_ready;
    assign m_valid=reset_n && out_valid && needs_output;
    assign m_data={8'd0,out_data};
    assign m_keep=4'hf;
    assign m_last=m_valid && output_words+1==expected_output_words;
    assign out_ready=!needs_output || m_ready;

    paper2_origin_core #(.IMAGE_WIDTH(640),.IMAGE_HEIGHT(360),.RUNTIME_GEOMETRY(1),
        .CONV1_OUTPUT_LANES(2),.CONV2_OUTPUT_LANES(12),.CONV3_OUTPUT_LANES(6),
        .ENABLE_HIERARCHICAL_MASK(1)) core (
        .clk(clk),.reset_n(reset_n),.active_image_width(active_width),.active_image_height(active_height),
        .mask_origin_row(origin_y),.mask_origin_column(origin_x),.selected_tile_mask(region_mask),
        .pixel_valid(pixel_valid),.pixel_ready(pixel_ready),.pixel_rgb(pixel_data),
        .rgb_valid(out_valid),.rgb_ready(out_ready),.rgb_data(out_data),.rgb_row(out_row),.rgb_column(out_col),
        .frame_done(core_done),.protocol_error(core_error),
        .conv1_active_positions(conv1_active),.conv2_active_positions(conv2_active),.conv3_active_positions(conv3_active));

    always @(posedge clk) begin
        if(!reset_n) begin
            x<=0;y<=0;input_finished<=0;core_finished<=0;reported<=0;
            done<=0;error<=0;input_words<=0;output_words<=0;
            zero_positions<=0;discarded_outputs<=0;output_checksum<=32'h811c9dc5;
        end else begin
            done<=0;
            if(core_error) error<=1;
            if(pixel_accept) begin
                if(needs_input) begin
                    input_words<=input_words+1'b1;
                    if(s_keep!=4'hf || s_last!=(input_words+1==expected_input_words) ||
                       input_words>=expected_input_words) error<=1;
                end else zero_positions<=zero_positions+1'b1;
                if(x+1==active_width) begin
                    x<=0;
                    if(y+1==active_height) begin
                        input_finished<=1;
                        if(input_words+(needs_input?1:0)!=expected_input_words) error<=1;
                    end else y<=y+1'b1;
                end else x<=x+1'b1;
            end
            if(out_valid && out_ready && !needs_output) discarded_outputs<=discarded_outputs+1'b1;
            if(m_valid && m_ready) begin
                output_words<=output_words+1'b1;
                // Simple diagnostic rotate-XOR, not cryptographic integrity.
                output_checksum<={output_checksum[26:0],output_checksum[31:27]}^m_data;
                if(output_words>=expected_output_words) error<=1;
            end
            if(core_done) core_finished<=1;
            if(input_finished && core_finished && !reported) begin
                reported<=1;
                if(output_words!=expected_output_words) error<=1;
                else done<=1;
            end
        end
    end
endmodule
