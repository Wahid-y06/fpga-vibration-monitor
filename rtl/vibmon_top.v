`timescale 1ns / 1ps
`default_nettype none

// FPGA vibration monitor.
//
//   sample (16-bit, 4 kHz) -> DC blocker -> 4-band biquad filter bank
//     -> block energy (overall + 4 bands) -> severity alarms -> VGA display
//
// The filter design, thresholds and widths come from vib_params.vh, which
// is generated from the Python reference model (python -m vibmodel generate).
module vibmon_top #(
    parameter integer CLK_DIV = 2,          // 50 MHz clock -> 25 MHz pixels
    parameter integer NCH     = 5
) (
    input  wire              clk,
    input  wire              rst,
    input  wire              sample_valid,
    input  wire [15:0]       sample,
    input  wire [NCH*32-1:0] warn_th,
    input  wire [NCH*32-1:0] crit_th,
    input  wire [3:0]        persist,
    output wire              block_valid,   // energies and levels updated
    output wire [NCH*32-1:0] energy,
    output wire [NCH*2-1:0]  level,
    output wire [1:0]        overall,
    output reg               overrun,       // sticky: sample arrived while busy
    output wire [3:0]        vga_r,
    output wire [3:0]        vga_g,
    output wire [3:0]        vga_b,
    output wire              vga_hs,
    output wire              vga_vs,
    output wire              vga_de
);
    `include "vib_params.vh"

    localparam integer DW = VIB_DW;

    wire               dc_valid;
    wire signed [DW-1:0] dc_out;
    dc_blocker #(.DW(DW), .SHIFT(VIB_INPUT_SHIFT), .K(VIB_DC_K)) u_dc (
        .clk(clk), .rst(rst), .in_valid(sample_valid), .in(sample),
        .out_valid(dc_valid), .out(dc_out));

    wire                     fb_valid, fb_busy;
    wire [VIB_N_BANDS*DW-1:0] bands;
    filter_bank #(.DW(DW), .CW(VIB_COEF_W), .FRAC(VIB_COEF_FRAC), .NB(VIB_N_BANDS),
                  .COEFS(VIB_COEFS)) u_fb (
        .clk(clk), .rst(rst), .in_valid(dc_valid), .in(dc_out),
        .out_valid(fb_valid), .out(bands), .busy(fb_busy));

    wire        en_valid, en_busy;
    band_energy #(.DW(DW), .SHIFT(VIB_INPUT_SHIFT), .NCH(NCH), .BLOCK_LOG2(8)) u_en (
        .clk(clk), .rst(rst), .in_valid(fb_valid), .in({bands, dc_out}),
        .block_valid(en_valid), .energy(energy), .busy(en_busy));

    alarm_unit #(.NCH(NCH)) u_al (
        .clk(clk), .rst(rst), .block_valid(en_valid), .energy(energy),
        .warn_th(warn_th), .crit_th(crit_th), .persist(persist),
        .level(level), .overall(overall), .level_valid(block_valid));

    always @(posedge clk) begin
        if (rst)
            overrun <= 1'b0;
        else if (sample_valid && (dc_valid || fb_busy || fb_valid || en_busy))
            overrun <= 1'b1;
    end

    // pixel clock enable
    reg pix_ce;
    generate
        if (CLK_DIV == 1) begin : g_ce1
            always @* pix_ce = 1'b1;
        end else begin : g_ce2
            always @(posedge clk) pix_ce <= rst ? 1'b0 : !pix_ce;
        end
    endgenerate

    vib_display #(.NCH(NCH)) u_disp (
        .clk(clk), .rst(rst), .pix_ce(pix_ce),
        .energy(energy), .warn_th(warn_th), .crit_th(crit_th),
        .level(level), .overall(overall),
        .vga_r(vga_r), .vga_g(vga_g), .vga_b(vga_b),
        .vga_hs(vga_hs), .vga_vs(vga_vs), .vga_de(vga_de));
endmodule

`default_nettype wire
