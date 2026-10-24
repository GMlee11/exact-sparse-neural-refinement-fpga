`timescale 1ns/1ps

// One explicitly registered signed INT8 multiplier lane.
//
// The USE_DSP parameter lets larger spatial-parallel experiments trade one
// small 8x8 product into LUT fabric. That recovers DSP headroom for the Z7-20
// without changing the integer arithmetic. The default remains DSP-backed so
// older building-block routes keep their established resource contract.
module signed_int8_registered_multiplier #(
    parameter integer USE_DSP = 1
) (
    input  logic              clk,
    input  logic              reset_n,
    input  logic              input_valid,
    input  logic signed [7:0] sample,
    input  logic signed [7:0] weight,
    output logic signed [15:0] product
);
`ifdef UPSCALING_TARGET_GOWIN
    // Keep the Gowin-specific synthesis attributes and implementation in one
    // adapter.  The established Xilinx path below is unchanged when the Tang
    // build define is absent.
    gowin_signed_int8_registered_multiplier #(
        .USE_DSP(USE_DSP)
    ) gowin_multiplier (
        .clk(clk),
        .reset_n(reset_n),
        .input_valid(input_valid),
        .sample(sample),
        .weight(weight),
        .product(product)
    );
`else
    generate
        if (USE_DSP != 0) begin : dsp_product
            (* use_dsp = "yes" *) logic signed [15:0] product_register;

            assign product = product_register;

            always @(posedge clk) begin
                if (!reset_n) begin
                    product_register <= 16'sd0;
                end else if (input_valid) begin
                    product_register <= $signed(sample) * $signed(weight);
                end
            end
        end else begin : fabric_product
            (* use_dsp = "no" *) logic signed [15:0] product_register;

            assign product = product_register;

            always @(posedge clk) begin
                if (!reset_n) begin
                    product_register <= 16'sd0;
                end else if (input_valid) begin
                    product_register <= $signed(sample) * $signed(weight);
                end
            end
        end
    endgenerate
`endif
endmodule

// Four-stage, nine-lane signed multiplier and balanced reduction pipeline.
//
// Stage one registers all nine INT8 x INT8 products. Stage two registers five
// pair sums in fabric. Stage three registers three wider partial sums. Stage
// four completes the INT32 reduction and registers the channel sum. The extra
// stage is specifically for 150 MHz spatial-parallel routes, where the previous
// pair-sum-to-final-sum path narrowly missed timing.
module mac_array_3x3_pipelined #(
    parameter integer DSP_MULTIPLIER_LANES = 9
) (
    input  logic               clk,
    input  logic               reset_n,
    input  logic               input_valid,
    input  logic signed [7:0]  sample_window [0:8],
    input  logic signed [7:0]  weights [0:8],
    output logic               output_valid,
    output logic signed [31:0] channel_product_sum
);
    logic signed [15:0] products [0:8];
    logic product_valid;
    logic pair_valid;
    logic quad_valid;

    logic signed [31:0] extended_products [0:8];
    // Explicitly keep reduction additions out of DSP48 post-adders. Otherwise
    // Vivado 2020.2 converts the tree into a six-DSP combinational cascade.
    (* use_dsp = "no" *) logic signed [31:0] pair_sums [0:4];
    (* use_dsp = "no" *) logic signed [31:0] quad_sums [0:2];
    logic signed [31:0] octet_sum;
    logic signed [31:0] balanced_sum;
    integer lane;
    genvar multiplier_lane;

    // Nine named instances make the intended one-product-per-DSP architecture
    // visible in both hierarchical utilization and post-route timing reports.
    generate
        for (multiplier_lane = 0; multiplier_lane < 9;
             multiplier_lane = multiplier_lane + 1) begin : multiplier_lanes
            signed_int8_registered_multiplier #(
                .USE_DSP(
                    (multiplier_lane < DSP_MULTIPLIER_LANES) ? 1 : 0
                )
            ) multiplier (
                .clk(clk),
                .reset_n(reset_n),
                .input_valid(input_valid),
                .sample(sample_window[multiplier_lane]),
                .weight(weights[multiplier_lane]),
                .product(products[multiplier_lane])
            );
        end
    endgenerate

    // Sign extension feeds the registered pair-sum boundary.
    always @* begin
        for (lane = 0; lane < 9; lane = lane + 1) begin
            extended_products[lane] =
                {{16{products[lane][15]}}, products[lane]};
        end
    end

    // Only two adder levels remain after the registered quad-sum boundary.
    always @* begin
        octet_sum = quad_sums[0] + quad_sums[1];
        balanced_sum = octet_sum + quad_sums[2];
    end

    // Valid advances with the data through the reduction registers. Product
    // values are registered by the multiplier instances above.
    always @(posedge clk) begin
        if (!reset_n) begin
            product_valid <= 1'b0;
            pair_valid <= 1'b0;
            quad_valid <= 1'b0;
            output_valid <= 1'b0;
            channel_product_sum <= 32'sd0;
            for (lane = 0; lane < 5; lane = lane + 1) begin
                pair_sums[lane] <= 32'sd0;
            end
            for (lane = 0; lane < 3; lane = lane + 1) begin
                quad_sums[lane] <= 32'sd0;
            end
        end else begin
            product_valid <= input_valid;
            pair_valid <= product_valid;
            quad_valid <= pair_valid;
            output_valid <= quad_valid;

            if (product_valid) begin
                pair_sums[0] <= extended_products[0] + extended_products[1];
                pair_sums[1] <= extended_products[2] + extended_products[3];
                pair_sums[2] <= extended_products[4] + extended_products[5];
                pair_sums[3] <= extended_products[6] + extended_products[7];
                pair_sums[4] <= extended_products[8];
            end
            if (pair_valid) begin
                quad_sums[0] <= pair_sums[0] + pair_sums[1];
                quad_sums[1] <= pair_sums[2] + pair_sums[3];
                quad_sums[2] <= pair_sums[4];
            end
            if (quad_valid) begin
                channel_product_sum <= balanced_sum;
            end
        end
    end
endmodule
