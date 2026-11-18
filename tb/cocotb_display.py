"""VGA display: sync timing, and a full frame compared pixel-by-pixel with
the Python renderer (vibmodel/display.py)."""
import os
from pathlib import Path

import numpy as np

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge, First, RisingEdge
from cocotb.utils import get_sim_time

from vibmodel.config import BLOCK, CRIT, WARN
from vibmodel.display import read_ppm, render, to_png
from vibmodel.reference import Monitor
from vibmodel.signals import looped

CLK_NS = 40     # one pixel per clock: 25 MHz


def pack(values, width):
    out = 0
    for i, v in enumerate(values):
        out |= v << (i * width)
    return out


def bearing_fault_state():
    """Display inputs taken from the model after a bearing-fault recording."""
    return Monitor(list(WARN), list(CRIT)).run(looped("bearing", 6 * BLOCK))[-1]


async def setup(dut, state):
    cocotb.start_soon(Clock(dut.clk, CLK_NS, unit="ns").start())
    dut.energy.value = pack(state.energies, 32)
    dut.warn_th.value = pack(WARN, 32)
    dut.crit_th.value = pack(CRIT, 32)
    dut.level.value = pack(state.levels, 2)
    dut.overall.value = state.overall
    dut.dump_en.value = 0
    dut.rst.value = 1
    await ClockCycles(dut.clk, 3)


@cocotb.test()
async def sync_timing_640x480(dut):
    await setup(dut, bearing_fault_state())
    dut.rst.value = 0
    await FallingEdge(dut.vga_hs)
    t0 = get_sim_time("ns")
    await RisingEdge(dut.vga_hs)
    t1 = get_sim_time("ns")
    await FallingEdge(dut.vga_hs)
    t2 = get_sim_time("ns")
    assert (t1 - t0) / CLK_NS == 96, "hsync pulse must be 96 pixels"
    assert (t2 - t0) / CLK_NS == 800, "line must be 800 pixels"

    # track the end of the last visible line before vsync
    last_de_fall = None
    while True:
        de_fall, vs_fall = FallingEdge(dut.vga_de), FallingEdge(dut.vga_vs)
        fired = await First(de_fall, vs_fall)
        if fired is vs_fall:
            break
        last_de_fall = get_sim_time("ns")
    v0 = get_sim_time("ns")
    await RisingEdge(dut.vga_vs)
    v1 = get_sim_time("ns")
    assert (v1 - v0) / CLK_NS == 2 * 800, "vsync pulse must be 2 lines"
    # vsync starts 10 lines (front porch) after the last visible line ends
    assert (v0 - last_de_fall) / CLK_NS == 10 * 800 + (800 - 640)


@cocotb.test()
async def frame_matches_model_pixel_exact(dut):
    state = bearing_fault_state()
    await setup(dut, state)
    dut.dump_en.value = 1
    dut.rst.value = 0
    while not int(dut.done.value):
        await ClockCycles(dut.clk, 10_000)
    got = read_ppm("frame.ppm")
    want = render(state.energies, WARN, CRIT, state.levels, state.overall)
    diff = np.argwhere(np.any(got != want, axis=2))
    assert len(diff) == 0, f"{len(diff)} pixels differ, first at (y, x) = {tuple(diff[0])}"
    out = os.environ.get("VIB_FRAME_PNG")
    if out:
        to_png(got, Path(out))
