"""Resolution-stable stroke document; erasing uses alpha composition."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import math
from PySide6.QtCore import QObject, QPointF, QRectF, Signal, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from .settings import read_json, write_json


@dataclass
class Stroke:
    color: str
    width: float
    eraser: bool = False
    points: list[tuple[float, float]] = field(default_factory=list)


class DrawingDocument(QObject):
    changed = Signal()

    def __init__(self, width: int = 1280, height: int = 720) -> None:
        super().__init__()
        self.width, self.height = width, height
        self.strokes: list[Stroke] = []
        self.redo_stack: list[Stroke] = []
        self.active: Stroke | None = None
        self.color, self.brush_width, self.eraser = '#ff3030', 5.0, False
        self.background, self.background_color = 'Beyaz', '#ffffff'
        self.content = QImage()
        self.content_path: str | None = None
        self.content_page = 0
        self._allocate()

    def _allocate(self) -> None:
        self.ink = QImage(self.width, self.height, QImage.Format.Format_ARGB32_Premultiplied)
        self.ink.fill(Qt.GlobalColor.transparent)

    def resize_canvas(self, width: int, height: int) -> None:
        self.end()
        if (width, height) == (self.width, self.height):
            return
        sx, sy = width/self.width, height/self.height
        for stroke in self.strokes:
            stroke.points = [(x*sx, y*sy) for x, y in stroke.points]
            stroke.width *= (sx+sy)/2
        self.width, self.height = width, height
        self.redo_stack.clear()
        self.rebuild()

    def feed(self, point: tuple[float, float] | None, enabled: bool, new_track: bool = False) -> None:
        if not enabled or point is None:
            self.end()
            return
        if new_track:
            self.end()
        if self.active is None:
            self.active = Stroke(self.color, self.brush_width, self.eraser, [point])
            self.strokes.append(self.active)
            self.redo_stack.clear()
            self._segment(self.active, point, point)
        else:
            previous = self.active.points[-1]
            if math.dist(point, previous) < .25:
                return
            self.active.points.append(point)
            self._segment(self.active, previous, point)
        self.changed.emit()

    def end(self) -> None:
        self.active = None

    def _segment(self, stroke: Stroke, first: tuple, second: tuple) -> None:
        painter = QPainter(self.ink)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if stroke.eraser:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.setPen(QPen(QColor(stroke.color), stroke.width, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if first == second:
            painter.drawPoint(QPointF(*first))
        else:
            painter.drawLine(QPointF(*first), QPointF(*second))
        painter.end()

    def rebuild(self) -> None:
        self._allocate()
        for stroke in self.strokes:
            self._segment(stroke, stroke.points[0], stroke.points[0])
            for a, b in zip(stroke.points, stroke.points[1:]):
                self._segment(stroke, a, b)
        self.changed.emit()

    def undo(self) -> None:
        self.end()
        if self.strokes:
            self.redo_stack.append(self.strokes.pop())
            self.rebuild()

    def redo(self) -> None:
        self.end()
        if self.redo_stack:
            self.strokes.append(self.redo_stack.pop())
            self.rebuild()

    def clear(self) -> None:
        self.end()
        self.strokes.clear()
        self.redo_stack.clear()
        self.rebuild()

    def paint(self, painter: QPainter, overlay: bool = False) -> None:
        bounds = QRectF(0, 0, self.width, self.height)
        if not overlay:
            color = '#000000' if self.background == 'Siyah' else self.background_color
            painter.fillRect(bounds, QColor(color))
            if self.background in ('Kareli', 'Çizgili'):
                painter.setPen(QPen(QColor('#b7c6d9'), 1))
                for y in range(0, self.height, 40):
                    painter.drawLine(0, y, self.width, y)
                if self.background == 'Kareli':
                    for x in range(0, self.width, 40):
                        painter.drawLine(x, 0, x, self.height)
            if not self.content.isNull():
                size = self.content.size().scaled(self.width, self.height, Qt.AspectRatioMode.KeepAspectRatio)
                rect = QRectF((self.width-size.width())/2, (self.height-size.height())/2, size.width(), size.height())
                painter.drawImage(rect, self.content)
        painter.drawImage(0, 0, self.ink)

    def export_png(self, path: Path, transparent: bool = False) -> None:
        image = QImage(self.width, self.height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self.paint(painter, overlay=transparent)
        painter.end()
        if not image.save(str(path), 'PNG'):
            raise OSError('PNG dosyası yazılamadı.')

    def save(self, path: Path) -> None:
        self.end()
        write_json(path, {'version': 1, 'width': self.width, 'height': self.height,
                          'background': self.background, 'background_color': self.background_color,
                          'content_path': self.content_path, 'content_page': self.content_page,
                          'strokes': [vars(s) for s in self.strokes]})

    def load(self, path: Path) -> dict:
        data = read_json(path)
        width, height = int(data['width']), int(data['height'])
        if not (1 <= width <= 16384 and 1 <= height <= 16384 and width*height <= 40_000_000):
            raise ValueError('Oturum boyutu geçersiz veya çok büyük.')
        strokes = []
        total = 0
        for value in data['strokes']:
            points = [tuple(map(float, p)) for p in value['points']]
            total += len(points)
            if not points or total > 1_000_000 or any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in points):
                raise ValueError('Geçersiz çizgi noktaları.')
            brush_width = float(value['width'])
            if not math.isfinite(brush_width) or not 0 < brush_width <= 2000 or not QColor(value['color']).isValid():
                raise ValueError('Geçersiz fırça.')
            strokes.append(Stroke(value['color'], brush_width, bool(value['eraser']), points))
        background = data.get('background', 'Beyaz')
        background_color = data.get('background_color', '#ffffff')
        content_path = data.get('content_path')
        content_page = data.get('content_page', 0)
        if background not in ('Beyaz', 'Siyah', 'Özel renk', 'Kareli', 'Çizgili'):
            raise ValueError('Geçersiz zemin türü.')
        if not isinstance(background_color, str) or not QColor(background_color).isValid():
            raise ValueError('Geçersiz zemin rengi.')
        if content_path is not None and not isinstance(content_path, str):
            raise ValueError('Geçersiz içerik yolu.')
        if not isinstance(content_page, int) or content_page < 0:
            raise ValueError('Geçersiz PDF sayfası.')
        self.end()
        self.width, self.height, self.strokes = width, height, strokes
        self.redo_stack.clear()
        self.background = background
        self.background_color = background_color
        self.content_path = content_path
        self.content_page = content_page
        self.content = QImage()
        self.rebuild()
        return data
