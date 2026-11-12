import cv2
import numpy as np
import pytest
from projection_pen.tracking import ColorTracker, TrackingConfig, sample_hsv


def image(*objects):
    frame = np.zeros((240, 320, 3), np.uint8)
    for x, y, radius in objects:
        cv2.circle(frame, (x, y), radius, (0, 255, 0), -1)
    return frame


def test_green_noise_and_offset():
    config = TrackingConfig(offset=(7, -3))
    frame = image((100, 100, 10), (20, 20, 1))
    result = ColorTracker().process(frame, 0, config)
    assert result.point == pytest.approx((107, 97))
    assert len(result.candidates) == 1
    assert result.new_track


def test_association_prefers_nearby_not_largest():
    tracker, config = ColorTracker(), TrackingConfig()
    tracker.process(image((100, 100, 10)), 0, config)
    found = tracker.process(image((105, 100, 10), (270, 200, 30)), .033, config)
    assert found.point == pytest.approx((105, 100))
    assert not found.new_track


def test_loss_breaks_track_even_if_identity_retained():
    tracker, config = ColorTracker(), TrackingConfig()
    tracker.process(image((100, 100, 10)), 0, config)
    assert tracker.process(image(), .033, config).point is None
    assert tracker.process(image((105, 100, 10)), .066, config).new_track


def test_jump_rejected_then_new_identity_after_timeout():
    tracker, config = ColorTracker(), TrackingConfig(max_speed=100)
    tracker.process(image((30, 30, 10)), 0, config)
    assert tracker.process(image((280, 200, 10)), .03, config).point is None
    assert tracker.process(image((280, 200, 10)), .5, config).new_track


def test_hue_seam_red():
    frame = np.zeros((100, 100, 3), np.uint8)
    frame[:] = (0, 0, 255)
    lo, hi = sample_hsv(frame, (50, 50))
    assert lo[0] > hi[0]
    result = ColorTracker().process(frame, 0, TrackingConfig(lower=lo, upper=hi, max_area=20000))
    assert result.point is not None


def test_roi_removes_projected_distractor():
    roi = np.array([(20, 20), (150, 20), (150, 180), (20, 180)])
    result = ColorTracker().process(image((100, 100, 10), (270, 200, 30)), 0, TrackingConfig(), roi)
    assert result.point == pytest.approx((100, 100))


@pytest.mark.parametrize('value', [100, 160, 240])
def test_brightness_variation(value):
    frame = image((100, 100, 10))
    frame[frame[:, :, 1] > 0, 1] = value
    assert ColorTracker().process(frame, 0, TrackingConfig()).point is not None


def test_track_epoch_survives_skipped_reacquisition_result():
    tracker, config = ColorTracker(), TrackingConfig()
    before = tracker.process(image((100, 100, 10)), 0, config)
    tracker.process(image(), .03, config)
    reacquired = tracker.process(image((105, 100, 10)), .06, config)
    later = tracker.process(image((110, 100, 10)), .09, config)
    assert later.track_id == reacquired.track_id != before.track_id
    assert not later.new_track


def test_surface_mask_is_applied_to_tip_not_marker_center():
    roi = np.array([(50, 50), (150, 50), (150, 180), (50, 180)])
    config = TrackingConfig(offset=(30, 0))
    result = ColorTracker().process(image((30, 100, 8)), 0, config, roi)
    assert result.point == pytest.approx((60, 100))
