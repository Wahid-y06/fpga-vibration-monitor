`timescale 1ns / 1ps
`default_nettype none

// VGA diagnostic display, drawn on the fly (no frame buffer):
//
//   - status strip across the top, coloured by the overall alarm level
//   - one bar per channel (overall, 1x, 2x, harmonics, bearing), height on a
//     log scale (16 px per octave of energy), coloured by that channel's level
//   - yellow / red markers at each channel's warning / critical limits
//   - grid lines every 32 px (= 2 octaves), white baseline
//
// Log scale: L = log2(energy) with 3 fractional bits (0..255),
//            height = max(L - 64, 0) * 2  -> energies below 2^8 show no bar.
module vib_display #(
    parameter integer NCH = 5
) (
    input  wire              clk,
    input  wire              rst,
    input  wire              pix_ce,
    input  wire [NCH*32-1:0] energy,
    input  wire [NCH*32-1:0] warn_th,
    input  wire [NCH*32-1:0] crit_th,
    input  wire [NCH*2-1:0]  level,
    input  wire [1:0]        overall,
    output reg  [3:0]        vga_r,
    output reg  [3:0]        vga_g,
    output reg  [3:0]        vga_b,
    output reg               vga_hs,
    output reg               vga_vs,
    output reg               vga_de
);
    localparam integer X0 = 60, SP = 112, BW = 64, MK = 8;
    localparam integer BASE = 440;
    localparam integer STRIP_Y0 = 16, STRIP_Y1 = 40;

    wire [9:0] hc, vc;
    wire de, hs, vs;
    vga_timing u_t (.clk(clk), .rst(rst), .pix_ce(pix_ce),
                    .hc(hc), .vc(vc), .de(de), .hsync(hs), .vsync(vs));

    // ---------------------------------------------------------- log2 scale
    function [7:0] log2_q3(input [31:0] v);
        integer i;
        reg [4:0] msb;
        reg found;
        reg [31:0] norm;
        begin
            msb = 0;
            found = 0;
            for (i = 31; i >= 0; i = i - 1)
                if (!found && v[i]) begin
                    msb = i;
                    found = 1;
                end
            norm = (msb >= 3) ? (v >> (msb - 3)) : (v << (3 - msb));
            log2_q3 = found ? {msb, norm[2:0]} : 8'd0;
        end
    endfunction

    function [8:0] bar_px(input [31:0] v);
        reg [7:0] l;
        begin
            l = log2_q3(v);
            bar_px = (l < 8'd64) ? 9'd0 : {l - 8'd64, 1'b0};
        end
    endfunction

    reg [NCH*9-1:0] h_bar, h_warn, h_crit;     // channel c at [c*9 +: 9]
    integer k;
    always @(posedge clk) begin
        for (k = 0; k < NCH; k = k + 1) begin
            h_bar[k * 9 +: 9]  <= bar_px(energy[k * 32 +: 32]);
            h_warn[k * 9 +: 9] <= bar_px(warn_th[k * 32 +: 32]);
            h_crit[k * 9 +: 9] <= bar_px(crit_th[k * 32 +: 32]);
        end
    end

    // ------------------------------------------------------------- colours
    function [11:0] level_rgb(input [1:0] lv);
        case (lv)
            2'd0:    level_rgb = 12'h0B2;      // green
            2'd1:    level_rgb = 12'hFC0;      // yellow
            default: level_rgb = 12'hF11;      // red
        endcase
    endfunction

    localparam [11:0] C_BG = 12'h112, C_GRID = 12'h334, C_AXIS = 12'hCCC,
                      C_WARN = 12'hFD0, C_CRIT = 12'hF00;

    // ------------------------------------------------------------- render
    reg [11:0] rgb;
    reg        hit_bar, hit_warn, hit_crit;
    reg [1:0]  bar_lv;
    integer c;
    integer x0;
    always @* begin
        hit_bar = 1'b0;
        hit_warn = 1'b0;
        hit_crit = 1'b0;
        bar_lv = 2'd0;
        for (c = 0; c < NCH; c = c + 1) begin
            x0 = X0 + c * SP;
            if (hc >= x0 && hc < x0 + BW && vc < BASE && vc >= BASE - h_bar[c * 9 +: 9]) begin
                hit_bar = 1'b1;
                bar_lv  = level[c * 2 +: 2];
            end
            if (hc + MK >= x0 && hc < x0 + BW + MK) begin
                if (vc == BASE - h_crit[c * 9 +: 9] || vc == BASE - h_crit[c * 9 +: 9] - 1) hit_crit = 1'b1;
                if (vc == BASE - h_warn[c * 9 +: 9] || vc == BASE - h_warn[c * 9 +: 9] - 1) hit_warn = 1'b1;
            end
        end

        if (vc >= STRIP_Y0 && vc < STRIP_Y1 && hc >= X0 && hc < X0 + (NCH - 1) * SP + BW)
            rgb = level_rgb(overall);
        else if (hit_crit)
            rgb = C_CRIT;
        else if (hit_warn)
            rgb = C_WARN;
        else if (hit_bar)
            rgb = level_rgb(bar_lv);
        else if ((vc == BASE || vc == BASE + 1) && hc >= X0 - 20 && hc < X0 + (NCH - 1) * SP + BW + 20)
            rgb = C_AXIS;
        else if (vc > STRIP_Y1 && vc < BASE && ((BASE - vc) & 10'd31) == 0)
            rgb = C_GRID;
        else
            rgb = C_BG;
    end

    always @(posedge clk) begin
        if (rst) begin
            {vga_r, vga_g, vga_b} <= 12'h000;
            vga_hs <= 1'b1;
            vga_vs <= 1'b1;
            vga_de <= 1'b0;
        end else if (pix_ce) begin
            {vga_r, vga_g, vga_b} <= de ? rgb : 12'h000;
            vga_hs <= hs;
            vga_vs <= vs;
            vga_de <= de;
        end
    end
endmodule

`default_nettype wire
