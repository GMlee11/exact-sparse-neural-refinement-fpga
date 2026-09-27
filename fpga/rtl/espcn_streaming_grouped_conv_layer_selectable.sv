`timescale 1ns/1ps

import espcn_fpga_student_weights_pkg::*;

// Select the frozen grouped-convolution engine or the two-context candidate.
// Keeping this choice at elaboration time means synthesis removes the unused
// branch completely, so the comparison does not add a runtime multiplexer or
// alter the external valid/ready contract.
module espcn_streaming_grouped_conv_layer_selectable #(
    parameter integer USE_TWO_CONTEXTS = 0,
    parameter integer LAYER_INDEX = 1,
    parameter integer INPUT_CHANNELS = 16,
    parameter integer OUTPUT_CHANNELS = 16,
    parameter integer OUTPUT_LANES = 4,
    parameter integer APPLY_RELU = 1,
    parameter integer RIGHT_SHIFT_BITS = TRAINED_DEFAULT_RIGHT_SHIFT_BITS,
    parameter integer DSP_MULTIPLIER_LANES = 9,
    parameter integer USE_SYNC_WEIGHT_ROM = 0,
    parameter integer COLUMN_BITS = 10,
    parameter integer ROW_BITS = 10
) (
    input  logic                                      clk,
    input  logic                                      reset_n,
    input  logic                                      weight_initialization_complete,
    input  logic                                      weight_initialization_write_enable,
    input  logic [7:0]                                weight_initialization_address,
    input  logic signed [71:0]                        weight_initialization_row,
    input  logic                                      window_valid,
    output logic                                      window_ready,
    input  logic                                      window_compute_enable,
    input  logic signed [INPUT_CHANNELS*72-1:0]       feature_windows,
    input  logic [ROW_BITS-1:0]                       window_row,
    input  logic [COLUMN_BITS-1:0]                    window_column,
    input  logic                                      window_last,
    output logic                                      feature_valid,
    input  logic                                      feature_ready,
    output logic signed [OUTPUT_CHANNELS*8-1:0]       feature_values,
    output logic [ROW_BITS-1:0]                       feature_row,
    output logic [COLUMN_BITS-1:0]                    feature_column,
    output logic                                      feature_last,
    output logic                                      protocol_error
);
    generate
        if (USE_TWO_CONTEXTS != 0) begin : use_two_contexts
            espcn_streaming_grouped_conv_layer_multicontext #(
                .LAYER_INDEX(LAYER_INDEX),
                .INPUT_CHANNELS(INPUT_CHANNELS),
                .OUTPUT_CHANNELS(OUTPUT_CHANNELS),
                .OUTPUT_LANES(OUTPUT_LANES),
                .APPLY_RELU(APPLY_RELU),
                .RIGHT_SHIFT_BITS(RIGHT_SHIFT_BITS),
                .DSP_MULTIPLIER_LANES(DSP_MULTIPLIER_LANES),
                .USE_SYNC_WEIGHT_ROM(USE_SYNC_WEIGHT_ROM),
                .COLUMN_BITS(COLUMN_BITS),
                .ROW_BITS(ROW_BITS)
            ) implementation (
                .clk(clk),
                .reset_n(reset_n),
                .weight_initialization_complete(weight_initialization_complete),
                .weight_initialization_write_enable(weight_initialization_write_enable),
                .weight_initialization_address(weight_initialization_address),
                .weight_initialization_row(weight_initialization_row),
                .window_valid(window_valid),
                .window_ready(window_ready),
                .window_compute_enable(window_compute_enable),
                .feature_windows(feature_windows),
                .window_row(window_row),
                .window_column(window_column),
                .window_last(window_last),
                .feature_valid(feature_valid),
                .feature_ready(feature_ready),
                .feature_values(feature_values),
                .feature_row(feature_row),
                .feature_column(feature_column),
                .feature_last(feature_last),
                .protocol_error(protocol_error)
            );
        end else begin : use_frozen_context
            espcn_streaming_grouped_conv_layer #(
                .LAYER_INDEX(LAYER_INDEX),
                .INPUT_CHANNELS(INPUT_CHANNELS),
                .OUTPUT_CHANNELS(OUTPUT_CHANNELS),
                .OUTPUT_LANES(OUTPUT_LANES),
                .APPLY_RELU(APPLY_RELU),
                .RIGHT_SHIFT_BITS(RIGHT_SHIFT_BITS),
                .DSP_MULTIPLIER_LANES(DSP_MULTIPLIER_LANES),
                .USE_SYNC_WEIGHT_ROM(USE_SYNC_WEIGHT_ROM),
                .COLUMN_BITS(COLUMN_BITS),
                .ROW_BITS(ROW_BITS)
            ) implementation (
                .clk(clk),
                .reset_n(reset_n),
                .weight_initialization_complete(weight_initialization_complete),
                .weight_initialization_write_enable(weight_initialization_write_enable),
                .weight_initialization_address(weight_initialization_address),
                .weight_initialization_row(weight_initialization_row),
                .window_valid(window_valid),
                .window_ready(window_ready),
                .window_compute_enable(window_compute_enable),
                .feature_windows(feature_windows),
                .window_row(window_row),
                .window_column(window_column),
                .window_last(window_last),
                .feature_valid(feature_valid),
                .feature_ready(feature_ready),
                .feature_values(feature_values),
                .feature_row(feature_row),
                .feature_column(feature_column),
                .feature_last(feature_last),
                .protocol_error(protocol_error)
            );
        end
    endgenerate
endmodule
