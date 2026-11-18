"""Builds each RTL test bench with Icarus Verilog and runs its cocotb tests.

    python -m pytest              # everything
    WAVES=1 python -m pytest      # also dump waveforms (open with GTKWave)
"""
import os
import shutil
import sys
from pathlib import Path

import pytest
from cocotb_tools.runner import get_results, get_runner

ROOT = Path(__file__).resolve().parent.parent
RTL, TB = ROOT / "rtl", ROOT / "tb"
sys.path.insert(0, str(TB))
sys.path.insert(0, str(ROOT))

if shutil.which("iverilog") is None and Path("C:/iverilog/bin").exists():
    os.environ["PATH"] = "C:/iverilog/bin" + os.pathsep + os.environ["PATH"]

DATAPATH = [RTL / f for f in ("dc_blocker.v", "filter_bank.v", "band_energy.v",
                              "alarm_unit.v", "vga_timing.v", "vib_display.v",
                              "vibmon_top.v")]

CASES = {
    # toplevel: (sources, cocotb module)
    "tb_filters": (DATAPATH + [TB / "tb_filters.v"], "cocotb_filters"),
    "alarm_unit": ([RTL / "alarm_unit.v"], "cocotb_alarm"),
    "vibmon_top": (DATAPATH, "cocotb_top"),
    "tb_display": (DATAPATH + [TB / "tb_display.v"], "cocotb_display"),
}


@pytest.mark.skipif(shutil.which("iverilog") is None, reason="Icarus Verilog not installed")
@pytest.mark.parametrize("toplevel", list(CASES))
def test_rtl(toplevel):
    sources, module = CASES[toplevel]
    waves = os.environ.get("WAVES") == "1"
    build_dir = ROOT / "sim_build" / toplevel
    runner = get_runner("icarus")
    runner.build(sources=sources, includes=[RTL], hdl_toplevel=toplevel,
                 build_dir=build_dir, always=True, waves=waves,
                 build_args=["-Wall"], timescale=("1ns", "1ps"))
    results = runner.test(hdl_toplevel=toplevel, test_module=module,
                          build_dir=build_dir, test_dir=build_dir, waves=waves,
                          extra_env={"PYTHONPATH": os.pathsep.join([str(ROOT), str(TB)])})
    total, failed = get_results(results)
    assert total > 0, "no cocotb tests ran"
    assert failed == 0, f"{failed} of {total} cocotb tests failed for {toplevel}"
