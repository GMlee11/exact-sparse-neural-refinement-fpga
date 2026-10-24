`timescale 1ns/1ps
// One request transaction may contain several conventional ROI traversals.
// This does not invent ROI execution; it preserves the existing publication
// contract across region resets and rejects overlap/missing support.
module paper2_roi_request_guard (
    input wire clk, reset_n,
    input wire request_start, prepare, cancel,
    input wire [63:0] request_mask,
    input wire [31:0] frame_id, expected_cycles, budget_cycles,
    input wire deadline_enable,
    input wire region_start,
    input wire [63:0] proposed_mask,
    input wire [9:0] proposed_x, proposed_width,
    input wire [8:0] proposed_y, proposed_height,
    input wire proposed_last,
    input wire input_valid, input_ready, output_valid, output_ready,
    input wire region_done, region_error,
    input wire [31:0] region_output_words,
    output wire active, done, commit,
    output wire [2:0] outcome,
    output wire [31:0] committed_id, elapsed, private_words,
    output wire region_ready, region_reset_n,
    output reg [63:0] active_region_mask,
    output reg [9:0] active_x, active_width,
    output reg [8:0] active_y, active_height,
    output reg [31:0] completed_regions,
    output wire protocol_error
);
    localparam WAIT_REGION=0, RESET_REGION=1, RUN_REGION=2;
    reg [1:0] state;
    reg [2:0] reset_count;
    reg [63:0] captured_mask, claimed_mask;
    reg region_is_last;
    reg request_done_pulse, fault;
    reg captured_deadline_enable;
    reg [31:0] captured_budget;
    wire controller_core_reset;
    wire controller_error;
    reg geometry_ok;
    wire accepted_start=request_start && !active;
    wire invalid_region_command=region_start && (!region_ready || !geometry_ok ||
        (proposed_mask & ~captured_mask)!=0 || (proposed_mask & claimed_mask)!=0 ||
        (proposed_last != ((claimed_mask|proposed_mask)==captured_mask)));
    wire completion_on_time=!captured_deadline_enable || elapsed<captured_budget;
    integer j, tx, ty, lo_x, lo_y, hi_x, hi_y;
    integer proposed_words, captured_words;

    // Constant tile boundaries let synthesis share comparisons. This conservative
    // validator may cost LUTs; timing/resource qualification is mandatory.
    always @* begin
        geometry_ok=proposed_mask!=0 && proposed_mask[63:60]==0 &&
            proposed_width!=0 && proposed_height!=0 &&
            ({1'b0,proposed_x}+proposed_width)<=640 &&
            ({1'b0,proposed_y}+proposed_height)<=360;
        proposed_words=0; captured_words=0;
        for(j=0;j<60;j=j+1) begin
            if(captured_mask[j]) captured_words=captured_words+15360;
            if(proposed_mask[j]) begin
                proposed_words=proposed_words+15360;
                tx=(j%10)*64;ty=(j/10)*60;
                lo_x=(tx>=3)?tx-3:0;lo_y=(ty>=3)?ty-3:0;
                hi_x=(tx+67<=640)?tx+67:640;
                hi_y=(ty+63<=360)?ty+63:360;
                if(proposed_x>lo_x || proposed_y>lo_y ||
                    ({1'b0,proposed_x}+proposed_width)<hi_x ||
                    ({1'b0,proposed_y}+proposed_height)<hi_y) geometry_ok=0;
            end
        end
    end

    assign region_ready=active && state==WAIT_REGION && captured_mask!=0 && !fault;
    assign region_reset_n=reset_n && controller_core_reset && state==RUN_REGION;
    assign protocol_error=fault || controller_error;

    reg [31:0] active_expected_words;
    always @(posedge clk) begin
        if(!reset_n) begin
            state<=WAIT_REGION;reset_count<=0;captured_mask<=0;claimed_mask<=0;
            region_is_last<=0;request_done_pulse<=0;fault<=0;
            active_region_mask<=0;active_x<=0;active_y<=0;
            active_width<=640;active_height<=360;active_expected_words<=0;
            completed_regions<=0;
            captured_deadline_enable<=0;captured_budget<=0;
        end else begin
            request_done_pulse<=0;
            if(prepare && !active) fault<=0;
            if(request_start && !active) begin
                captured_mask<=request_mask;claimed_mask<=0;state<=WAIT_REGION;
                completed_regions<=0;fault<=request_mask[63:60]!=0;
                captured_deadline_enable<=deadline_enable;captured_budget<=budget_cycles;
            end
            if(request_start && active) fault<=1;
            if(!active && !request_start) state<=WAIT_REGION;
            if(active && captured_mask==0 && state==WAIT_REGION && !fault)
                request_done_pulse<=1;
            if(region_start) begin
                if(invalid_region_command) begin
                    fault<=1;
                end else begin
                    active_region_mask<=proposed_mask;
                    claimed_mask<=claimed_mask|proposed_mask;
                    active_x<=proposed_x;active_y<=proposed_y;
                    active_width<=proposed_width;active_height<=proposed_height;
                    active_expected_words<=proposed_words;
                    region_is_last<=proposed_last;reset_count<=0;state<=RESET_REGION;
                end
            end
            if(active && state==RESET_REGION) begin
                if(reset_count==4) state<=RUN_REGION;
                else reset_count<=reset_count+1'b1;
            end
            if(active && state==RUN_REGION && region_error) fault<=1;
            if(active && state==RUN_REGION && region_done) begin
                if(region_output_words!=active_expected_words) fault<=1;
                else begin
                    completed_regions<=completed_regions+1'b1;
                    state<=WAIT_REGION;
                    if(region_is_last) begin
                        if(claimed_mask!=captured_mask || private_words!=captured_words)
                            fault<=1;
                        else request_done_pulse<=1;
                    end
                end
            end
        end
    end

    sparse_hierarchical_commit_controller controller (
        .clk(clk),.reset_n(reset_n),.start_pulse(accepted_start),.prepare_pulse(prepare),
        .cancel_pulse(cancel),.clear_counters_pulse(accepted_start || (prepare && !active)),
        .deadline_enable(accepted_start?deadline_enable:captured_deadline_enable),.configured_frame_id(frame_id),
        .expected_compute_cycles(expected_cycles),.frame_budget_cycles(accepted_start?budget_cycles:captured_budget),
        .input_axis_tvalid(input_valid),.input_axis_tready(input_ready),
        .output_axis_tvalid(output_valid),.output_axis_tready(output_ready),
        .core_activity_pulse(input_valid && input_ready),
        .core_frame_done(request_done_pulse && completion_on_time),
        .core_protocol_error(fault || invalid_region_command || (request_start && active) || (state==RUN_REGION && region_error)),
        .core_reset_n(controller_core_reset),.frame_active(active),
        .frame_done_latched(done),.commit_valid_latched(commit),.last_outcome(outcome),
        .committed_frame_id(committed_id),.frame_elapsed_cycles(elapsed),
        .active_private_output_words(private_words),.controller_protocol_error(controller_error));
endmodule
