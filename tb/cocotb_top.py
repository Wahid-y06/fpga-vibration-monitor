"""End-to-end bit-exact check of vibmon_top against the Python model."""
import numpy as np

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

from vibmodel.config import BLOCK, CRIT, N_CH, PERSIST_BLOCKS, WARN
from vibmodel.reference import CRITICAL, NORMAL, WARNING, Monitor
from vibmodel.signals import looped

GAP = 64           # clocks per sample in simulation (real system: 12,500)


def pack(values, width):
    out = 0
    for i, v in enumerate(values):
        out |= v << (i * width)
    return out


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    dut.sample_valid.value = 0
    dut.sample.value = 0
    dut.warn_th.value = pack(WARN, 32)
    dut.crit_th.value = pack(CRIT, 32)
    dut.persist.value = PERSIST_BLOCKS
    dut.rst.value = 1
    await ClockCycles(dut.clk, 3)
    dut.rst.value = 0
    await ClockCycles(dut.clk, 2)


async def run_and_compare(dut, samples, model):
    results = []
    for i, s in enumerate(samples):
        dut.sample.value = int(s) & 0xFFFF
        dut.sample_valid.value = 1
        await RisingEdge(dut.clk)
        dut.sample_valid.value = 0
        await ClockCycles(dut.clk, GAP - 1)
        want = model.step(int(s))
        if want is None:
            continue
        raw_e, raw_l = int(dut.energy.value), int(dut.level.value)
        energies = [(raw_e >> (32 * c)) & 0xFFFFFFFF for c in range(N_CH)]
        levels = [(raw_l >> (2 * c)) & 3 for c in range(N_CH)]
        block = (i + 1) // BLOCK
        assert energies == want.energies, f"block {block}: {energies} != {want.energies}"
        assert levels == want.levels, f"block {block}: {levels} != {want.levels}"
        assert int(dut.overall.value) == want.overall
        results.append(want)
    assert not int(dut.overrun.value)
    return results


EXPECTED = {   # final alarm levels per channel: overall, 1x, 2x, harmonics, bearing
    "healthy":      [NORMAL, NORMAL, NORMAL, NORMAL, NORMAL],
    "imbalance":    [CRITICAL, CRITICAL, NORMAL, NORMAL, NORMAL],
    "misalignment": [WARNING, NORMAL, CRITICAL, NORMAL, NORMAL],
    "looseness":    [WARNING, NORMAL, NORMAL, WARNING, NORMAL],
    "bearing":      [NORMAL, NORMAL, NORMAL, NORMAL, CRITICAL],
}


def scenario_test(name):
    async def test(dut):
        await setup(dut)
        res = await run_and_compare(dut, looped(name, 6 * BLOCK),
                                    Monitor(list(WARN), list(CRIT)))
        assert res[-1].levels == EXPECTED[name]
    test.__name__ = f"diagnoses_{name}"
    test.__qualname__ = test.__name__
    return cocotb.test()(test)


diagnoses_healthy = scenario_test("healthy")
diagnoses_imbalance = scenario_test("imbalance")
diagnoses_misalignment = scenario_test("misalignment")
diagnoses_looseness = scenario_test("looseness")
diagnoses_bearing = scenario_test("bearing")


@cocotb.test()
async def fault_develops_then_clears(dut):
    """healthy -> imbalance -> healthy: alarm needs 2 blocks to raise, clears at once."""
    await setup(dut)
    sig = np.concatenate([looped("healthy", 3 * BLOCK), looped("imbalance", 5 * BLOCK),
                          looped("healthy", 4 * BLOCK)])
    res = await run_and_compare(dut, sig, Monitor(list(WARN), list(CRIT)))
    one_x = [r.levels[1] for r in res]
    assert one_x[:3] == [NORMAL] * 3
    assert CRITICAL in one_x[3:8]
    assert one_x[-1] == NORMAL


@cocotb.test()
async def overrun_flag_when_samples_too_fast(dut):
    await setup(dut)
    for _ in range(5):
        dut.sample.value = 1000
        dut.sample_valid.value = 1
        await RisingEdge(dut.clk)
        dut.sample_valid.value = 0
        await ClockCycles(dut.clk, 9)       # filter bank needs 29 clocks
    assert int(dut.overrun.value) == 1
