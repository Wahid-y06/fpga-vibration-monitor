`timescale 1ns / 1ps
`default_nettype none

// 640x480 @ 60 Hz VGA timing (800 x 525 total, negative syncs).
// Counters advance on pix_ce (25 MHz pixel rate from a 50 MHz clock).
module vga_timing (
    input  wire       clk,
    input  wire       rst,
    input  wire       pix_ce,
    output reg  [9:0] hc,
    output reg  [9:0] vc,
    output wire       de,
    output wire       hsync,
    output wire       vsync
);
    localparam integer H_VIS = 640, H_FP = 16, H_SYNC = 96, H_BP = 48;
    localparam integer V_VIS = 480, V_FP = 10, V_SYNC = 2,  V_BP = 33;
    localparam integer H_TOT = H_VIS + H_FP + H_SYNC + H_BP;   // 800
    localparam integer V_TOT = V_VIS + V_FP + V_SYNC + V_BP;   // 525

    always @(posedge clk) begin
        if (rst) begin
            hc <= 10'd0;
            vc <= 10'd0;
        end else if (pix_ce) begin
            if (hc == H_TOT - 1) begin
                hc <= 10'd0;
                vc <= (vc == V_TOT - 1) ? 10'd0 : vc + 10'd1;
            end else begin
                hc <= hc + 10'd1;
            end
        end
    end

    assign de    = (hc < H_VIS) && (vc < V_VIS);
    assign hsync = !((hc >= H_VIS + H_FP) && (hc < H_VIS + H_FP + H_SYNC));
    assign vsync = !((vc >= V_VIS + V_FP) && (vc < V_VIS + V_FP + V_SYNC));
endmodule

`default_nettype wire
