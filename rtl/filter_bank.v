`timescale 1ns / 1ps
`default_nettype none

// Bank of NB direct-form-I biquad band-pass filters sharing ONE multiplier.
//
// Samples arrive at 4 kHz but the clock is 50 MHz, so there are 12,500
// clocks per sample. Instead of 5 multipliers per band, a single pipelined
// MAC walks through all NB x 5 taps (7 clocks per band) - one DSP block for
// the whole filter bank.
//
//   acc = b0*x[n] + b1*x[n-1] + b2*x[n-2] + (-a1)*y[n-1] + (-a2)*y[n-2]
//   y   = saturate((acc + 2^(FRAC-1)) >>> FRAC)
//
// Coefficients are Q2.FRAC, feedback terms stored negated so every product
// is added. The input history x[n-1], x[n-2] is shared by all bands.
module filter_bank #(
    parameter integer DW     = 24,
    parameter integer CW     = 18,
    parameter integer FRAC   = 16,
    parameter integer NB     = 4,
    parameter [NB*5*CW-1:0] COEFS = 0
) (
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    in_valid,
    input  wire signed [DW-1:0]    in,
    output reg                     out_valid,
    output reg  [NB*DW-1:0]        out,        // band b at [b*DW +: DW]
    output wire                    busy
);
    localparam integer PW = DW + CW;           // product width
    localparam integer AW = PW + 4;            // accumulator width (5 terms)
    localparam signed [AW-1:0] ROUND = 1 <<< (FRAC - 1);
    localparam signed [AW-1:0] MAX = (1 <<< (DW - 1)) - 1;
    localparam signed [AW-1:0] MIN = -(1 <<< (DW - 1));
    localparam [1:0] S_IDLE = 2'd0, S_MAC = 2'd1, S_DRAIN = 2'd2, S_FIN = 2'd3;

    reg [1:0]  state;
    reg [2:0]  tap;
    reg [2:0]  band;

    reg signed [DW-1:0] x0, x1, x2;
    reg [NB*DW-1:0]     y1, y2;            // band b at [b*DW +: DW]

    reg signed [PW-1:0] prod;
    reg                 prod_v;
    reg signed [AW-1:0] acc;

    assign busy = (state != S_IDLE);

    // coefficient and operand for the current tap
    wire [5:0] cidx = band * 5 + tap;
    wire signed [CW-1:0] coef = COEFS[cidx * CW +: CW];
    reg  signed [DW-1:0] op;
    always @* begin
        case (tap)
            3'd0:    op = x0;
            3'd1:    op = x1;
            3'd2:    op = x2;
            3'd3:    op = y1[band * DW +: DW];
            default: op = y2[band * DW +: DW];
        endcase
    end

    wire signed [AW-1:0] rounded = (acc + ROUND) >>> FRAC;
    wire signed [DW-1:0] y_new = (rounded > MAX) ? MAX[DW-1:0] :
                                 (rounded < MIN) ? MIN[DW-1:0] : rounded[DW-1:0];

    always @(posedge clk) begin
        out_valid <= 1'b0;
        if (rst) begin
            state  <= S_IDLE;
            tap    <= 3'd0;
            band   <= 3'd0;
            x0     <= 0;
            x1     <= 0;
            x2     <= 0;
            prod   <= 0;
            prod_v <= 1'b0;
            acc    <= 0;
            out    <= 0;
            y1     <= 0;
            y2     <= 0;
        end else begin
            case (state)
                S_IDLE: if (in_valid) begin
                    x0     <= in;
                    band   <= 3'd0;
                    tap    <= 3'd0;
                    acc    <= 0;
                    prod_v <= 1'b0;
                    state  <= S_MAC;
                end

                S_MAC: begin                          // issue one product per clock
                    prod   <= op * coef;
                    prod_v <= 1'b1;
                    if (prod_v) acc <= acc + prod;
                    tap    <= tap + 3'd1;
                    if (tap == 3'd4) state <= S_DRAIN;
                end

                S_DRAIN: begin                        // add the last product
                    acc    <= acc + prod;
                    prod_v <= 1'b0;
                    state  <= S_FIN;
                end

                S_FIN: begin                          // round, saturate, update state
                    y2[band * DW +: DW] <= y1[band * DW +: DW];
                    y1[band * DW +: DW] <= y_new;
                    out[band * DW +: DW] <= y_new;
                    acc <= 0;
                    tap <= 3'd0;
                    if (band == NB - 1) begin
                        x2        <= x1;
                        x1        <= x0;
                        out_valid <= 1'b1;
                        state     <= S_IDLE;
                    end else begin
                        band  <= band + 3'd1;
                        state <= S_MAC;
                    end
                end
            endcase
        end
    end
endmodule

`default_nettype wire
