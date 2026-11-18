`timescale 1ns / 1ps
`default_nettype none

// Per-channel severity alarms, evaluated once per energy block.
//
//   level 0 normal, 1 warning, 2 critical
//
// Hysteresis: an active limit only clears once energy falls 12.5% below it
//   (limit - limit/8), so a value hovering at a limit cannot flicker.
// Persistence: escalation needs `persist` consecutive blocks above the
//   limit; de-escalation is immediate.
module alarm_unit #(
    parameter integer NCH = 5
) (
    input  wire              clk,
    input  wire              rst,
    input  wire              block_valid,
    input  wire [NCH*32-1:0] energy,
    input  wire [NCH*32-1:0] warn_th,
    input  wire [NCH*32-1:0] crit_th,
    input  wire [3:0]        persist,
    output reg  [NCH*2-1:0]  level,          // channel c at [c*2 +: 2]
    output wire [1:0]        overall,
    output reg               level_valid
);
    reg [3:0] pending [0:NCH-1];

    integer c;
    reg [31:0] e, w, k;
    reg [1:0]  cur, raw;
    always @(posedge clk) begin
        level_valid <= 1'b0;
        if (rst) begin
            level <= 0;
            for (c = 0; c < NCH; c = c + 1) pending[c] <= 4'd0;
        end else if (block_valid) begin
            level_valid <= 1'b1;
            for (c = 0; c < NCH; c = c + 1) begin
                e   = energy[c * 32 +: 32];
                cur = level[c * 2 +: 2];
                k   = crit_th[c * 32 +: 32] - ((cur >= 2'd2) ? (crit_th[c * 32 +: 32] >> 3) : 32'd0);
                w   = warn_th[c * 32 +: 32] - ((cur >= 2'd1) ? (warn_th[c * 32 +: 32] >> 3) : 32'd0);
                raw = (e >= k) ? 2'd2 : (e >= w) ? 2'd1 : 2'd0;
                if (raw <= cur) begin
                    pending[c]       <= 4'd0;
                    level[c * 2 +: 2] <= raw;
                end else if (pending[c] + 4'd1 >= persist) begin
                    pending[c]       <= 4'd0;
                    level[c * 2 +: 2] <= raw;
                end else begin
                    pending[c] <= pending[c] + 4'd1;
                end
            end
        end
    end

    // highest level of any channel
    reg [1:0] max_l;
    integer j;
    always @* begin
        max_l = 2'd0;
        for (j = 0; j < NCH; j = j + 1)
            if (level[j * 2 +: 2] > max_l) max_l = level[j * 2 +: 2];
    end
    assign overall = max_l;
endmodule

`default_nettype wire
