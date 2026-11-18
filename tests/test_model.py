"""Tests for the Python reference model, filter design and generated files."""
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vibmodel.__main__ import write_demo_rom, write_params  # noqa: E402
from vibmodel.config import BANDS, BLOCK, CRIT, FS, ROM_LEN, WARN  # noqa: E402
from vibmodel.design import band_coefficients, frequency_response, pole_radius  # noqa: E402
from vibmodel.reference import (CRITICAL, NORMAL, WARNING, AlarmChannel, DcBlocker,  # noqa: E402
                                FilterBank, Monitor, bar_height, log2_q3, sat)
from vibmodel.signals import generate, looped  # noqa: E402


def test_quantized_filters_are_stable_with_unity_peak_gain():
    for (_, f0, _), c in zip(BANDS, band_coefficients()):
        assert pole_radius(c) < 0.995
        assert frequency_response(c, np.array([f0]))[0] == pytest.approx(1.0, abs=0.01)


def test_each_band_rejects_the_other_band_centres():
    centres = [f0 for _, f0, _ in BANDS]
    for i, c in enumerate(band_coefficients()):
        for j, f in enumerate(centres):
            if abs(i - j) > 1:      # non-neighbouring bands
                assert frequency_response(c, np.array([f]))[0] < 0.2


def test_dc_blocker_removes_offset():
    dc = DcBlocker()
    out = [dc.step(5000) for _ in range(5000)]
    assert abs(out[-1]) < 2 ** 7               # < 1 input LSB after settling


def test_filter_bank_picks_out_its_band():
    t = np.arange(4 * ROM_LEN)
    tone = np.round(10000 * np.sin(2 * np.pi * BANDS[3][1] * t / FS)).astype(int)
    bank, dc = FilterBank(), DcBlocker()
    outs = np.array([bank.step(dc.step(int(s))) for s in tone])[ROM_LEN:]
    rms = np.sqrt(np.mean((outs / 2 ** 7) ** 2, axis=0))
    assert rms[3] == pytest.approx(10000 / np.sqrt(2), rel=0.05)
    assert rms[0] < 0.05 * rms[3]


def test_saturation_helper():
    assert sat(1 << 30, 24) == (1 << 23) - 1
    assert sat(-(1 << 30), 24) == -(1 << 23)


@pytest.mark.parametrize("scenario, expected", [
    ("healthy", [NORMAL] * 5),
    ("imbalance", [CRITICAL, CRITICAL, NORMAL, NORMAL, NORMAL]),
    ("misalignment", [WARNING, NORMAL, CRITICAL, NORMAL, NORMAL]),
    ("looseness", [WARNING, NORMAL, NORMAL, WARNING, NORMAL]),
    ("bearing", [NORMAL, NORMAL, NORMAL, NORMAL, CRITICAL]),
])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_each_fault_is_diagnosed_in_its_own_band(scenario, expected, seed):
    res = Monitor(list(WARN), list(CRIT)).run(looped(scenario, 12 * BLOCK, seed=seed))
    for r in res[3:]:
        assert r.levels == expected


def test_alarm_persistence_and_hysteresis():
    a = AlarmChannel(warn=1000, crit=3000, persist=2)
    assert [a.update(e) for e in (1100, 1100, 900, 870)] == [0, 1, 1, 0]


def test_log2_and_bar_height():
    assert log2_q3(0) == 0 and log2_q3(1) == 0
    assert log2_q3(8) == 24 and log2_q3(12) == 28
    assert bar_height(2 ** 8) == 0
    assert bar_height(2 ** 9) == 16                 # 16 px per octave
    assert bar_height(2 ** 31) == (31 * 8 - 64) * 2


def test_signals_loop_seamlessly():
    s = generate("imbalance")
    assert len(s) == ROM_LEN and s.dtype == np.int16
    assert np.array_equal(looped("imbalance", 2 * ROM_LEN)[ROM_LEN:], s)


def test_generated_files_are_up_to_date(tmp_path):
    write_params(tmp_path / "vib_params.vh")
    write_demo_rom(tmp_path / "vib_demo.hex")
    assert (tmp_path / "vib_params.vh").read_text() == (ROOT / "rtl" / "vib_params.vh").read_text(), \
        "run `python -m vibmodel generate`"
    assert (tmp_path / "vib_demo.hex").read_text() == (ROOT / "board" / "vib_demo.hex").read_text()


@pytest.mark.skipif(shutil.which("iverilog") is None and not Path("C:/iverilog/bin").exists(),
                    reason="Icarus Verilog not installed")
def test_board_wrapper_compiles_without_warnings(tmp_path):
    iverilog = shutil.which("iverilog") or "C:/iverilog/bin/iverilog.exe"
    sources = sorted((ROOT / "rtl").glob("*.v")) + [ROOT / "board" / "de10lite_top.v"]
    r = subprocess.run([iverilog, "-Wall", "-g2005", "-I", str(ROOT / "rtl"),
                        "-s", "de10lite_top", "-o", str(tmp_path / "a.out"),
                        *map(str, sources)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "warning" not in r.stderr.lower(), r.stderr
