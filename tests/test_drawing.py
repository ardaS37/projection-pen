import json
import pytest
from PySide6.QtGui import QImage
from projection_pen.drawing import DrawingDocument
from projection_pen.filters import OneEuroFilter
from projection_pen.controls import ContactEstimator, ContactMetrics


def test_tracking_loss_and_gate_never_bridge(app):
    doc = DrawingDocument(100, 100)
    doc.feed((10, 10), True)
    doc.feed((20, 20), True)
    doc.feed(None, True)
    doc.feed((80, 80), True)
    assert len(doc.strokes) == 2
    assert doc.ink.pixelColor(50, 50).alpha() == 0
    doc.feed((85, 85), False)
    doc.feed((90, 90), True)
    assert len(doc.strokes) == 3


def test_new_identity_breaks_without_missing_frame(app):
    doc = DrawingDocument(100, 100)
    doc.feed((10, 10), True)
    doc.feed((90, 90), True, new_track=True)
    assert len(doc.strokes) == 2
    assert doc.ink.pixelColor(50, 50).alpha() == 0


def test_eraser_undo_redo_export_and_session(app, tmp_path):
    doc = DrawingDocument(100, 100)
    doc.brush_width = 10
    doc.feed((10, 50), True)
    doc.feed((90, 50), True)
    doc.end()
    doc.eraser = True
    doc.feed((50, 50), True)
    doc.end()
    assert doc.ink.pixelColor(50, 50).alpha() == 0
    doc.undo()
    assert doc.ink.pixelColor(50, 50).alpha() > 0
    doc.redo()
    assert doc.ink.pixelColor(50, 50).alpha() == 0
    path = tmp_path/'ink.png'
    doc.export_png(path, True)
    assert QImage(str(path)).pixelColor(0, 0).alpha() == 0
    doc.export_png(path, False)
    assert QImage(str(path)).pixelColor(0, 0).alpha() == 255
    session = tmp_path/'session.json'
    doc.save(session)
    restored = DrawingDocument()
    restored.load(session)
    assert len(restored.strokes) == 2
    assert restored.ink == doc.ink


def test_malformed_session_does_not_replace_drawing(app, tmp_path):
    doc = DrawingDocument(100, 100)
    doc.feed((10, 10), True)
    path = tmp_path/'bad.json'
    path.write_text(json.dumps({'version': 1, 'width': 100, 'height': 100, 'strokes': [{'color': 'red', 'width': -1, 'points': [[0, 0]]}]}))
    with pytest.raises(ValueError):
        doc.load(path)
    assert len(doc.strokes) == 1


def test_filter_reset_starts_at_new_location():
    f = OneEuroFilter()
    f.apply((0, 0), 1)
    p = f.apply((10, 10), 1.03)
    assert 0 < p[0] < 10
    f.reset()
    assert f.apply((100, 100), 2) == (100, 100)


def test_contact_is_only_hypothesis_with_label_metrics():
    estimator = ContactEstimator()
    assert not estimator.update((10, 10), 0)
    for t in [.03, .06, .09]:
        predicted = estimator.update((10, 10), t)
    assert predicted
    metrics = ContactMetrics()
    metrics.add(predicted, False)
    metrics.add(False, True)
    assert metrics.report()['false_positive_rate'] == 1
    assert metrics.report()['false_negative_rate'] == 1
