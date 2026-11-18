"""Sample-by-sample bit-exact check of dc_blocker + filter_bank."""
import numpy as np

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

from vibmodel.config import DW
from vibmodel.reference import DcBlocker, FilterBank
from vibmodel.signals import generate

GAP = 40           # clocks per sample (the filter bank needs 29)


def signed(value: int, bits: int) -> int:
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    dut.sample_valid.value = 0
    dut.sample.value = 0
    dut.rst.value = 1
    await ClockCycles(dut.clk, 3)
    dut.rst.value = 0
    await ClockCycles(dut.clk, 2)


async def check(dut, samples):
    dc, bank = DcBlocker(), FilterBank()
    for i, s in enumerate(samples):
        s = int(s)
        dut.sample.value = s & 0xFFFF
        dut.sample_valid.value = 1
        await RisingEdge(dut.clk)
        dut.sample_valid.value = 0
        await ClockCycles(dut.clk, GAP - 1)
        assert not int(dut.busy.value), "filter bank still busy"

        x = dc.step(s)
        ys = bank.step(x)
        got_dc = signed(int(dut.dc_out.value), DW)
        raw = int(dut.bands.value)
        got = [signed((raw >> (b * DW)) & ((1 << DW) - 1), DW) for b in range(len(ys))]
        assert got_dc == x, f"sample {i}: DC blocker {got_dc} != model {x}"
        assert got == ys, f"sample {i}: bands {got} != model {ys}"


@cocotb.test()
async def fault_signals_bit_exact(dut):
    await setup(dut)
    sig = np.concatenate([generate(n, 400) for n in
                          ("healthy", "imbalance", "misalignment", "looseness", "bearing")])
    await check(dut, sig)


@cocotb.test()
async def impulse_and_step_bit_exact(dut):
    await setup(dut)
    sig = [0] * 5 + [20000] + [0] * 300 + [15000] * 300 + [0] * 100
    await check(dut, sig)


@cocotb.test()
async def full_scale_saturation_bit_exact(dut):
    """Full-scale square waves near each band centre drive the filters into
    saturation; rounding and clipping must still match exactly."""
    await setup(dut)
    t = np.arange(1200)
    sig = np.where(np.sin(2 * np.pi * 29.3 * t / 4000) >= 0, 32767, -32768)
    sig[600:] = np.where(np.sin(2 * np.pi * 1200 * t[600:] / 4000) >= 0, 32767, -32768)
    await check(dut, sig)


@cocotb.test()
async def random_full_range_bit_exact(dut):
    await setup(dut)
    rng = np.random.default_rng(5)
    await check(dut, rng.integers(-32768, 32768, 800))
