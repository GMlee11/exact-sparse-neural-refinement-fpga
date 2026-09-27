`timescale 1ns/1ps

// Pipelined, resource-conscious serial-input-channel 3x3 convolution lane.
//
// One channel window may be accepted every cycle. DSP products, pair sums, and
// final reduction occupy three stages; channel accumulation and requantization
// add two more. Input markers, bias, and ReLU controls travel through matching
// registers so the added latency does not change the numerical policy.
module conv2d_3x3_multi_channel #(
    parameter integer RIGHT_SHIFT_BITS = 8,
    parameter integer DSP_MULTIPLIER_LANES = 9
) (
    input  logic               clk,
    input  logic               reset_n,
    input  logic               input_valid,
    output logic               input_ready,
    input  logic               input_first_channel,
    input  logic               input_last_channel,
    input  logic signed [7:0]  sample_window [0:8],
    input  logic signed [7:0]  weights [0:8],
    input  logic signed [31:0] bias,
    input  logic               apply_relu,
    input  logic [4:0]         right_shift_bits,
    output logic               partial_valid,
    output logic signed [31:0] partial_accumulator,
    output logic               output_valid,
    output logic signed [31:0] output_accumulator,
    output logic signed [7:0]  output_value,
    output logic               protocol_error
);
    logic input_transaction_active;
    logic input_protocol_violation;
    logic accepted_input_valid;

    logic marker_product_valid;
    logic marker_pair_valid;
    logic marker_quad_valid;
    logic marker_sum_valid;
    logic first_product_stage;
    logic first_pair_stage;
    logic first_quad_stage;
    logic last_product_stage;
    logic last_pair_stage;
    logic last_quad_stage;
    logic first_sum_stage;
    logic last_sum_stage;
    logic signed [31:0] bias_product_stage;
    logic signed [31:0] bias_pair_stage;
    logic signed [31:0] bias_quad_stage;
    logic signed [31:0] bias_sum_stage;
    logic relu_product_stage;
    logic relu_pair_stage;
    logic relu_quad_stage;
    logic relu_sum_stage;
    logic [4:0] shift_product_stage;
    logic [4:0] shift_pair_stage;
    logic [4:0] shift_quad_stage;
    logic [4:0] shift_sum_stage;

    logic channel_sum_valid;
    logic signed [31:0] channel_product_sum;
    logic signed [31:0] running_product_sum;
    logic signed [31:0] stored_bias;
    logic stored_apply_relu;
    logic [4:0] stored_right_shift_bits;
    logic signed [31:0] products_after_channel;
    logic signed [31:0] effective_bias;
    logic effective_apply_relu;
    logic [4:0] effective_right_shift_bits;

    logic final_stage_valid;
    logic signed [31:0] final_stage_accumulator;
    logic final_stage_apply_relu;
    logic [4:0] final_stage_right_shift_bits;

    assign input_ready = 1'b1;
    assign input_protocol_violation =
        input_valid &&
        ((!input_transaction_active && !input_first_channel) ||
         (input_transaction_active && input_first_channel));
    assign accepted_input_valid = input_valid && !input_protocol_violation;

    mac_array_3x3_pipelined #(
        .DSP_MULTIPLIER_LANES(DSP_MULTIPLIER_LANES)
    ) channel_mac (
        .clk(clk),
        .reset_n(reset_n),
        .input_valid(accepted_input_valid),
        .sample_window(sample_window),
        .weights(weights),
        .output_valid(channel_sum_valid),
        .channel_product_sum(channel_product_sum)
    );

    // These controls accompany the product and reduction registers inside the
    // MAC. A protocol violation clears both marker stages, thereby discarding
    // every unfinished channel already in flight before the next transaction.
    always @(posedge clk) begin
        if (!reset_n) begin
            input_transaction_active <= 1'b0;
            protocol_error <= 1'b0;
            marker_product_valid <= 1'b0;
            marker_pair_valid <= 1'b0;
            marker_quad_valid <= 1'b0;
            marker_sum_valid <= 1'b0;
            first_product_stage <= 1'b0;
            first_pair_stage <= 1'b0;
            first_quad_stage <= 1'b0;
            last_product_stage <= 1'b0;
            last_pair_stage <= 1'b0;
            last_quad_stage <= 1'b0;
            first_sum_stage <= 1'b0;
            last_sum_stage <= 1'b0;
            bias_product_stage <= 32'sd0;
            bias_pair_stage <= 32'sd0;
            bias_quad_stage <= 32'sd0;
            bias_sum_stage <= 32'sd0;
            relu_product_stage <= 1'b0;
            relu_pair_stage <= 1'b0;
            relu_quad_stage <= 1'b0;
            relu_sum_stage <= 1'b0;
            shift_product_stage <= RIGHT_SHIFT_BITS[4:0];
            shift_pair_stage <= RIGHT_SHIFT_BITS[4:0];
            shift_quad_stage <= RIGHT_SHIFT_BITS[4:0];
            shift_sum_stage <= RIGHT_SHIFT_BITS[4:0];
        end else begin
            protocol_error <= input_protocol_violation;

            if (input_protocol_violation) begin
                input_transaction_active <= 1'b0;
                marker_product_valid <= 1'b0;
                marker_pair_valid <= 1'b0;
                marker_quad_valid <= 1'b0;
                marker_sum_valid <= 1'b0;
            end else begin
                marker_product_valid <= accepted_input_valid;
                marker_pair_valid <= marker_product_valid;
                marker_quad_valid <= marker_pair_valid;
                marker_sum_valid <= marker_quad_valid;

                if (accepted_input_valid) begin
                    first_product_stage <= input_first_channel;
                    last_product_stage <= input_last_channel;
                    bias_product_stage <= bias;
                    relu_product_stage <= apply_relu;
                    shift_product_stage <= right_shift_bits;

                    if (input_last_channel) begin
                        input_transaction_active <= 1'b0;
                    end else begin
                        input_transaction_active <= 1'b1;
                    end
                end

                if (marker_product_valid) begin
                    first_pair_stage <= first_product_stage;
                    last_pair_stage <= last_product_stage;
                    bias_pair_stage <= bias_product_stage;
                    relu_pair_stage <= relu_product_stage;
                    shift_pair_stage <= shift_product_stage;
                end

                if (marker_pair_valid) begin
                    first_quad_stage <= first_pair_stage;
                    last_quad_stage <= last_pair_stage;
                    bias_quad_stage <= bias_pair_stage;
                    relu_quad_stage <= relu_pair_stage;
                    shift_quad_stage <= shift_pair_stage;
                end

                if (marker_quad_valid) begin
                    first_sum_stage <= first_quad_stage;
                    last_sum_stage <= last_quad_stage;
                    bias_sum_stage <= bias_quad_stage;
                    relu_sum_stage <= relu_quad_stage;
                    shift_sum_stage <= shift_quad_stage;
                end
            end
        end
    end

    // The first channel starts a fresh pixel sum. Continuations use the prior
    // registered partial. This one-cycle feedback path is intentionally short.
    always @* begin
        if (first_sum_stage) begin
            products_after_channel = channel_product_sum;
            effective_bias = bias_sum_stage;
            effective_apply_relu = relu_sum_stage;
            effective_right_shift_bits = shift_sum_stage;
        end else begin
            products_after_channel = running_product_sum + channel_product_sum;
            effective_bias = stored_bias;
            effective_apply_relu = stored_apply_relu;
            effective_right_shift_bits = stored_right_shift_bits;
        end
    end

    // Accumulation publishes every channel partial. The final biased sum is
    // captured in a separate register so requantization cannot extend the DSP
    // and reduction path within the same clock period.
    always @(posedge clk) begin
        if (!reset_n) begin
            running_product_sum <= 32'sd0;
            stored_bias <= 32'sd0;
            stored_apply_relu <= 1'b0;
            stored_right_shift_bits <= RIGHT_SHIFT_BITS[4:0];
            partial_valid <= 1'b0;
            partial_accumulator <= 32'sd0;
            final_stage_valid <= 1'b0;
            final_stage_accumulator <= 32'sd0;
            final_stage_apply_relu <= 1'b0;
            final_stage_right_shift_bits <= RIGHT_SHIFT_BITS[4:0];
        end else begin
            partial_valid <= 1'b0;
            final_stage_valid <= 1'b0;

            if (input_protocol_violation) begin
                running_product_sum <= 32'sd0;
            end else if (channel_sum_valid && marker_sum_valid) begin
                partial_valid <= 1'b1;
                partial_accumulator <= products_after_channel;
                running_product_sum <= products_after_channel;

                if (first_sum_stage) begin
                    stored_bias <= bias_sum_stage;
                    stored_apply_relu <= relu_sum_stage;
                    stored_right_shift_bits <= shift_sum_stage;
                end

                if (last_sum_stage) begin
                    final_stage_valid <= 1'b1;
                    final_stage_accumulator <= products_after_channel + effective_bias;
                    final_stage_apply_relu <= effective_apply_relu;
                    final_stage_right_shift_bits <= effective_right_shift_bits;
                end
            end
        end
    end

    // Requantization uses separate rounding and saturation registers. This adds
    // one result-latency cycle while preserving the accumulator and INT8 policy.
    relu_clamp_pipelined #(
        .RIGHT_SHIFT_BITS(RIGHT_SHIFT_BITS)
    ) final_requantizer (
        .clk(clk),
        .reset_n(reset_n),
        .input_valid(final_stage_valid),
        .accumulator(final_stage_accumulator),
        .apply_relu(final_stage_apply_relu),
        .right_shift_bits(final_stage_right_shift_bits),
        .output_valid(output_valid),
        .output_accumulator(output_accumulator),
        .output_value(output_value)
    );
endmodule
