"""Open and verify a stream, falling back only to endpoints of the same camera."""
from __future__ import annotations

from threading import Event
from collections.abc import Callable
import cv2
import numpy as np
from .camera_devices import CameraDevice, camera_endpoints


def open_camera(source: int | CameraDevice, backend: int, width: int, height: int,
                fps: int, stopped: Event, status: Callable[[str], None]):
    failures = []
    name = source.name if isinstance(source, CameraDevice) else f'Kamera {source}'
    for endpoint in camera_endpoints(source, backend):
        for requested in (True, False):
            if stopped.is_set():
                raise RuntimeError('Kamera açılışı iptal edildi.')
            mode = f'{width}×{height}, {fps} FPS isteği' if requested else 'cihaz varsayılanları'
            status(f'{name}: {endpoint.label}, {mode} deneniyor…')
            cap = None
            accepted = False
            try:
                cap = cv2.VideoCapture(endpoint.index, endpoint.backend)
                if cap.isOpened():
                    if requested:
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                        cap.set(cv2.CAP_PROP_FPS, fps)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    for _ in range(3):
                        if stopped.is_set():
                            break
                        ok, first = cap.read()
                        if ok and isinstance(first, np.ndarray) and first.size > 0:
                            accepted = True
                            return cap, first, endpoint, mode
                        stopped.wait(.04)
                failures.append(f'{endpoint.label} ({mode}): görüntü alınamadı')
            except Exception as exc:
                failures.append(f'{endpoint.label} ({mode}): {exc}')
            finally:
                if cap is not None and not accepted:
                    cap.release()
    raise RuntimeError(
        f'{name} açılamadı. Windows Ayarlar → Gizlilik ve güvenlik → Kamera bölümünde '
        'masaüstü uygulamalarının erişimini açın. Kamera/Teams/Zoom/OBS gibi kamerayı kullanan '
        'uygulamaları kapatın. Kamera yöntemini değiştirin veya 640×480 / 30 FPS deneyin.\n'
        + '\n'.join(failures))
