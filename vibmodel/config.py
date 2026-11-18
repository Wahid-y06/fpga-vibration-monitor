"""System constants shared by the reference model, the coefficient generator
and the testbenches. The RTL receives the same values through
rtl/vib_params.vh, which is generated from this file."""

FS = 4000                 # sample rate, Hz
BLOCK_LOG2 = 8            # energy block = 256 samples = 64 ms
BLOCK = 1 << BLOCK_LOG2

SAMPLE_W = 16             # input sample width (signed)
INPUT_SHIFT = 7           # samples are scaled up by 2^7 inside the datapath
DW = 24                   # datapath width (signed)
COEF_W = 18               # biquad coefficient width (signed), fits an 18x18 DSP
COEF_FRAC = 16            # Q2.16 coefficients: range [-2, 2)
DC_K = 7                  # DC blocker pole = 1 - 2^-7 (cut-off ~5 Hz)

# Motor at 1758 rpm: 1x = 30 cycles per 4096 samples, so demo ROM loops are seamless
ROM_LEN = 4096
F_1X = 30 * FS / ROM_LEN  # 29.30 Hz

# (name, centre frequency Hz, Q)
BANDS = (
    ("1x", F_1X, 2.0),            # imbalance
    ("2x", 2 * F_1X, 4.0),        # misalignment
    ("harmonics", 200.0, 1.2),    # mechanical looseness (3x..12x)
    ("bearing", 1200.0, 0.8),     # bearing defect resonance
)
CHANNELS = ("overall",) + tuple(b[0] for b in BANDS)
N_CH = len(CHANNELS)

ENERGY_W = 32
PERSIST_BLOCKS = 2        # escalation must persist this many blocks

# Absolute severity limits per channel (mean-square, input LSB^2), in the
# spirit of ISO 10816 zones: chosen with margin above the healthy baseline
# and above the leakage each band picks up from faults in other bands.
#              overall      1x         2x         harmonics  bearing
WARN = (6_000_000, 4_000_000, 2_000_000, 1_200_000, 400_000)
CRIT = (20_000_000, 12_000_000, 6_000_000, 8_000_000, 800_000)
