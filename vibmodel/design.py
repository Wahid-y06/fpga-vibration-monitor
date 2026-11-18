"""Band-pass biquad design (RBJ audio-EQ cookbook) and Q2.16 quantization."""
from __future__ import annotations

import math

import numpy as np

from .config import BANDS, COEF_FRAC, COEF_W, FS


def rbj_bandpass(f0: float, q: float, fs: float = FS) -> tuple[list[float], list[float]]:
    """Constant 0 dB peak-gain band-pass. Returns (b, a) with a[0] = 1."""
    w0 = 2 * math.pi * f0 / fs
    alpha = math.sin(w0) / (2 * q)
    a0 = 1 + alpha
    b = [alpha / a0, 0.0, -alpha / a0]
    a = [1.0, -2 * math.cos(w0) / a0, (1 - alpha) / a0]
    return b, a


def quantize(value: float) -> int:
    q = round(value * (1 << COEF_FRAC))
    lo, hi = -(1 << (COEF_W - 1)), (1 << (COEF_W - 1)) - 1
    if not lo <= q <= hi:
        raise ValueError(f"coefficient {value} does not fit Q2.{COEF_FRAC}")
    return q


def band_coefficients() -> list[list[int]]:
    """Per band: [b0, b1, b2, -a1, -a2] as Q2.16 integers (feedback terms
    negated so the hardware only ever adds products)."""
    out = []
    for _, f0, q in BANDS:
        b, a = rbj_bandpass(f0, q)
        out.append([quantize(b[0]), quantize(b[1]), quantize(b[2]),
                    quantize(-a[1]), quantize(-a[2])])
    return out


def pole_radius(coefs: list[int]) -> float:
    """Largest pole magnitude of a quantized biquad (must be < 1)."""
    a1 = -coefs[3] / (1 << COEF_FRAC)
    a2 = -coefs[4] / (1 << COEF_FRAC)
    return float(max(abs(np.roots([1.0, a1, a2]))))


def frequency_response(coefs: list[int], freqs: np.ndarray, fs: float = FS) -> np.ndarray:
    scale = 1 << COEF_FRAC
    b = np.array(coefs[:3]) / scale
    a = np.array([1.0, -coefs[3] / scale, -coefs[4] / scale])
    z = np.exp(-1j * 2 * np.pi * freqs / fs)
    num = b[0] + b[1] * z + b[2] * z ** 2
    den = a[0] + a[1] * z + a[2] * z ** 2
    return np.abs(num / den)
