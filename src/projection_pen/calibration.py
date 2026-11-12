"""Planar mapping and independent validation in physical projector pixels."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np
from .settings import read_json, write_json


def targets(width: int, height: int) -> np.ndarray:
    margin = max(40, min(width, height) * 0.09)
    return np.array([(margin, margin), (width-margin, margin),
                     (width-margin, height-margin), (margin, height-margin)], np.float64)


def marker_layout(width: int, height: int) -> tuple[np.ndarray, int]:
    return targets(width, height), max(32, int(min(width, height)*0.09))


def detect_markers(frame: np.ndarray) -> np.ndarray:
    detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50))
    corners, ids, _ = detector.detectMarkers(frame)
    if ids is None:
        raise ValueError("Dört ArUco hedefi bulunamadı; manuel seçim kullanabilirsiniz.")
    found = {int(i): np.mean(c.reshape(4, 2), axis=0) for c, i in zip(corners, ids.flatten())}
    if not all(i in found for i in range(4)):
        raise ValueError("0–3 numaralı hedeflerin tümü görünmeli.")
    return np.array([found[i] for i in range(4)], np.float64)


@dataclass
class Calibration:
    camera_points: np.ndarray
    output_points: np.ndarray
    camera_size: tuple[int, int]
    output_size: tuple[int, int]
    camera_id: str = ""
    screen_id: str = ""
    offset: tuple[float, float] = (0, 0)

    def __post_init__(self) -> None:
        self.camera_points = np.asarray(self.camera_points, np.float64)
        self.output_points = np.asarray(self.output_points, np.float64)
        for points in (self.camera_points, self.output_points):
            if points.shape != (4, 2) or not np.isfinite(points).all():
                raise ValueError("Kalibrasyon dört sonlu nokta gerektirir.")
            if not cv2.isContourConvex(points.astype(np.float32)) or abs(cv2.contourArea(points.astype(np.float32))) < 100:
                raise ValueError("Noktalar sıralı, dışbükey ve yeterince aralıklı olmalı.")
        for size in (self.camera_size, self.output_size):
            if len(size) != 2 or any(not isinstance(v, (int, np.integer)) or not 1 <= v <= 16384 for v in size):
                raise ValueError("Geçersiz kamera veya projeksiyon boyutu.")
        if len(self.offset) != 2 or not np.isfinite(self.offset).all():
            raise ValueError("Geçersiz kalem ofseti.")
        self.matrix = cv2.getPerspectiveTransform(self.camera_points.astype(np.float32), self.output_points.astype(np.float32))
        if not np.isfinite(self.matrix).all() or abs(np.linalg.det(self.matrix)) < 1e-12:
            raise ValueError("Kalibrasyon matrisi tekil.")
        inverse = np.linalg.inv(self.matrix)
        w, h = self.output_size
        denominators = (inverse @ np.array([[0, 0, 1], [w, 0, 1], [w, h, 1], [0, h, 1]]).T)[2]
        if np.any(np.abs(denominators) < 1e-8) or not (np.all(denominators > 0) or np.all(denominators < 0)):
            raise ValueError("Yüzey sınırında perspektif tekilliği var; kamera açısını değiştirin.")

    @property
    def surface_points(self) -> np.ndarray:
        corners = np.array([[(0., 0.), (self.output_size[0]-1., 0.),
                             (self.output_size[0]-1., self.output_size[1]-1.), (0., self.output_size[1]-1.)]], np.float64)
        return cv2.perspectiveTransform(corners, np.linalg.inv(self.matrix))[0]

    def map(self, point: tuple[float, float], restrict: bool = True) -> tuple[float, float] | None:
        if not np.isfinite(point).all():
            return None
        value = self.matrix @ np.array([*point, 1.0])
        if abs(value[2]) < 1e-9:
            return None
        x, y = value[:2] / value[2]
        if not np.isfinite([x, y]).all():
            return None
        if restrict and not (0 <= x < self.output_size[0] and 0 <= y < self.output_size[1]):
            return None
        return float(x), float(y)

    def errors(self, camera: np.ndarray, output: np.ndarray) -> dict:
        camera, output = np.asarray(camera, float), np.asarray(output, float)
        if camera.shape != output.shape or camera.ndim != 2 or camera.shape[1] != 2 or len(camera) < 1:
            raise ValueError("Eşleşen doğrulama noktaları gerekli.")
        mapped = [self.map(tuple(p), restrict=False) for p in camera]
        if any(p is None for p in mapped):
            raise ValueError("Doğrulama noktası dönüştürülemiyor.")
        distances = np.linalg.norm(np.array(mapped)-output, axis=1)
        return {"mean_px": float(distances.mean()), "max_px": float(distances.max()), "errors_px": distances.tolist()}

    def save(self, path: Path) -> None:
        write_json(path, {"version": 1, "camera_points": self.camera_points.tolist(),
                         "output_points": self.output_points.tolist(), "camera_size": self.camera_size,
                         "output_size": self.output_size, "camera_id": self.camera_id,
                         "screen_id": self.screen_id, "offset": self.offset})

    @classmethod
    def load(cls, path: Path) -> Calibration:
        data = read_json(path)
        data.pop('version')
        allowed = {'camera_points', 'output_points', 'camera_size', 'output_size', 'camera_id', 'screen_id', 'offset'}
        if set(data)-allowed:
            raise ValueError("Bilinmeyen kalibrasyon alanı.")
        return cls(**data)
