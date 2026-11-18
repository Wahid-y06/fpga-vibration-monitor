"""Randomised bit-exact check of alarm_unit (hysteresis + persistence)."""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

from vibmodel.reference import AlarmChannel

N = 5
WARN = [1000, 5000, 20000, 100000, 2_000_000]
CRIT = [3000, 9000, 60000, 400000, 2_100_000]


def pack(values, width):
    out = 0
    for i, v in enumerate(values):
        out |= (v & ((1 << width) - 1)) << (i * width)
    return out


async def setup(dut, persist):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    dut.block_valid.value = 0
    dut.energy.value = 0
    dut.warn_th.value = pack(WARN, 32)
    dut.crit_th.value = pack(CRIT, 32)
    dut.persist.value = persist
    dut.rst.value = 1
    await ClockCycles(dut.clk, 3)
    dut.rst.value = 0
    await ClockCycles(dut.clk, 2)


async def block(dut, energies):
    dut.energy.value = pack(energies, 32)
    dut.block_valid.value = 1
    await RisingEdge(dut.clk)
    dut.block_valid.value = 0
    await ClockCycles(dut.clk, 2)
    raw = int(dut.level.value)
    return [(raw >> (2 * c)) & 3 for c in range(N)], int(dut.overall.value)


@cocotb.test()
async def random_walk_matches_model(dut):
    rng = random.Random(11)
    for persist in (0, 1, 2, 3):
        await setup(dut, persist)
        model = [AlarmChannel(w, c, persist) for w, c in zip(WARN, CRIT)]
        e = [w // 2 for w in WARN]
        for step in range(300):
            # random walk around the limits, sometimes jumping
            for c in range(N):
                if rng.random() < 0.1:
                    e[c] = rng.randrange(0, 2 * CRIT[c])
                else:
                    e[c] = max(0, int(e[c] * rng.uniform(0.8, 1.25)) + rng.randrange(-50, 50))
            got, overall = await block(dut, e)
            want = [m.update(v) for m, v in zip(model, e)]
            assert got == want, f"persist={persist} step {step}: {got} != {want} (e={e})"
            assert overall == max(want)


@cocotb.test()
async def hysteresis_and_persistence_sequence(dut):
    """Channel 0: warn 1000 (clears below 875), crit 3000 (clears below 2625)."""
    await setup(dut, persist=2)
    seq = [
        (1100, 0),   # above warn, 1st block: pending
        (1100, 1),   # 2nd consecutive block: WARNING
        (900, 1),    # below warn but above 875: still WARNING (hysteresis)
        (870, 0),    # below 875: cleared immediately
        (3500, 0),   # pending
        (500, 0),    # dropped: pending reset
        (3500, 0),   # pending again
        (3500, 2),   # CRITICAL after 2 blocks
        (2700, 2),   # above 2625: stays CRITICAL
        (2600, 1),   # below 2625: de-escalates to WARNING at once
    ]
    for energy, expected in seq:
        got, _ = await block(dut, [energy, 0, 0, 0, 0])
        assert got[0] == expected, f"energy {energy}: level {got[0]} != {expected}"
