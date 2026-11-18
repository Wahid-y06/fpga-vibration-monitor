`timescale 1ns / 1ps
`default_nettype none

// Test wrapper: VGA display at one pixel per clock, plus a simulation-only
// dumper that writes the first full frame to frame.ppm.
module tb_display (
    input  wire         clk,
    input  wire         rst,
    input  wire         dump_en,
    input  wire [159:0] energy,
    input  wire [159:0] warn_th,
    input  wire [159:0] crit_th,
    input  wire [9:0]   level,
    input  wire [1:0]   overall,
    output wire [3:0]   vga_r,
    output wire [3:0]   vga_g,
    output wire [3:0]   vga_b,
    output wire         vga_hs,
    output wire         vga_vs,
    output wire         vga_de,
    output reg          done
);
    vib_display #(.NCH(5)) u_disp (
        .clk(clk), .rst(rst), .pix_ce(1'b1),
        .energy(energy), .warn_th(warn_th), .crit_th(crit_th),
        .level(level), .overall(overall),
        .vga_r(vga_r), .vga_g(vga_g), .vga_b(vga_b),
        .vga_hs(vga_hs), .vga_vs(vga_vs), .vga_de(vga_de));

    integer f, n;
    initial begin
        done = 1'b0;
        n = 0;
    end

    always @(posedge clk) begin
        if (dump_en && !rst && vga_de && !done) begin
            if (n == 0) begin
                f = $fopen("frame.ppm", "w");
                $fwrite(f, "P3\n640 480\n15\n");
            end
            $fwrite(f, "%0d %0d %0d\n", vga_r, vga_g, vga_b);
            n = n + 1;
            if (n == 640 * 480) begin
                $fclose(f);
                done <= 1'b1;
            end
        end
    end
endmodule

`default_nettype wire
