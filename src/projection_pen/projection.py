"""Qt projector window. The document is always expressed in physical pixels."""
from __future__ import annotations

import cv2
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QScreen
from PySide6.QtWidgets import QWidget
from .calibration import marker_layout, targets
from .drawing import DrawingDocument


def frame_image(frame) -> QImage:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format.Format_RGB888).copy()


class ProjectionWindow(QWidget):
    closed = Signal()

    def __init__(self, document: DrawingDocument) -> None:
        super().__init__()
        self.document = document
        self.overlay = False
        self.calibrating = False
        self.validation_target: tuple[float, float] | None = None
        self.cursor: tuple[float, float] | None = None
        self.setWindowTitle('Projection Pen — Projeksiyon')
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.document.changed.connect(self.update)
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.markers = []
        for index in range(4):
            image = cv2.aruco.generateImageMarker(dictionary, index, 200)
            self.markers.append(QImage(image.data, 200, 200, image.strides[0], QImage.Format.Format_Grayscale8).copy())

    def set_overlay(self, enabled: bool) -> None:
        self.overlay = enabled
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, enabled)
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, enabled)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)
        if visible:
            self.showFullScreen()
        self.update()

    def present(self, screen: QScreen) -> None:
        self.winId()
        self.windowHandle().setScreen(screen)
        self.setGeometry(screen.geometry())
        self.showFullScreen()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        # A transparent repaint must remove the previous cursor/ink too.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.scale(self.width()/self.document.width, self.height()/self.document.height)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.calibrating:
            painter.fillRect(QRectF(0, 0, self.document.width, self.document.height), QColor('white'))
            centers, size = marker_layout(self.document.width, self.document.height)
            painter.setPen(QColor('black'))
            for index, (x, y) in enumerate(centers):
                rect = QRectF(x-size/2, y-size/2, size, size)
                painter.drawImage(rect, self.markers[index])
                painter.drawText(QRectF(x-70, y+size/2+8, 140, 25), Qt.AlignmentFlag.AlignCenter, f'{index+1}')
        else:
            self.document.paint(painter, self.overlay)
            if self.cursor is not None:
                painter.setPen(QPen(QColor('#17cfee'), 2))
                painter.drawEllipse(QRectF(self.cursor[0]-9, self.cursor[1]-9, 18, 18))
        if self.validation_target:
            x, y = self.validation_target
            painter.setPen(QPen(QColor('#f0a000'), 3))
            painter.drawEllipse(QRectF(x-16, y-16, 32, 32))
            painter.drawLine(int(x-24), int(y), int(x+24), int(y))
            painter.drawLine(int(x), int(y-24), int(x), int(y+24))
        painter.end()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.closed.emit()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)
