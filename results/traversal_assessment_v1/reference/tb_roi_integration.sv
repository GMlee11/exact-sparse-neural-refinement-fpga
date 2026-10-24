`timescale 1ns/1ps
module tb_roi_integration;
 reg clk=0,reset_n=0;always #5 clk=~clk;
 reg [31:0] command=0,wdata=0;
 wire [31:0] rdata,status;
 reg [31:0] sdata=0;reg [3:0] skeep=15;reg svalid=0,slast=0;
 wire sready;wire [31:0] mdata;wire [3:0] mkeep;wire mvalid,mlast;reg mready=1;
 integer descriptor[0:4095];reg [31:0] inputs[0:1999999],outputs[0:1999999];
 integer mode;
 integer cases,base,case_no,regions,regno,srcbase,outbase,nin,nout,sent,got,cycles,totalcycles;
 integer masklo,maskhi,ox,oy,w,h,rmlo,rmhi,checksum,accepted_regions;
 reg [31:0] captured_checksum;
 paper2_roi_board_wrapper dut(.ACLK(clk),.ARESETN(reset_n),.config_command(command),.config_write_data(wdata),.config_read_data(rdata),.config_status(status),
 .S_AXIS_TDATA(sdata),.S_AXIS_TKEEP(skeep),.S_AXIS_TVALID(svalid),.S_AXIS_TLAST(slast),.S_AXIS_TREADY(sready),
 .M_AXIS_TDATA(mdata),.M_AXIS_TKEEP(mkeep),.M_AXIS_TVALID(mvalid),.M_AXIS_TLAST(mlast),.M_AXIS_TREADY(mready));
 task tick;begin @(posedge clk);#1;end endtask
 task wr(input [7:0] addr,input [31:0] value);
 begin @(negedge clk);wdata=value;command=addr;tick();@(negedge clk);command=32'h100|addr;tick();@(negedge clk);command=addr;tick();end endtask
 task rd(input [7:0] addr);begin @(negedge clk);command=addr<<16;tick();end endtask
 task failure_case(input integer kind);
 integer limit,wanted,packet_words;
 begin
  wr(3,4);wr(0,1);wr(1,0);wr(16,900+kind);wr(17,0);wr(18,kind==4?80:100000000);wr(3,9);
  wr(2,4221);wr(39,0);wr(40,67|(63<<16));wr(41,1);wr(42,0);wr(43,1);wr(3,24);
  @(negedge clk);svalid=1;sdata=32'h00554433;skeep=kind==0?7:15;slast=kind==1;
  limit=0;while(!sready && limit<1000)begin tick();limit=limit+1;end
  tick();@(negedge clk);svalid=0;slast=0;skeep=15;
  if(kind==3)begin
   // An overlong packet omits TLAST at the configured final word. Feed until
   // the checker rejects it, including ordinary partially produced output.
   packet_words=1;limit=0;
   while(!status[1] && limit<2000000)begin
    @(negedge clk);svalid=1;slast=packet_words==4221;
    @(posedge clk);if(sready)packet_words=packet_words+1;limit=limit+1;
   end
   @(negedge clk);svalid=0;slast=0;
  end
  if(kind==2)begin
   // Exercise cancellation after actual private output, not merely at start.
   limit=0;
   while(!mvalid && limit<2000000)begin
    @(negedge clk);svalid=1;sdata=32'h00554433;slast=0;
    tick();limit=limit+1;
   end
   @(negedge clk);svalid=0;if(!mvalid && limit>=2000000)$fatal(1,"NO_PRIVATE_OUTPUT_BEFORE_CANCEL");
  end
  if(kind==2)begin wr(3,10);wanted=3;end
  else if(kind==4)wanted=4;
  else wanted=5;
  limit=0;while(!status[1] && limit<1000)begin tick();limit=limit+1;end
  if(!status[1] || status[2] || status[7:5]!=wanted)$fatal(1,"AXI_FAILURE kind=%0d status=%h",kind,status);
  wr(3,4);if(status[4])$fatal(1,"AXI_PREPARE_NOT_CLEAN");
  // Empty successor proves ownership/status reuse without a global reset.
  wr(0,0);wr(18,1000);wr(3,9);repeat(5)tick();
  if(!status[2] || status[4])$fatal(1,"AXI_FAILURE_REUSE kind=%0d status=%h",kind,status);
  $display("AXI_FAILURE_PASS kind=%0d outcome=%0d",kind,wanted);
 end endtask
 initial begin
  $readmemh("integration_descriptors.mem",descriptor);$readmemh("integration_inputs.mem",inputs);$readmemh("integration_outputs.mem",outputs);
  repeat(5)tick();@(negedge clk);reset_n=1;tick();cases=descriptor[0];base=1;
  rd(8'h31);if(rdata!=0)$fatal(1,"ZERO_DEFAULT");
  for(mode=0;mode<2;mode=mode+1)begin
  base=1;wr(8'h31,mode);rd(8'h31);
  if(rdata[0]!==mode[0])$fatal(1,"ZERO_CONFIG_READBACK");
  failure_case(0);failure_case(1);failure_case(2);failure_case(3);failure_case(4);
  for(case_no=0;case_no<cases;case_no=case_no+1) begin
   masklo=descriptor[base];maskhi=descriptor[base+1];regions=descriptor[base+2];base=base+3;
   wr(3,4);wr(0,masklo);wr(1,maskhi);wr(16,case_no+101);wr(17,0);wr(18,100000000);
   wr(3,9);totalcycles=0;
   rd(8'h31);if(rdata[1:0]!=={mode[0],mode[0]})$fatal(1,"ZERO_REQUEST_LATCH");
   if(regions>0)begin
     wr(8'h31,!mode);rd(8'h31);
     if(rdata[1:0]!=={mode[0],mode[0]})$fatal(1,"ZERO_BUSY_WRITE_CHANGED");
   end
   for(regno=0;regno<regions;regno=regno+1)begin
    ox=descriptor[base];oy=descriptor[base+1];w=descriptor[base+2];h=descriptor[base+3];
    rmlo=descriptor[base+4];rmhi=descriptor[base+5];nin=descriptor[base+6];nout=descriptor[base+7];srcbase=descriptor[base+8];outbase=descriptor[base+9];base=base+10;
    if(!status[3])$fatal(1,"NOT_READY case=%0d region=%0d status=%h",case_no,regno,status);
    wr(2,nin);wr(39,ox|(oy<<16));wr(40,w|(h<<16));wr(41,rmlo);wr(42,rmhi);wr(43,regno==regions-1);
    wr(3,24);
    // Changing the next descriptor must not mutate an accepted region.
    wr(2,1);wr(39,123);wr(40,2);wr(41,0);wr(42,0);wr(16,4321);
    sent=0;got=0;cycles=0;captured_checksum=32'h811c9dc5;
    while((got<nout || !(status[3]||status[1])) && cycles<40000000)begin
      @(negedge clk);svalid=sent<nin && cycles%13!=2;sdata=inputs[srcbase+sent];slast=sent==nin-1;mready=cycles%17!=4 && cycles%17!=5;
      @(posedge clk);cycles=cycles+1;
      if(svalid&&sready)sent=sent+1;
      if(mvalid&&mready)begin
       if(got>=nout || mdata!==outputs[outbase+got] || mkeep!=15 || mlast!=(got==nout-1))
          $fatal(1,"AXI_BYTE_ORDER case=%0d region=%0d idx=%0d got=%h expected=%h last=%b",case_no,regno,got,mdata,outputs[outbase+got],mlast);
       captured_checksum={captured_checksum[26:0],captured_checksum[31:27]}^mdata;got=got+1;
      end
      if(status[4] || (status[1]&&!status[2]))$fatal(1,"TERMINAL_ERROR case=%0d region=%0d status=%h",case_no,regno,status);
      if(regno<regions-1 && status[2])$fatal(1,"PARTIAL_PUBLISHED");
      if(cycles%1000000==0)$display("AXI_PROGRESS case=%0d region=%0d cycles=%0d sent=%0d got=%0d",case_no,regno,cycles,sent,got);
    end
    @(negedge clk);svalid=0;slast=0;mready=1;
    if(got!=nout || sent!=nin)$fatal(1,"AXI_COUNT_TIMEOUT");
    rd(45);if(rdata!==captured_checksum)$fatal(1,"CHECKSUM_READBACK got=%h expected=%h",rdata,captured_checksum);
    rd(6);if(rdata!=nin)$fatal(1,"INPUT_READBACK");rd(8);if(rdata!=nout)$fatal(1,"OUTPUT_READBACK");
    totalcycles=totalcycles+cycles;
    $display("AXI_REGION_PASS case=%0d region=%0d cycles=%0d input_words=%0d output_words=%0d checksum=%h",case_no,regno,cycles,sent,got,captured_checksum);
   end
   repeat(4)tick();if(!status[2] || !status[1] || status[0])$fatal(1,"NOT_COMMITTED");
   rd(19);if(rdata!=case_no+101)$fatal(1,"SOURCE_ID");rd(46);if(rdata!=regions)$fatal(1,"REGION_COUNT");
   rd(5);$display("AXI_REQUEST_PASS case=%0d regions=%0d service_cycles=%0d execution_loop_cycles=%0d",case_no,regions,rdata,totalcycles);
  end
  $display("C07_MODE_PASS mode=%0d",mode);
  end
  $display("PAPER2_ROI_INTEGRATION_PASS");$finish;
 end
 initial begin #1000000000;$fatal(1,"INTEGRATION_WATCHDOG");end
endmodule

