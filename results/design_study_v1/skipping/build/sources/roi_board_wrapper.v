`timescale 1ns/1ps
// New common-image GPIO/AXI shell. Existing sealed images remain unchanged.
module paper2_roi_board_wrapper (
 input wire ACLK,ARESETN,
 input wire [31:0] config_command,config_write_data,
 output reg [31:0] config_read_data,
 output wire [31:0] config_status,
 input wire [31:0] S_AXIS_TDATA,
 input wire [3:0] S_AXIS_TKEEP,
 input wire S_AXIS_TVALID,S_AXIS_TLAST,
 output wire S_AXIS_TREADY,
 output wire [31:0] M_AXIS_TDATA,
 output wire [3:0] M_AXIS_TKEEP,
 output wire M_AXIS_TVALID,M_AXIS_TLAST,
 input wire M_AXIS_TREADY
);
 reg zero_enable_config,zero_enable_active;
 reg [63:0] request_mask,proposed_mask;
 reg [31:0] input_count,frame_id,expected_cycles,budget;
 reg [9:0] px,pw;reg [8:0] py,ph;
 reg last,de;
 reg old_strobe,request_start,region_start,cancel,prepare;
 wire write_pulse=config_command[8]&&!old_strobe;
 wire active,done,commit,region_ready,region_reset_n,guard_error;
 wire [2:0] outcome;
 wire [31:0] committed_id,elapsed,private_words,regions;
 wire [63:0] amask;wire [9:0] ax,aw;wire [8:0] ay,ah;
 reg [31:0] active_input_count;
 wire region_done,region_error;
 wire [31:0] r_input,r_output,r_zero,r_discard,r_checksum,c1,c2,c3;
 reg [31:0] last_input,last_output,last_zero,last_discard,last_checksum,last_c1,last_c2,last_c3;
 reg [31:0] total_input;
 always @(posedge ACLK) begin
   if(!ARESETN) begin
     zero_enable_config<=0;zero_enable_active<=0;
     request_mask<=0;proposed_mask<=0;input_count<=0;frame_id<=0;expected_cycles<=0;budget<=0;
     px<=0;py<=0;pw<=640;ph<=360;last<=1;de<=0;old_strobe<=0;
     request_start<=0;region_start<=0;cancel<=0;prepare<=0;active_input_count<=0;
     last_input<=0;last_output<=0;last_zero<=0;last_discard<=0;last_checksum<=0;
     last_c1<=0;last_c2<=0;last_c3<=0;total_input<=0;
   end else begin
     old_strobe<=config_command[8];request_start<=0;region_start<=0;cancel<=0;prepare<=0;
     if(write_pulse) begin
       case(config_command[7:0])
        8'h00:request_mask[31:0]<=config_write_data;
        8'h01:request_mask[63:32]<=config_write_data;
        8'h02:input_count<=config_write_data;
        8'h03:begin request_start<=config_write_data[0];cancel<=config_write_data[1];prepare<=config_write_data[2];de<=config_write_data[3];region_start<=config_write_data[4];end
        8'h10:frame_id<=config_write_data;
        8'h11:expected_cycles<=config_write_data;
        8'h12:budget<=config_write_data;
        8'h27:begin px<=config_write_data[9:0];py<=config_write_data[24:16];end
        8'h28:begin pw<=config_write_data[9:0];ph<=config_write_data[24:16];end
        8'h29:proposed_mask[31:0]<=config_write_data;
        8'h2a:proposed_mask[63:32]<=config_write_data;
        8'h2b:last<=config_write_data[0];
        // Extension 0x31, default disabled. Busy writes ignored; request-latched.
        8'h31:if(!active) zero_enable_config<=config_write_data[0];
       endcase
     end
     if(request_start && !active) begin
        zero_enable_active<=zero_enable_config;
        total_input<=0;last_input<=0;last_output<=0;last_zero<=0;last_discard<=0;
        last_checksum<=0;last_c1<=0;last_c2<=0;last_c3<=0;
     end
     if(region_start && region_ready) active_input_count<=input_count;
     if(S_AXIS_TVALID && S_AXIS_TREADY) total_input<=total_input+1'b1;
     if(region_done) begin
        last_input<=r_input;last_output<=r_output;last_zero<=r_zero;last_discard<=r_discard;
        last_checksum<=r_checksum;last_c1<=c1;last_c2<=c2;last_c3<=c3;
     end
   end
 end
 assign config_status={24'd0,outcome,guard_error,region_ready,commit,done,active};
 always @* begin
  case(config_command[23:16])
   8'h04:config_read_data=config_status;
   8'h05:config_read_data=elapsed;
   8'h06:config_read_data=last_input;
   8'h07:config_read_data=last_zero;
   8'h08:config_read_data=last_output;
   8'h09:config_read_data=last_discard;
   8'h0a:config_read_data=last_c1;
   8'h0b:config_read_data=last_c2;
   8'h0c:config_read_data=last_c3;
   8'h13:config_read_data=committed_id;
   8'h2c:config_read_data=private_words;
   8'h2d:config_read_data=last_checksum;
   8'h2e:config_read_data=regions;
   8'h2f:config_read_data=total_input;
   8'h30:config_read_data=32'h524f4931;
   8'h31:config_read_data={30'd0,zero_enable_active,zero_enable_config};
   default:config_read_data=0;
  endcase
 end
 paper2_roi_request_guard guard (
   .clk(ACLK),.reset_n(ARESETN),.request_start(request_start),.prepare(prepare),.cancel(cancel),
   .request_mask(request_mask),.frame_id(frame_id),.expected_cycles(expected_cycles),.budget_cycles(budget),.deadline_enable(de),
   .region_start(region_start),.proposed_mask(proposed_mask),.proposed_x(px),.proposed_width(pw),.proposed_y(py),.proposed_height(ph),.proposed_last(last),
   .input_valid(S_AXIS_TVALID),.input_ready(S_AXIS_TREADY),.output_valid(M_AXIS_TVALID),.output_ready(M_AXIS_TREADY),
   .region_done(region_done),.region_error(region_error),.region_output_words(r_output),
   .active(active),.done(done),.commit(commit),.outcome(outcome),.committed_id(committed_id),.elapsed(elapsed),.private_words(private_words),
   .region_ready(region_ready),.region_reset_n(region_reset_n),.active_region_mask(amask),.active_x(ax),.active_width(aw),.active_y(ay),.active_height(ah),
   .completed_regions(regions),.protocol_error(guard_error));
 paper2_roi_stream stream (
   .clk(ACLK),.reset_n(region_reset_n),.zero_compaction_enable(zero_enable_active),.region_mask(amask),.origin_x(ax),.origin_y(ay),.active_width(aw),.active_height(ah),.expected_input_words(active_input_count),
   .s_data(S_AXIS_TDATA),.s_keep(S_AXIS_TKEEP),.s_valid(S_AXIS_TVALID),.s_last(S_AXIS_TLAST),.s_ready(S_AXIS_TREADY),
   .m_data(M_AXIS_TDATA),.m_keep(M_AXIS_TKEEP),.m_valid(M_AXIS_TVALID),.m_last(M_AXIS_TLAST),.m_ready(M_AXIS_TREADY),
   .done(region_done),.error(region_error),.input_words(r_input),.output_words(r_output),.zero_positions(r_zero),.discarded_outputs(r_discard),.output_checksum(r_checksum),
   .conv1_active(c1),.conv2_active(c2),.conv3_active(c3));
endmodule

