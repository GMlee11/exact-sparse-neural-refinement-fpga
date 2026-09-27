`timescale 1ns/1ps

// Three-stage registered requantization for the multi-channel timing path.
//
// Stage one captures sign and magnitude, stage two computes the signed
// rounded-and-shifted value using the locked ties-away-from-zero policy, and
// stage three applies optional ReLU plus signed INT8 saturation. The original
// INT32 accumulator is delayed beside the numerical result so both public
// outputs remain aligned. The extra sign/magnitude register removes the
// accumulator-to-rounding carry chain that became the worst 150 MHz path once
// Conv2 and Conv3 were both spatial-parallel.
module relu_clamp_pipelined #(
    parameter integer RIGHT_SHIFT_BITS = 8
) (
    input  logic               clk,
    input  logic               reset_n,
    input  logic               input_valid,
    input  logic signed [31:0] accumulator,
    input  logic               apply_relu,
    input  logic [4:0]         right_shift_bits,
    output logic               output_valid,
    output logic signed [31:0] output_accumulator,
    output logic signed [7:0]  output_value
);
    logic signed [32:0] extended_accumulator;
    logic signed [32:0] selected_magnitude;
    logic signed [32:0] selected_half_step;
    logic signed [32:0] rounded_shifted_value;
    logic signed [7:0] saturated_value;

    logic sign_stage_valid;
    logic sign_stage_negative;
    logic signed [32:0] sign_stage_magnitude;
    logic signed [31:0] sign_stage_accumulator;
    logic sign_stage_apply_relu;
    logic [4:0] sign_stage_right_shift_bits;

    logic round_stage_valid;
    logic signed [32:0] round_stage_value;
    logic signed [31:0] round_stage_accumulator;
    logic round_stage_apply_relu;

    // Compute only sign and positive magnitude in front of the first register.
    // The actual add-half-step rounding is deliberately moved after this
    // boundary so the preceding convolution accumulator no longer drives the
    // wide rounding carry chain in the same cycle.
    always @* begin
        extended_accumulator = {accumulator[31], accumulator};
        selected_magnitude =
            (extended_accumulator >= 0) ?
            extended_accumulator : -extended_accumulator;
    end

    // Restoring the sign after adding half a quantization step makes exact
    // positive and negative half ties move away from zero without depending on
    // implementation-defined signed shifts.
    always @* begin
        selected_half_step =
            33'sd1 <<< (sign_stage_right_shift_bits - 1'b1);
        if (sign_stage_negative) begin
            rounded_shifted_value =
                -((sign_stage_magnitude + selected_half_step) >>>
                  sign_stage_right_shift_bits);
        end else begin
            rounded_shifted_value =
                (sign_stage_magnitude + selected_half_step) >>>
                sign_stage_right_shift_bits;
        end
    end

    // ReLU follows rounding, and saturation follows ReLU, matching the Python
    // policy and the original combinational `relu_clamp` operation order.
    always @* begin
        if (round_stage_apply_relu && round_stage_value < 0) begin
            saturated_value = 8'sd0;
        end else if (round_stage_value > 33'sd127) begin
            saturated_value = 8'sd127;
        end else if (round_stage_value < -33'sd128) begin
            saturated_value = -8'sd128;
        end else begin
            saturated_value = round_stage_value[7:0];
        end
    end

    // The second register boundary is deliberately separate from the rounding
    // register. Invalid cycles advance valid state without publishing new data.
    always @(posedge clk) begin
        if (!reset_n) begin
            sign_stage_valid <= 1'b0;
            sign_stage_negative <= 1'b0;
            sign_stage_magnitude <= 33'sd0;
            sign_stage_accumulator <= 32'sd0;
            sign_stage_apply_relu <= 1'b0;
            sign_stage_right_shift_bits <= RIGHT_SHIFT_BITS[4:0];
            round_stage_valid <= 1'b0;
            round_stage_value <= 33'sd0;
            round_stage_accumulator <= 32'sd0;
            round_stage_apply_relu <= 1'b0;
            output_valid <= 1'b0;
            output_accumulator <= 32'sd0;
            output_value <= 8'sd0;
        end else begin
            sign_stage_valid <= input_valid;
            round_stage_valid <= sign_stage_valid;
            output_valid <= round_stage_valid;

            if (input_valid) begin
                sign_stage_negative <= extended_accumulator < 0;
                sign_stage_magnitude <= selected_magnitude;
                sign_stage_accumulator <= accumulator;
                sign_stage_apply_relu <= apply_relu;
                sign_stage_right_shift_bits <= right_shift_bits;
            end
            if (sign_stage_valid) begin
                round_stage_value <= rounded_shifted_value;
                round_stage_accumulator <= sign_stage_accumulator;
                round_stage_apply_relu <= sign_stage_apply_relu;
            end
            if (round_stage_valid) begin
                output_accumulator <= round_stage_accumulator;
                output_value <= saturated_value;
            end
        end
    end
endmodule
