"""Latest-frame capture and processing workers, bounded independently of GUI speed."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock, Thread
import copy
import time
import cv2
import numpy as np
from .tracking import ColorTracker, Detection, TrackingConfig
from .camera_devices import CameraDevice, available_cameras
from .camera_open import open_camera


class LatestSlot:
    def __init__(self) -> None:
        self.lock = Lock()
        self.value = None

    def put(self, value) -> None:
        with self.lock:
            self.value = value

    def get(self):
        with self.lock:
            return self.value

    def take(self):
        with self.lock:
            value, self.value = self.value, None
            return value


@dataclass
class Frame:
    image: np.ndarray
    timestamp: float
    sequence: int
    generation: int


@dataclass
class TrackingResult:
    frame: Frame
    detection: Detection
    processing_ms: float
    fps: float
    config_revision: int = 0


class CameraPipeline:
    def __init__(self, source: int | str | CameraDevice, width: int = 1280, height: int = 720,
                 fps: int = 30, generation: int = 0, simulate: bool = False, backend: int = cv2.CAP_ANY) -> None:
        self.source, self.width, self.height, self.fps = source, width, height, fps
        self.backend = backend
        self.generation, self.simulate = generation, simulate
        self.frames, self.results = LatestSlot(), LatestSlot()
        self.errors, self.info = LatestSlot(), LatestSlot()
        self.settings, self.camera_controls = LatestSlot(), LatestSlot()
        self.revision = 0
        self.settings.put((TrackingConfig(), None, self.revision))
        self.stop_event = Event()
        self.threads: list[Thread] = []

    def configure(self, config: TrackingConfig, roi: np.ndarray | None) -> None:
        self.revision += 1
        self.settings.put((copy.deepcopy(config), None if roi is None else roi.copy(), self.revision))

    def start(self) -> None:
        self.threads = [Thread(target=self._capture, daemon=True, name='capture'),
                        Thread(target=self._process, daemon=True, name='tracking')]
        for thread in self.threads:
            thread.start()

    def stop(self) -> bool:
        self.stop_event.set()
        # Never block the GUI indefinitely on a backend's stalled read().
        for thread in self.threads:
            thread.join(timeout=0.15)
        return not any(thread.is_alive() for thread in self.threads)

    def _capture(self) -> None:
        cap = None
        try:
            if not self.simulate:
                pending = None
                opened_as = 'Video'
                if isinstance(self.source, (int, CameraDevice)):
                    cap, pending, endpoint, mode = open_camera(self.source, self.backend, self.width, self.height,
                                                              self.fps, self.stop_event, self.info.put)
                    opened_as = f'{endpoint.label} · {mode}'
                else:
                    cap = cv2.VideoCapture(self.source, cv2.CAP_ANY)
                    if not cap.isOpened():
                        raise RuntimeError('Video dosyası açılamadı. Dosya yolunu ve biçimini kontrol edin.')
                actual_fps = cap.get(cv2.CAP_PROP_FPS)
                self.info.put(f'{opened_as} · {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))} × '
                              f'{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}, cihaz FPS: {actual_fps:.1f}')
            else:
                actual_fps = self.fps
                self.info.put(f'Simülasyon: {self.width} × {self.height}, {self.fps} FPS')
            sequence, origin = 0, time.monotonic()
            while not self.stop_event.is_set():
                if self.simulate:
                    image = np.full((self.height, self.width, 3), 25, np.uint8)
                    elapsed = time.monotonic()-origin
                    center = (int(self.width*(.5+.3*np.cos(elapsed))), int(self.height*(.5+.3*np.sin(elapsed))))
                    cv2.circle(image, center, 12, (0, 255, 0), -1)
                else:
                    controls = self.camera_controls.take()
                    if controls:
                        for prop, value in controls:
                            if not cap.set(prop, value):
                                self.info.put('Kamera bu pozlama/beyaz dengesi ayarını desteklemiyor.')
                    if pending is not None:
                        ok, image, pending = True, pending, None
                    else:
                        ok, image = cap.read()
                    if not ok:
                        raise RuntimeError('Video sona erdi veya kamera bağlantısı kesildi. Çizim durduruldu.')
                self.frames.put(Frame(image, time.monotonic(), sequence, self.generation))
                sequence += 1
                if self.simulate or isinstance(self.source, str):
                    period = 1/max(1, actual_fps if actual_fps > 0 else self.fps)
                    self.stop_event.wait(max(0, origin+sequence*period-time.monotonic()))
        except Exception as exc:
            if not self.stop_event.is_set():
                self.errors.put(str(exc))
        finally:
            if cap is not None:
                cap.release()
            self.stop_event.set()

    def _process(self) -> None:
        tracker = ColorTracker()
        last_sequence, previous_time = -1, None
        previous_revision = -1
        while not self.stop_event.is_set():
            frame = self.frames.get()
            if frame is None or frame.sequence == last_sequence:
                self.stop_event.wait(.002)
                continue
            config, roi, revision = self.settings.get()
            if revision != previous_revision:
                tracker.reset()
                previous_revision = revision
            try:
                start = time.monotonic()
                detection = tracker.process(frame.image, frame.timestamp, config, roi)
                fps = 0 if previous_time is None else 1/max(1e-6, frame.timestamp-previous_time)
                self.results.put(TrackingResult(frame, detection, (time.monotonic()-start)*1000, fps, revision))
                last_sequence, previous_time = frame.sequence, frame.timestamp
            except Exception as exc:
                self.errors.put(f'Görüntü işleme hatası: {exc}')
                self.stop_event.set()
