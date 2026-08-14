"""Industrial signal generators for the simulator.

Each generator yields the next sample when ``next(t)`` is called. ``t`` is a
unix timestamp (seconds); when omitted, ``time.time()`` is used so signals are
phase-stable across calls.
"""
import math
import random
import time
from typing import Optional


class Signal:
    def next(self, t: Optional[float] = None):
        raise NotImplementedError


class SineSignal(Signal):
    def __init__(self, p: dict):
        self.amp = float(p.get("amplitude", 1))
        self.offset = float(p.get("offset", 0))
        self.period = float(p.get("period", 60))
        self.phase = float(p.get("phase", 0))

    def next(self, t: Optional[float] = None):
        t = time.time() if t is None else t
        return self.offset + self.amp * math.sin(2 * math.pi * t / self.period + self.phase)


class RandomWalkSignal(Signal):
    def __init__(self, p: dict):
        self.value = float(p.get("start", 0))
        self.step = float(p.get("step", 1))
        self.min = float(p.get("min", -1e9))
        self.max = float(p.get("max", 1e9))

    def next(self, t: Optional[float] = None):
        self.value += random.uniform(-self.step, self.step)
        self.value = max(self.min, min(self.max, self.value))
        return self.value


class SquareSignal(Signal):
    """Toggle between low/high every `period` seconds (returns 0/1 or low/high)."""

    def __init__(self, p: dict):
        self.low = float(p.get("low", 0))
        self.high = float(p.get("high", 1))
        self.period = float(p.get("period", 30))

    def next(self, t: Optional[float] = None):
        t = time.time() if t is None else t
        return self.high if (int(t / self.period) % 2 == 0) else self.low


class ConstantSignal(Signal):
    def __init__(self, p: dict):
        self.value = float(p.get("value", 0))

    def next(self, t: Optional[float] = None):
        return self.value


class RampSignal(Signal):
    def __init__(self, p: dict):
        self.start = float(p.get("start", 0))
        self.stop = float(p.get("stop", 100))
        self.period = float(p.get("period", 60))

    def next(self, t: Optional[float] = None):
        t = time.time() if t is None else t
        phase = (t % self.period) / self.period
        return self.start + (self.stop - self.start) * phase


def make_signal(gen_spec: dict) -> Signal:
    """Build a Signal from a generator spec dict {type: ..., ...params}."""
    g = gen_spec or {"type": "constant", "value": 0}
    t = g.get("type", "constant")
    if t == "sine":
        return SineSignal(g)
    if t == "random_walk":
        return RandomWalkSignal(g)
    if t in ("square", "step"):
        return SquareSignal(g)
    if t == "ramp":
        return RampSignal(g)
    return ConstantSignal(g)
