import cv2
import numpy as np
import pytest
from projection_pen.calibration import Calibration, detect_markers, targets


def calibration():
    return Calibration(np.array([(50, 30), (600, 60), (570, 420), (20, 390)]), targets(1280, 720), (640, 480), (1280, 720))


def test_perspective_reference_and_independent_point():
    c = calibration()
    for source, output in zip(c.camera_points, c.output_points):
        assert c.map(tuple(source)) == pytest.approx(output, abs=.001)
    source = tuple(np.mean(c.camera_points, axis=0))
    assert c.map(source) == pytest.approx((640, 360), abs=.001)
    assert c.map((0, 0)) is None
    assert c.map((float('nan'), 0)) is None


def test_measured_error_not_fit_residual():
    c = calibration()
    result = c.errors(np.array([[310, 225]]), np.array([[643, 364]]))
    assert result['mean_px'] == pytest.approx(5, abs=1e-3)
    assert result['max_px'] == pytest.approx(5, abs=1e-3)


@pytest.mark.parametrize('points', [np.zeros((4, 2)), np.array([(0, 0), (100, 100), (100, 0), (0, 100)]), np.full((4, 2), np.nan)])
def test_bad_quadrilaterals(points):
    with pytest.raises(ValueError):
        Calibration(points, targets(1280, 720), (640, 480), (1280, 720))


def test_profile_round_trip(tmp_path):
    c = calibration()
    path = tmp_path/'profile.json'
    c.save(path)
    loaded = Calibration.load(path)
    assert loaded.map((310, 225)) == pytest.approx(c.map((310, 225)))


def test_automatic_four_markers():
    frame = np.full((600, 800, 3), 255, np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    centers = [(100, 100), (700, 100), (700, 500), (100, 500)]
    for index, (x, y) in enumerate(centers):
        marker = cv2.aruco.generateImageMarker(dictionary, index, 80)
        frame[y-40:y+40, x-40:x+40] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    assert detect_markers(frame) == pytest.approx(np.array(centers), abs=1)


def test_full_surface_not_only_inset_fit_rectangle():
    c = Calibration(targets(640, 480), targets(1280, 960), (640, 480), (1280, 960))
    assert c.map((5, 5)) == pytest.approx((10, 10), abs=.001)
    assert c.surface_points.shape == (4, 2)
    assert c.surface_points[0] == pytest.approx((0, 0), abs=.001)
