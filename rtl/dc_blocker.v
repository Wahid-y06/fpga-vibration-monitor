`timescale 1ns / 1ps
`default_nettype none

// First-order DC blocker:  y[n] = x[n] - x[n-1] + y[n-1] - (y[n-1] >>> K)
// Pole at 1 - 2^-K (K = 7 -> cut-off ~5 Hz at 4 kHz). The multiply by the
// pole is a shift, so no multiplier is needed. The 16-bit input is scaled
// by 2^SHIFT into the DW-bit datapath to give the filters fractional bits.
module dc_blocker #(
    parameter integer DW    = 24,
    parameter integer SHIFT = 7,
    parameter integer K     = 7
) (
    input  wire                 clk,
    input  wire                 rst,
    input  wire                 in_valid,
    input  wire signed [15:0]   in,
    output reg                  out_valid,
    output reg  signed [DW-1:0] out
);
    localparam integer IW = DW + 3;
    localparam signed [IW-1:0] MAX = (1 <<< (DW - 1)) - 1;
    localparam signed [IW-1:0] MIN = -(1 <<< (DW - 1));

    reg  signed [DW-1:0] x1, y1;
    wire signed [DW-1:0] x = {{(DW - 16 - SHIFT){in[15]}}, in, {SHIFT{1'b0}}};
    wire signed [IW-1:0] sum = x - x1 + y1 - (y1 >>> K);
    wire signed [DW-1:0] y = (sum > MAX) ? MAX[DW-1:0] :
                             (sum < MIN) ? MIN[DW-1:0] : sum[DW-1:0];

    always @(posedge clk) begin
        out_valid <= 1'b0;
        if (rst) begin
            x1  <= 0;
            y1  <= 0;
            out <= 0;
        end else if (in_valid) begin
            x1        <= x;
            y1        <= y;
            out       <= y;
            out_valid <= 1'b1;
        end
    end
endmodule

`default_nettype wire
