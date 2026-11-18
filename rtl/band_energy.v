`timescale 1ns / 1ps
`default_nettype none

// Mean-square energy of NCH channels over blocks of 2^BLOCK_LOG2 samples.
//
// Each channel value is scaled back to input LSBs (>>> SHIFT), squared and
// accumulated; one shared multiplier processes the channels in turn. At the
// end of a block, energy = sum >> BLOCK_LOG2, saturated to 32 bits.
module band_energy #(
    parameter integer DW         = 24,
    parameter integer SHIFT      = 7,
    parameter integer NCH        = 5,
    parameter integer BLOCK_LOG2 = 8
) (
    input  wire                 clk,
    input  wire                 rst,
    input  wire                 in_valid,
    input  wire [NCH*DW-1:0]    in,             // channel c at [c*DW +: DW]
    output reg                  block_valid,
    output reg  [NCH*32-1:0]    energy,
    output wire                 busy
);
    localparam integer VW = DW - SHIFT;          // scaled value width
    localparam integer SW = 2 * VW + BLOCK_LOG2; // sum width

    reg [NCH*DW-1:0] latched;
    reg [SW-1:0]     sums [0:NCH-1];
    reg [2:0]        ch;
    reg              active;
    reg [BLOCK_LOG2-1:0] count;

    assign busy = active;

    wire signed [DW-1:0] cur    = latched[ch * DW +: DW];
    wire signed [VW-1:0] scaled = cur >>> SHIFT;
    wire        [2*VW-1:0] sq   = scaled * scaled;          // always >= 0

    function [31:0] sat32(input [SW-1:0] v);
        sat32 = (v >> BLOCK_LOG2) > 32'hFFFF_FFFF ? 32'hFFFF_FFFF : v >> BLOCK_LOG2;
    endfunction

    integer i;
    always @(posedge clk) begin
        block_valid <= 1'b0;
        if (rst) begin
            active <= 1'b0;
            ch     <= 3'd0;
            count  <= 0;
            energy <= 0;
            for (i = 0; i < NCH; i = i + 1) sums[i] <= 0;
        end else if (!active) begin
            if (in_valid) begin
                latched <= in;
                ch      <= 3'd0;
                active  <= 1'b1;
            end
        end else begin
            if (ch == NCH - 1) begin
                active <= 1'b0;
                count  <= count + 1'b1;
                if (&count) begin                   // last sample of the block
                    for (i = 0; i < NCH - 1; i = i + 1) begin
                        energy[i * 32 +: 32] <= sat32(sums[i]);
                        sums[i] <= 0;
                    end
                    energy[(NCH - 1) * 32 +: 32] <= sat32(sums[NCH - 1] + sq);
                    sums[NCH - 1] <= 0;
                    block_valid <= 1'b1;
                end else begin
                    sums[ch] <= sums[ch] + sq;
                end
            end else begin
                sums[ch] <= sums[ch] + sq;
                ch       <= ch + 3'd1;
            end
        end
    end
endmodule

`default_nettype wire
