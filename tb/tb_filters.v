`timescale 1ns / 1ps
`default_nettype none

// Test wrapper: DC blocker + filter bank with the generated coefficients,
// so each filter output can be compared sample-by-sample with the model.
module tb_filters (
    input  wire        clk,
    input  wire        rst,
    input  wire        sample_valid,
    input  wire [15:0] sample,
    output wire        dc_valid,
    output wire [23:0] dc_out,
    output wire        bank_valid,
    output wire [95:0] bands,
    output wire        busy
);
    `include "vib_params.vh"

    dc_blocker #(.DW(VIB_DW), .SHIFT(VIB_INPUT_SHIFT), .K(VIB_DC_K)) u_dc (
        .clk(clk), .rst(rst), .in_valid(sample_valid), .in(sample),
        .out_valid(dc_valid), .out(dc_out));

    filter_bank #(.DW(VIB_DW), .CW(VIB_COEF_W), .FRAC(VIB_COEF_FRAC), .NB(VIB_N_BANDS),
                  .COEFS(VIB_COEFS)) u_fb (
        .clk(clk), .rst(rst), .in_valid(dc_valid), .in(dc_out),
        .out_valid(bank_valid), .out(bands), .busy(busy));
endmodule

`default_nettype wire
