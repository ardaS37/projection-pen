"""HSV tracking with bounded association; no GUI or camera dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import cv2
import numpy as np


@dataclass
class TrackingConfig:
    lower: tuple[int, int, int] = (35, 80, 65)
    upper: tuple[int, int, int] = (90, 255, 255)
    min_area: float = 25
    max_area: float = 15000
    kernel: int = 3
    max_speed: float = 1800  # camera pixels/second
    max_lost: float = 0.25
    offset: tuple[float, float] = (0.0, 0.0)


@dataclass
class Detection:
    point: tuple[float, float] | None
    raw_point: tuple[float, float] | None
    mask: np.ndarray
    candidates: list[tuple[float, float, float]] = field(default_factory=list)
    new_track: bool = False
    track_id: int = 0


def sample_hsv(frame: np.ndarray, point: tuple[int, int], radius: int = 4) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    x, y = point
    patch = frame[max(0, y-radius):y+radius+1, max(0, x-radius):x+radius+1]
    if patch.size == 0:
        raise ValueError("Örnek noktası görüntü dışında.")
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    # Circular mean handles red at the 0/179 hue seam.
    angles = hsv[:, 0].astype(float) * math.pi / 90
    hue = round(math.atan2(np.sin(angles).mean(), np.cos(angles).mean()) * 90 / math.pi) % 180
    s, v = np.median(hsv[:, 1:], axis=0)
    return ((hue-12) % 180, max(30, int(s)-65), max(25, int(v)-80)), ((hue+12) % 180, 255, 255)


class ColorTracker:
    def __init__(self) -> None:
        self.track_id = 0
        self.reset()

    def reset(self) -> None:
        self.track_id += 1
        self.previous: tuple[float, float] | None = None
        self.last_seen: float | None = None
        self.missing = True

    def process(self, frame: np.ndarray, timestamp: float, config: TrackingConfig,
                roi: np.ndarray | None = None) -> Detection:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lo, hi = np.array(config.lower, np.uint8), np.array(config.upper, np.uint8)
        if lo[0] <= hi[0]:
            mask = cv2.inRange(hsv, lo, hi)
        else:
            mask = cv2.inRange(hsv, (0, int(lo[1]), int(lo[2])), tuple(map(int, hi)))
            mask |= cv2.inRange(hsv, tuple(map(int, lo)), (179, int(hi[1]), int(hi[2])))
        if roi is not None:
            region = np.zeros(mask.shape, np.uint8)
            cv2.fillPoly(region, [np.asarray(np.asarray(roi)-config.offset, np.int32)], 255)
            mask &= region
        kernel = np.ones((config.kernel | 1, config.kernel | 1), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: list[tuple[float, float, float]] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if not config.min_area <= area <= config.max_area:
                continue
            hull_area = cv2.contourArea(cv2.convexHull(contour))
            if hull_area <= 0 or area / hull_area < 0.35:
                continue
            moments = cv2.moments(contour)
            if moments['m00']:
                candidates.append((moments['m10']/moments['m00'], moments['m01']/moments['m00'], area))
        associated = self.previous is not None and self.last_seen is not None and timestamp-self.last_seen <= config.max_lost
        chosen = None
        if associated:
            ranked = sorted(candidates, key=lambda c: math.dist(c[:2], self.previous))
            if ranked and math.dist(ranked[0][:2], self.previous) <= 15 + config.max_speed * max(0, timestamp-self.last_seen):
                chosen = ranked[0]
        elif candidates:
            chosen = max(candidates, key=lambda c: c[2])
        if chosen is None:
            self.missing = True
            return Detection(None, None, mask, candidates, track_id=self.track_id)
        fresh = self.missing or not associated
        if fresh:
            self.track_id += 1
        raw = chosen[:2]
        self.previous, self.last_seen, self.missing = raw, timestamp, False
        point = (raw[0]+config.offset[0], raw[1]+config.offset[1])
        return Detection(point, raw, mask, candidates, fresh, self.track_id)
