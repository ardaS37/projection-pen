"""Native camera discovery: names and backend-specific indices, no stream probing."""
from __future__ import annotations

from dataclasses import dataclass
import platform
import re
import cv2
from cv2_enumerate_cameras import enumerate_cameras


BACKEND_NAMES = {cv2.CAP_ANY: 'Otomatik', cv2.CAP_MSMF: 'Media Foundation',
                 cv2.CAP_DSHOW: 'DirectShow', cv2.CAP_V4L2: 'V4L2', cv2.CAP_AVFOUNDATION: 'AVFoundation'}


@dataclass(frozen=True)
class CameraEndpoint:
    index: int
    backend: int

    @property
    def label(self) -> str:
        return f'{BACKEND_NAMES.get(self.backend, str(self.backend))} #{self.index}'


@dataclass(frozen=True)
class CameraDevice:
    name: str
    identifier: str
    endpoints: tuple[CameraEndpoint, ...]

    @property
    def label(self) -> str:
        return f'{self.name} — {", ".join(e.label for e in self.endpoints)}'


def native_backends() -> tuple[int, ...]:
    system = platform.system()
    if system == 'Windows':
        return cv2.CAP_MSMF, cv2.CAP_DSHOW
    if system == 'Linux':
        return (cv2.CAP_V4L2,)
    if system == 'Darwin':
        return (cv2.CAP_AVFOUNDATION,)
    return (cv2.CAP_ANY,)


def device_identity(path: str, backend: int, index: int) -> str:
    if not path:
        # Two cameras may share a friendly name. Never merge them by name alone.
        return f'backend:{backend}:index:{index}'
    if platform.system() == 'Windows':
        value = path.casefold().removeprefix('@device:pnp:')
        # MF and DShow may expose different interface-category GUIDs for the
        # same device instance. Preserve USB serial/MI; remove only the tail.
        return re.sub(r'#\{[0-9a-f-]{36}\}(?:\\.*)?$', '', value)
    return path


def available_cameras() -> list[CameraDevice]:
    devices: dict[str, CameraDevice] = {}
    failures = []
    successes = 0
    for backend in native_backends():
        try:
            entries = enumerate_cameras(backend)
            successes += 1
        except Exception as exc:
            failures.append(f'{BACKEND_NAMES.get(backend, backend)}: {exc}')
            continue
        for entry in entries:
            identity = device_identity(entry.path, backend, entry.index)
            endpoint = CameraEndpoint(entry.index, backend)
            if identity in devices:
                device = devices[identity]
                if endpoint not in device.endpoints:
                    devices[identity] = CameraDevice(device.name, identity, (*device.endpoints, endpoint))
            else:
                devices[identity] = CameraDevice(entry.name or f'Kamera {entry.index}', identity, (endpoint,))
    if not successes:
        raise RuntimeError('Kamera listesi alınamadı. ' + '; '.join(failures))
    return list(devices.values())


def camera_endpoints(source: int | CameraDevice, backend: int = cv2.CAP_ANY) -> tuple[CameraEndpoint, ...]:
    if isinstance(source, CameraDevice):
        endpoints = tuple(e for e in source.endpoints if backend == cv2.CAP_ANY or e.backend == backend)
        if not endpoints:
            raise RuntimeError(f'{source.name} seçilen kamera yönteminde listelenmiyor. Otomatik seçin veya listeyi yenileyin.')
        return endpoints
    return tuple(CameraEndpoint(source, b) for b in (native_backends() if backend == cv2.CAP_ANY else (backend,)))
