from types import SimpleNamespace
from threading import Event
import cv2
import numpy as np
import pytest
from projection_pen import camera_devices
from projection_pen.camera_devices import CameraDevice, CameraEndpoint
from projection_pen.camera_open import open_camera


def entry(index, name, path):
    return SimpleNamespace(index=index, name=name, path=path)


def test_windows_discovery_has_names_no_six_index_limit_and_no_stream_open(monkeypatch):
    monkeypatch.setattr(camera_devices.platform, 'system', lambda: 'Windows')
    devices = [entry(i, f'USB Camera {i}', f'usb-camera-{i}') for i in range(12)]
    monkeypatch.setattr(camera_devices, 'enumerate_cameras', lambda backend: devices)
    monkeypatch.setattr(cv2, 'VideoCapture', lambda *args: pytest.fail('Discovery must not open streams'))
    found = camera_devices.available_cameras()
    assert len(found) == 12
    assert found[11].name == 'USB Camera 11'
    assert found[11].endpoints == (CameraEndpoint(11, cv2.CAP_MSMF), CameraEndpoint(11, cv2.CAP_DSHOW))


def test_backend_indices_matched_by_device_path_not_name_or_index(monkeypatch):
    monkeypatch.setattr(camera_devices.platform, 'system', lambda: 'Windows')
    def enumerate_devices(backend):
        if backend == cv2.CAP_MSMF:
            return [entry(0, 'USB Camera', r'\\?\usb#vid_1'), entry(1, 'USB Camera', r'\\?\usb#vid_2')]
        return [entry(3, 'USB Camera', r'@device:pnp:\\?\USB#VID_2'), entry(4, 'USB Camera', r'@device:pnp:\\?\USB#VID_1')]
    monkeypatch.setattr(camera_devices, 'enumerate_cameras', enumerate_devices)
    found = camera_devices.available_cameras()
    assert len(found) == 2
    assert found[0].endpoints == (CameraEndpoint(0, cv2.CAP_MSMF), CameraEndpoint(4, cv2.CAP_DSHOW))
    assert found[1].endpoints == (CameraEndpoint(1, cv2.CAP_MSMF), CameraEndpoint(3, cv2.CAP_DSHOW))


def test_discovery_survives_one_unavailable_backend(monkeypatch):
    monkeypatch.setattr(camera_devices.platform, 'system', lambda: 'Windows')
    def enumerate_devices(backend):
        if backend == cv2.CAP_MSMF:
            raise OSError('unavailable')
        return [entry(0, 'Webcam', 'camera-a')]
    monkeypatch.setattr(camera_devices, 'enumerate_cameras', enumerate_devices)
    assert camera_devices.available_cameras()[0].name == 'Webcam'


def test_discovery_does_not_merge_equal_names_without_device_paths(monkeypatch):
    monkeypatch.setattr(camera_devices.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(camera_devices, 'enumerate_cameras', lambda backend: [entry(0, 'Webcam', ''), entry(1, 'Webcam', '')])
    assert len(camera_devices.available_cameras()) == 4


class FakeCapture:
    def __init__(self, opened=True, frames=True):
        self.opened, self.frames, self.released = opened, frames, False
        self.properties = []
    def isOpened(self):
        return self.opened
    def set(self, prop, value):
        self.properties.append(prop)
        return True
    def read(self):
        return (True, np.zeros((12, 16, 3), np.uint8)) if self.frames else (False, None)
    def release(self):
        self.released = True


def test_fallback_checks_first_frame_and_uses_same_cameras_dshow_index(monkeypatch):
    attempts, captures = [], []
    def capture(index, backend):
        attempts.append((index, backend))
        cap = FakeCapture(opened=True, frames=backend == cv2.CAP_DSHOW)
        captures.append(cap)
        return cap
    monkeypatch.setattr(cv2, 'VideoCapture', capture)
    device = CameraDevice('USB Camera', 'camera-a', (CameraEndpoint(2, cv2.CAP_MSMF), CameraEndpoint(5, cv2.CAP_DSHOW)))
    cap, frame, endpoint, _ = open_camera(device, cv2.CAP_ANY, 1280, 720, 30, Event(), lambda _: None)
    assert attempts == [(2, cv2.CAP_MSMF), (2, cv2.CAP_MSMF), (5, cv2.CAP_DSHOW)]
    assert all(c.released for c in captures[:-1])
    assert not cap.released
    assert endpoint.index == 5
    assert frame.shape == (12, 16, 3)


def test_fallback_reopens_with_native_format_when_requested_format_fails(monkeypatch):
    captures = []
    def capture(*args):
        cap = FakeCapture(frames=bool(captures))
        captures.append(cap)
        return cap
    monkeypatch.setattr(cv2, 'VideoCapture', capture)
    device = CameraDevice('Webcam', 'device', (CameraEndpoint(0, cv2.CAP_DSHOW),))
    cap, _, _, mode = open_camera(device, cv2.CAP_ANY, 1920, 1080, 60, Event(), lambda _: None)
    assert cv2.CAP_PROP_FRAME_WIDTH in captures[0].properties
    assert cv2.CAP_PROP_FRAME_WIDTH not in cap.properties
    assert mode == 'cihaz varsayılanları'


def test_open_failure_releases_devices_and_reports_permissions(monkeypatch):
    captures = []
    def capture(*args):
        cap = FakeCapture(opened=False)
        captures.append(cap)
        return cap
    monkeypatch.setattr(cv2, 'VideoCapture', capture)
    with pytest.raises(RuntimeError, match='masaüstü uygulamalarının erişimini'):
        open_camera(0, cv2.CAP_DSHOW, 640, 480, 30, Event(), lambda _: None)
    assert all(c.released for c in captures)


def test_manual_backend_never_opens_wrong_device(monkeypatch):
    device = CameraDevice('Webcam', 'id', (CameraEndpoint(1, cv2.CAP_MSMF),))
    monkeypatch.setattr(cv2, 'VideoCapture', lambda *args: pytest.fail('Cannot guess index on a backend where device was not found'))
    with pytest.raises(RuntimeError, match='Otomatik'):
        open_camera(device, cv2.CAP_DSHOW, 640, 480, 30, Event(), lambda _: None)


def test_cancelled_open_does_not_access_device(monkeypatch):
    stopped = Event()
    stopped.set()
    monkeypatch.setattr(cv2, 'VideoCapture', lambda *args: pytest.fail('Cancelled'))
    with pytest.raises(RuntimeError, match='iptal'):
        open_camera(0, cv2.CAP_DSHOW, 640, 480, 30, stopped, lambda _: None)


def test_same_usb_instance_with_different_interface_category_guids_is_merged(monkeypatch):
    monkeypatch.setattr(camera_devices.platform, 'system', lambda: 'Windows')
    mf = r'\\?\usb#vid_046d&pid_0825&mi_00#serial-a#{e5323777-f976-4f5b-9b55-b94699c46e44}\global'
    ds = r'@device:pnp:\\?\usb#vid_046d&pid_0825&mi_00#serial-a#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global'
    monkeypatch.setattr(camera_devices, 'enumerate_cameras', lambda backend: [entry(0 if backend == cv2.CAP_MSMF else 3, 'Webcam', mf if backend == cv2.CAP_MSMF else ds)])
    found = camera_devices.available_cameras()
    assert len(found) == 1
    assert [e.index for e in found[0].endpoints] == [0, 3]
