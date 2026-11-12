"""Stroke gating and explicitly experimental motion-based contact estimate."""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass
class ContactEstimator:
    """Slow movement is a hypothesis, never evidence of physical contact."""
    speed_threshold: float = 700
    previous: tuple[float, float] | None = None
    timestamp: float | None = None
    warmup: int = 0

    def reset(self) -> None:
        self.previous, self.timestamp, self.warmup = None, None, 0

    def update(self, point: tuple[float, float], timestamp: float) -> bool:
        speed = float('inf')
        if self.previous is not None and self.timestamp is not None:
            speed = math.dist(point, self.previous) / max(1e-4, timestamp-self.timestamp)
        self.previous, self.timestamp = point, timestamp
        self.warmup = self.warmup + 1 if speed < self.speed_threshold else 0
        return self.warmup >= 3


class ContactMetrics:
    def __init__(self) -> None:
        self.counts = dict(tp=0, fp=0, tn=0, fn=0)

    def add(self, predicted: bool, actual: bool) -> None:
        self.counts[('tp' if actual else 'fp') if predicted else ('fn' if actual else 'tn')] += 1

    def report(self) -> dict:
        c = self.counts
        return {**c, 'false_positive_rate': c['fp']/(c['fp']+c['tn']) if c['fp']+c['tn'] else None,
                'false_negative_rate': c['fn']/(c['fn']+c['tp']) if c['fn']+c['tp'] else None}
