"""Bit-exact reference model of the RTL datapath.

Every operation mirrors the Verilog: integer arithmetic, arithmetic right
shifts (Python's >> floors, like Verilog's >>> on signed values), the same
rounding and the same saturation. The RTL testbenches compare against this
model sample-for-sample and block-for-block, so any difference is a bug.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import (BLOCK, BLOCK_LOG2, COEF_FRAC, DC_K, DW, ENERGY_W, INPUT_SHIFT, N_CH,
                     PERSIST_BLOCKS)
from .design import band_coefficients

NORMAL, WARNING, CRITICAL = 0, 1, 2


def sat(value: int, bits: int) -> int:
    lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    return lo if value < lo else hi if value > hi else value


def sat_u(value: int, bits: int) -> int:
    return min(value, (1 << bits) - 1)


class DcBlocker:
    """y[n] = x[n] - x[n-1] + y[n-1] - y[n-1] * 2^-K"""

    def __init__(self) -> None:
        self.x1 = 0
        self.y1 = 0

    def step(self, sample: int) -> int:
        x = sample << INPUT_SHIFT
        y = sat(x - self.x1 + self.y1 - (self.y1 >> DC_K), DW)
        self.x1, self.y1 = x, y
        return y


class FilterBank:
    """Direct-form-I biquads sharing the input history."""

    def __init__(self, coefs: list[list[int]] | None = None) -> None:
        self.coefs = coefs or band_coefficients()
        n = len(self.coefs)
        self.x1 = self.x2 = 0
        self.y1 = [0] * n
        self.y2 = [0] * n

    def step(self, x: int) -> list[int]:
        out = []
        for b, c in enumerate(self.coefs):
            acc = (c[0] * x + c[1] * self.x1 + c[2] * self.x2
                   + c[3] * self.y1[b] + c[4] * self.y2[b])
            y = sat((acc + (1 << (COEF_FRAC - 1))) >> COEF_FRAC, DW)
            self.y2[b], self.y1[b] = self.y1[b], y
            out.append(y)
        self.x2, self.x1 = self.x1, x
        return out


class BlockEnergy:
    """Mean-square value of each channel over BLOCK samples, in input LSB^2."""

    def __init__(self, n_ch: int = N_CH) -> None:
        self.sums = [0] * n_ch
        self.count = 0

    def step(self, channels: list[int]) -> list[int] | None:
        for i, y in enumerate(channels):
            v = y >> INPUT_SHIFT
            self.sums[i] += v * v
        self.count += 1
        if self.count < BLOCK:
            return None
        energies = [sat_u(s >> BLOCK_LOG2, ENERGY_W) for s in self.sums]
        self.sums = [0] * len(self.sums)
        self.count = 0
        return energies


@dataclass
class AlarmChannel:
    warn: int
    crit: int
    persist: int = PERSIST_BLOCKS
    level: int = NORMAL
    pending: int = 0

    def classify(self, energy: int) -> int:
        crit = self.crit - ((self.crit >> 3) if self.level >= CRITICAL else 0)
        warn = self.warn - ((self.warn >> 3) if self.level >= WARNING else 0)
        if energy >= crit:
            return CRITICAL
        if energy >= warn:
            return WARNING
        return NORMAL

    def update(self, energy: int) -> int:
        raw = self.classify(energy)
        if raw <= self.level:
            self.pending = 0
            self.level = raw
        else:
            self.pending += 1
            if self.pending >= self.persist:
                self.level = raw
                self.pending = 0
        return self.level


@dataclass
class BlockResult:
    energies: list[int]
    levels: list[int]

    @property
    def overall(self) -> int:
        return max(self.levels)


@dataclass
class Monitor:
    warn: list[int]
    crit: list[int]
    persist: int = PERSIST_BLOCKS
    dc: DcBlocker = field(default_factory=DcBlocker)
    bank: FilterBank = field(default_factory=FilterBank)
    energy: BlockEnergy = field(default_factory=BlockEnergy)

    def __post_init__(self) -> None:
        self.alarms = [AlarmChannel(w, c, self.persist) for w, c in zip(self.warn, self.crit)]

    def step(self, sample: int) -> BlockResult | None:
        x = self.dc.step(sample)
        channels = [x] + self.bank.step(x)
        energies = self.energy.step(channels)
        if energies is None:
            return None
        levels = [a.update(e) for a, e in zip(self.alarms, energies)]
        return BlockResult(energies, levels)

    def run(self, samples) -> list[BlockResult]:
        results = []
        for s in samples:
            r = self.step(int(s))
            if r is not None:
                results.append(r)
        return results


def log2_q3(value: int) -> int:
    """8-bit log2 with 3 fractional bits, as used for the VGA bar heights."""
    if value <= 0:
        return 0
    msb = value.bit_length() - 1
    frac = (value >> (msb - 3)) & 7 if msb >= 3 else (value << (3 - msb)) & 7
    return (msb << 3) | frac


def bar_height(value: int) -> int:
    """VGA bar height in pixels: 16 px per octave, energies below 2^8 hidden."""
    level = log2_q3(value)
    return 0 if level < 64 else (level - 64) * 2
