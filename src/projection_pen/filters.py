"""Adaptive smoothing in output pixel coordinates."""
from __future__ import annotations

import math
import numpy as np


class OneEuroFilter:
    def __init__(self, min_cutoff: float = 1.5, beta: float = 0.02) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.reset()

    def reset(self) -> None:
        self.previous: np.ndarray | None = None
        self.derivative = np.zeros(2)
        self.time: float | None = None

    @staticmethod
    def alpha(cutoff: float | np.ndarray, dt: float) -> float | np.ndarray:
        return 1.0 / (1.0 + 1.0 / (2.0 * math.pi * cutoff * dt))

    def apply(self, point: tuple[float, float], timestamp: float) -> tuple[float, float]:
        value = np.asarray(point, dtype=float)
        if self.previous is None or self.time is None:
            filtered = value
        else:
            dt = max(1e-4, timestamp - self.time)
            derivative = (value - self.previous) / dt
            a = self.alpha(1.0, dt)
            self.derivative = a * derivative + (1 - a) * self.derivative
            a = self.alpha(self.min_cutoff + self.beta * np.abs(self.derivative), dt)
            filtered = a * value + (1 - a) * self.previous
        self.previous, self.time = filtered, timestamp
        return float(filtered[0]), float(filtered[1])
