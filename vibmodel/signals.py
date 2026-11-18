"""Synthetic accelerometer signals for a motor running at F_1X.

Every periodic component uses a whole number of cycles per ROM_LEN samples,
so a ROM_LEN-sample loop (the board demo ROM) repeats seamlessly.
"""
from __future__ import annotations

import numpy as np

from .config import FS, ROM_LEN

BIN = FS / ROM_LEN                 # 0.977 Hz
K_1X = 30                          # 1x running speed = 30 bins


def _tone(n: int, k: int, amp: float, phase: float = 0.0) -> np.ndarray:
    t = np.arange(n)
    return amp * np.sin(2 * np.pi * k * t / ROM_LEN + phase)


def _base(n: int, rng: np.random.Generator) -> np.ndarray:
    """Healthy machine: small 1x/2x/3x plus broadband sensor noise."""
    return (_tone(n, K_1X, 1500) + _tone(n, 2 * K_1X, 300, 1.0)
            + _tone(n, 3 * K_1X, 150, 2.0) + rng.normal(0, 120, n))


def healthy(n: int, rng): return _base(n, rng)


def imbalance(n: int, rng):
    """Rotor imbalance: strong vibration at 1x running speed."""
    return _base(n, rng) + _tone(n, K_1X, 6000, 0.3)


def misalignment(n: int, rng):
    """Shaft misalignment: dominant 2x component."""
    return _base(n, rng) + _tone(n, 2 * K_1X, 4500, 0.7) + _tone(n, 3 * K_1X, 600)


def looseness(n: int, rng):
    """Mechanical looseness: many running-speed harmonics."""
    sig = _base(n, rng)
    for h in range(3, 13):
        sig += _tone(n, h * K_1X, 2000 / h ** 0.3, h * 0.9)
    return sig


def bearing(n: int, rng):
    """Outer-race defect: impacts every 32 samples (125 Hz) ringing a
    1500 Hz structural resonance with a 2 ms decay."""
    sig = _base(n, rng)
    t = np.arange(32)
    ring = 6000 * np.exp(-t / (0.002 * FS)) * np.sin(2 * np.pi * 1500 * t / FS)
    pulses = np.zeros(n)
    pulses[::32] = 1.0
    return sig + np.convolve(pulses, ring)[:n]


SCENARIOS = {
    "healthy": healthy,
    "imbalance": imbalance,
    "misalignment": misalignment,
    "looseness": looseness,
    "bearing": bearing,
}


def generate(name: str, n: int = ROM_LEN, seed: int = 1) -> np.ndarray:
    """int16 samples for scenario ``name``."""
    rng = np.random.default_rng(seed)
    sig = SCENARIOS[name](n, rng)
    return np.clip(np.round(sig), -32768, 32767).astype(np.int16)


def looped(name: str, n: int, seed: int = 1) -> np.ndarray:
    """Play a ROM_LEN-sample recording in a loop, as the board demo does."""
    base = generate(name, ROM_LEN, seed)
    return np.resize(base, n)
