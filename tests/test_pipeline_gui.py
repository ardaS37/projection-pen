import time
import cv2
import numpy as np
import pytest
from projection_pen.camera import CameraPipeline, LatestSlot
from projection_pen.gui import MainWindow


def wait_for(app, condition, seconds=3):
    limit = time.monotonic()+seconds
    while time.monotonic() < limit:
        app.processEvents()
        if condition():
            return
        time.sleep(.005)
    raise AssertionError('Timed out')


def test_latest_slot_is_bounded():
    slot = LatestSlot()
    for i in range(10000):
        slot.put(i)
    assert slot.take() == 9999
    assert slot.take() is None


def test_synthetic_camera_mapping_drawing_end_to_end(app, tmp_path):
    window = MainWindow()
    window.config_dir = tmp_path
    window.show()
    window.show_projection()
    window.mode.setCurrentIndex(1)
    window.start_camera(simulate=True)
    wait_for(app, lambda: len(window.document.strokes) > 0)
    wait_for(app, lambda: len(window.document.strokes[0].points) > 4)
    assert window.calibration is not None
    assert window.last_result.detection.point is not None
    assert not window.document.ink.isNull()
    window.stop_camera()
    assert window.document.active is None
    window.close()


def test_screen_geometry_change_invalidates_mapping(app, tmp_path):
    window = MainWindow()
    window.config_dir = tmp_path
    window.start_camera(simulate=True)
    assert window.calibration is not None
    window.output_changed()
    assert window.calibration is None
    window.close()


def test_video_file_tracking_and_end_of_stream(tmp_path):
    path = tmp_path/'green.avi'
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 30, (320, 240))
    if not writer.isOpened():
        pytest.skip('MJPG video encoder unavailable')
    for x in range(30, 90, 5):
        frame = np.zeros((240, 320, 3), np.uint8)
        cv2.circle(frame, (x, 100), 10, (0, 255, 0), -1)
        writer.write(frame)
    writer.release()
    pipeline = CameraPipeline(str(path), generation=7)
    pipeline.start()
    seen = []
    deadline = time.monotonic()+3
    while time.monotonic() < deadline and not pipeline.stop_event.is_set():
        result = pipeline.results.take()
        if result:
            seen.append(result)
        time.sleep(.005)
    pipeline.stop()
    assert any(r.detection.point is not None for r in seen)
    assert all(r.frame.generation == 7 for r in seen)
    assert pipeline.errors.take() is not None


def test_real_projector_targets_detectable_and_dpi_mapping(app, tmp_path):
    from projection_pen.calibration import detect_markers, targets
    window = MainWindow()
    window.config_dir = tmp_path
    window.projection.resize(800, 600)
    window.document.resize_canvas(1600, 1200)
    window.projection.calibrating = True
    image = window.projection.grab().toImage().convertToFormat(__import__('PySide6.QtGui', fromlist=['QImage']).QImage.Format.Format_RGB888)
    frame = np.frombuffer(image.bits(), np.uint8).reshape(image.height(), image.bytesPerLine())[:, :image.width()*3].reshape(image.height(), image.width(), 3).copy()
    found = detect_markers(frame)
    expected = targets(1600, 1200) * [image.width()/1600, image.height()/1200]
    assert found == pytest.approx(expected, abs=2)
    window.close()


def test_pdf_background_render(app, tmp_path):
    from PySide6.QtGui import QPainter, QPdfWriter
    from PySide6.QtCore import QRect
    path = tmp_path/'slide.pdf'
    writer = QPdfWriter(str(path))
    painter = QPainter(writer)
    painter.drawText(QRect(0, 0, 800, 800), 0, 'Projection Pen PDF test')
    painter.end()
    del writer
    window = MainWindow()
    window.config_dir = tmp_path
    window.set_content(str(path))
    assert not window.document.content.isNull()
    assert window.document.content_page == 0
    assert window.document.content.width() < window.document.content.height()  # portrait PDF must retain aspect ratio
    window.close()


def test_gui_does_not_bridge_if_latest_slot_skipped_loss_and_reacquisition(app, tmp_path):
    from projection_pen.calibration import Calibration, targets
    from projection_pen.camera import Frame, TrackingResult
    from projection_pen.tracking import Detection
    window = MainWindow()
    window.config_dir = tmp_path
    window.show_projection()
    window.mode.setCurrentIndex(1)
    w, h = window.document.width, window.document.height
    window.calibration = Calibration(targets(w, h), targets(w, h), (w, h), (w, h))
    window.pipeline = CameraPipeline(0, simulate=True)
    frame = np.zeros((h, w, 3), np.uint8)
    mask = np.zeros((h, w), np.uint8)
    for seq, point, epoch in [(0, (100., 100.), 1), (1, (200., 200.), 2)]:
        # The one-frame new_track flag is deliberately false: GUI missed that result.
        result = TrackingResult(Frame(frame, time.monotonic(), seq, 0), Detection(point, point, mask, track_id=epoch), 1, 30)
        window.pipeline.results.put(result)
        window.tick()
    assert len(window.document.strokes) == 2
    assert window.document.ink.pixelColor(150, 150).alpha() == 0
    window.close()


def test_camera_dropdown_lists_real_names_and_keeps_device_selection(app, tmp_path):
    from projection_pen.camera_devices import CameraDevice, CameraEndpoint
    window = MainWindow()
    window.config_dir = tmp_path
    cameras = [CameraDevice('Integrated Webcam', 'builtin', (CameraEndpoint(0, cv2.CAP_MSMF),)),
               CameraDevice('Logitech USB Webcam', 'usb-1', (CameraEndpoint(2, cv2.CAP_MSMF), CameraEndpoint(4, cv2.CAP_DSHOW)))]
    window.populate_cameras(cameras)
    assert window.camera_choice.count() == 2
    assert 'Logitech' in window.camera_choice.itemText(1)
    window.camera_choice.setCurrentIndex(1)
    window.populate_cameras(list(reversed(cameras)))
    assert window.camera_choice.currentData().identifier == 'usb-1'
    window.populate_cameras([])
    assert window.camera_choice.count() == 0  # no fictional Camera 0
    assert 'bulunamadı' in window.camera_list_info.text()
    window.close()


def test_start_camera_passes_selected_device_and_backend(app, tmp_path, monkeypatch):
    from projection_pen.camera_devices import CameraDevice, CameraEndpoint
    window = MainWindow()
    window.config_dir = tmp_path
    device = CameraDevice('USB Webcam', 'usb-device', (CameraEndpoint(7, cv2.CAP_DSHOW),))
    window.populate_cameras([device])
    monkeypatch.setattr(CameraPipeline, 'start', lambda self: None)
    window.start_camera()
    assert window.pipeline.source == device
    assert window.source_id == 'usb-device'
    assert window.pipeline.backend == cv2.CAP_ANY
    window.close()
