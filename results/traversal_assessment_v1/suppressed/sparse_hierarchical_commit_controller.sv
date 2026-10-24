`timescale 1ns/1ps

// Deadline- and frame-safe publication controller for the persistent sparse
// ESPCN datapath. Residual DMA storage is private; commit_valid_latched is the
// only authorization for software to expose a completed frame.
module sparse_hierarchical_commit_controller (
    input  logic         clk,
    input  logic         reset_n,
    input  logic         start_pulse,
    input  logic         prepare_pulse,
    input  logic         cancel_pulse,
    input  logic         clear_counters_pulse,
    input  logic         deadline_enable,
    input  logic [31:0]  configured_frame_id,
    input  logic [31:0]  expected_compute_cycles,
    input  logic [31:0]  frame_budget_cycles,

    input  logic         input_axis_tvalid,
    input  logic         input_axis_tready,
    input  logic         output_axis_tvalid,
    input  logic         output_axis_tready,
    input  logic         core_activity_pulse,
    input  logic         core_frame_done,
    input  logic         core_protocol_error,

    output logic         core_reset_n,
    output logic         frame_active,
    output logic         input_seen,
    output logic         frame_done_latched,
    output logic         commit_valid_latched,
    output logic [2:0]   last_outcome,
    output logic [31:0]  committed_frame_id,
    output logic [31:0]  completed_frame_id,
    output logic [31:0]  frame_elapsed_cycles,
    output logic [31:0]  active_compute_cycles,
    output logic [31:0]  active_private_output_words,
    output logic [31:0]  frame_launch_count,
    output logic [31:0]  deadline_skip_count,
    output logic [31:0]  canceled_frame_count,
    output logic [31:0]  useful_commit_count,
    output logic [31:0]  late_discard_count,
    output logic [31:0]  commit_sequence,
    output logic [31:0]  total_compute_cycles,
    output logic [31:0]  input_stall_cycles,
    output logic [31:0]  output_stall_cycles,
    output logic [31:0]  committed_output_words,
    output logic [31:0]  discarded_private_output_words,
    output logic [31:0]  protocol_error_count,
    output logic         controller_protocol_error
);
    localparam logic [2:0] OUTCOME_RUNNING = 3'd0;
    localparam logic [2:0] OUTCOME_COMMITTED = 3'd1;
    localparam logic [2:0] OUTCOME_DEADLINE_SKIP = 3'd2;
    localparam logic [2:0] OUTCOME_CANCELED = 3'd3;
    localparam logic [2:0] OUTCOME_LATE_DISCARD = 3'd4;
    localparam logic [2:0] OUTCOME_PROTOCOL_ERROR = 3'd5;

    logic [31:0] active_frame_id;
    logic compute_seen;
    logic core_enabled;
    logic input_handshake;
    logic output_handshake;

    assign input_handshake = input_axis_tvalid && input_axis_tready;
    assign output_handshake = output_axis_tvalid && output_axis_tready;
    assign core_reset_n = reset_n && core_enabled;

    // A single sequential block owns all outcome and counter transitions. This
    // ensures each frame is attributed to exactly one terminal outcome.
    always_ff @(posedge clk) begin
        if (!reset_n) begin
            frame_active <= 1'b0;
            core_enabled <= 1'b0;
            input_seen <= 1'b0;
            compute_seen <= 1'b0;
            frame_done_latched <= 1'b0;
            commit_valid_latched <= 1'b0;
            last_outcome <= OUTCOME_RUNNING;
            active_frame_id <= 32'd0;
            committed_frame_id <= 32'hFFFFFFFF;
            completed_frame_id <= 32'hFFFFFFFF;
            frame_elapsed_cycles <= 32'd0;
            active_compute_cycles <= 32'd0;
            active_private_output_words <= 32'd0;
            frame_launch_count <= 32'd0;
            deadline_skip_count <= 32'd0;
            canceled_frame_count <= 32'd0;
            useful_commit_count <= 32'd0;
            late_discard_count <= 32'd0;
            commit_sequence <= 32'd0;
            total_compute_cycles <= 32'd0;
            input_stall_cycles <= 32'd0;
            output_stall_cycles <= 32'd0;
            committed_output_words <= 32'd0;
            discarded_private_output_words <= 32'd0;
            protocol_error_count <= 32'd0;
            controller_protocol_error <= 1'b0;
        end else begin
            // PREPARE is issued before reconfiguration. A completed core stays
            // alive for counter readback until this explicit reset boundary.
            if (prepare_pulse && !frame_active) begin
                core_enabled <= 1'b0;
                frame_done_latched <= 1'b0;
                commit_valid_latched <= 1'b0;
            end

            // Counter clearing never changes an active frame's safety state.
            if (clear_counters_pulse) begin
                frame_launch_count <= 32'd0;
                deadline_skip_count <= 32'd0;
                canceled_frame_count <= 32'd0;
                useful_commit_count <= 32'd0;
                late_discard_count <= 32'd0;
                total_compute_cycles <= 32'd0;
                input_stall_cycles <= 32'd0;
                output_stall_cycles <= 32'd0;
                committed_output_words <= 32'd0;
                discarded_private_output_words <= 32'd0;
                protocol_error_count <= 32'd0;
                controller_protocol_error <= 1'b0;
            end

            // A start captures all mutable command fields atomically. Starting
            // over an active frame is a protocol error, never an implicit abort.
            if (start_pulse) begin
                if (frame_active) begin
                    protocol_error_count <= protocol_error_count + 1'b1;
                    controller_protocol_error <= 1'b1;
                end else begin
                    active_frame_id <= configured_frame_id;
                    frame_launch_count <= frame_launch_count + 1'b1;
                    frame_elapsed_cycles <= 32'd0;
                    active_compute_cycles <= 32'd0;
                    active_private_output_words <= 32'd0;
                    input_seen <= 1'b0;
                    compute_seen <= 1'b0;
                    frame_done_latched <= 1'b0;
                    commit_valid_latched <= 1'b0;
                    last_outcome <= OUTCOME_RUNNING;

                    // Predicted work that cannot fit is rejected before either
                    // DMA channel or the neural core consumes data.
                    if (deadline_enable &&
                        (frame_budget_cycles == 0 ||
                         expected_compute_cycles > frame_budget_cycles)) begin
                        frame_active <= 1'b0;
                        core_enabled <= 1'b0;
                        frame_done_latched <= 1'b1;
                        completed_frame_id <= configured_frame_id;
                        last_outcome <= OUTCOME_DEADLINE_SKIP;
                        deadline_skip_count <= deadline_skip_count + 1'b1;
                    end else begin
                        frame_active <= 1'b1;
                        core_enabled <= 1'b1;
                    end
                end
            end else if (frame_active) begin
                frame_elapsed_cycles <= frame_elapsed_cycles + 1'b1;

                if (input_handshake)
                    input_seen <= 1'b1;
                if (core_activity_pulse)
                    compute_seen <= 1'b1;
                if (compute_seen || core_activity_pulse) begin
                    active_compute_cycles <= active_compute_cycles + 1'b1;
                    total_compute_cycles <= total_compute_cycles + 1'b1;
                end
                if (input_axis_tvalid && !input_axis_tready)
                    input_stall_cycles <= input_stall_cycles + 1'b1;
                if (output_axis_tvalid && !output_axis_tready)
                    output_stall_cycles <= output_stall_cycles + 1'b1;
                if (output_handshake)
                    active_private_output_words <=
                        active_private_output_words + 1'b1;

                // Explicit cancellation has precedence over completion. The
                // host resets any active DMA packet and keeps the base image.
                if (cancel_pulse) begin
                    frame_active <= 1'b0;
                    core_enabled <= 1'b0;
                    frame_done_latched <= 1'b1;
                    commit_valid_latched <= 1'b0;
                    completed_frame_id <= active_frame_id;
                    last_outcome <= OUTCOME_CANCELED;
                    canceled_frame_count <= canceled_frame_count + 1'b1;
                    discarded_private_output_words <=
                        discarded_private_output_words +
                        active_private_output_words + output_handshake;
                end else if (core_protocol_error) begin
                    frame_active <= 1'b0;
                    core_enabled <= 1'b0;
                    frame_done_latched <= 1'b1;
                    commit_valid_latched <= 1'b0;
                    completed_frame_id <= active_frame_id;
                    last_outcome <= OUTCOME_PROTOCOL_ERROR;
                    protocol_error_count <= protocol_error_count + 1'b1;
                    controller_protocol_error <= 1'b1;
                    discarded_private_output_words <=
                        discarded_private_output_words +
                        active_private_output_words + output_handshake;
                end else if (core_frame_done) begin
                    // Completion at the budget boundary is on time. The marker
                    // publishes every prior private output word atomically.
                    frame_active <= 1'b0;
                    // Keep the quiescent core enabled so its per-frame layer
                    // and traffic counters remain readable until PREPARE.
                    core_enabled <= 1'b1;
                    frame_done_latched <= 1'b1;
                    commit_valid_latched <= 1'b1;
                    committed_frame_id <= active_frame_id;
                    completed_frame_id <= active_frame_id;
                    last_outcome <= OUTCOME_COMMITTED;
                    useful_commit_count <= useful_commit_count + 1'b1;
                    commit_sequence <= commit_sequence + 1'b1;
                    committed_output_words <= committed_output_words +
                        active_private_output_words + output_handshake;
                end else if (deadline_enable &&
                             frame_elapsed_cycles >= frame_budget_cycles) begin
                    // Resetting core_reset_n terminates real compute. Partial
                    // private output remains invisible because no commit occurs.
                    frame_active <= 1'b0;
                    core_enabled <= 1'b0;
                    frame_done_latched <= 1'b1;
                    commit_valid_latched <= 1'b0;
                    completed_frame_id <= active_frame_id;
                    last_outcome <= OUTCOME_LATE_DISCARD;
                    late_discard_count <= late_discard_count + 1'b1;
                    discarded_private_output_words <=
                        discarded_private_output_words +
                        active_private_output_words + output_handshake;
                end
            end else if (cancel_pulse) begin
                // Canceling an idle engine is harmless but recorded as a bad
                // command so host-control bugs cannot disappear silently.
                protocol_error_count <= protocol_error_count + 1'b1;
                controller_protocol_error <= 1'b1;
            end
        end
    end
endmodule
