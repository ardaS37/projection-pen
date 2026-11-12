"""Control panel and orchestration; all QPainter operations stay on the GUI thread."""
from __future__ import annotations

from collections import deque
from pathlib import Path
import time
import cv2
import numpy as np
from PySide6.QtCore import QPointF, QStandardPaths, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QImage, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSpinBox, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)
from .calibration import Calibration, detect_markers, targets
from .camera import CameraPipeline, TrackingResult, available_cameras
from .controls import ContactEstimator, ContactMetrics
from .drawing import DrawingDocument
from .filters import OneEuroFilter
from .projection import ProjectionWindow, frame_image
from .settings import read_json, write_json
from .shortcuts import GlobalToggle
from .tracking import TrackingConfig, sample_hsv


class Preview(QWidget):
    clicked = Signal(float, float)

    def __init__(self) -> None:
        super().__init__()
        self.image = QImage()
        self.points: list[tuple[float, float]] = []
        self.cursor = None
        self.candidates = []
        self.setMinimumSize(320, 200)

    def image_rect(self):
        if self.image.isNull():
            return None
        size = self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        from PySide6.QtCore import QRectF
        return QRectF((self.width()-size.width())/2, (self.height()-size.height())/2, size.width(), size.height())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#10151e'))
        rect = self.image_rect()
        if rect is None:
            painter.setPen(QColor('#9baac0'))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'Kamera başlatın veya simülasyonu açın')
            return
        painter.drawImage(rect, self.image)
        painter.translate(rect.left(), rect.top())
        painter.scale(rect.width()/self.image.width(), rect.height()/self.image.height())
        painter.setPen(QPen(QColor('#f4bc41'), 2))
        for x, y, area in self.candidates:
            painter.drawEllipse(QPointF(x, y), 8, 8)
        if self.cursor:
            painter.setPen(QPen(QColor('#00e5ff'), 3))
            painter.drawEllipse(QPointF(*self.cursor), 12, 12)
        painter.setPen(QPen(QColor('#ff5959'), 3))
        for index, point in enumerate(self.points):
            painter.drawEllipse(QPointF(*point), 6, 6)
            painter.drawText(QPointF(point[0]+9, point[1]-9), str(index+1))

    def mousePressEvent(self, event) -> None:
        rect = self.image_rect()
        if rect and rect.contains(event.position()):
            self.clicked.emit((event.position().x()-rect.x())*self.image.width()/rect.width(),
                              (event.position().y()-rect.y())*self.image.height()/rect.height())


class MainWindow(QMainWindow):
    def __init__(self, demo: bool = False) -> None:
        super().__init__()
        self.setWindowTitle('Projection Pen — Kamera Tabanlı Akıllı Tahta')
        self.resize(1220, 820)
        self.config_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.document = DrawingDocument()
        self.projection = ProjectionWindow(self.document)
        self.projection.closed.connect(self.projection_hidden)
        self.pipeline: CameraPipeline | None = None
        self.retired_pipelines: list[CameraPipeline] = []
        self.last_track_id: int | None = None
        self.generation = 0
        self.source_id = ''
        self.calibration: Calibration | None = None
        self.last_result: TrackingResult | None = None
        self.last_frame = None
        self.last_sequence = -1
        self.camera_size: tuple[int, int] | None = None
        self.filter = OneEuroFilter()
        self.contact = ContactEstimator()
        self.contact_metrics = ContactMetrics()
        self.predicted_contact = False
        self.collecting = False
        self.frozen_frame = None
        self.validation_index: int | None = None
        self.validation_camera: list = []
        self.validation_output: list = []
        self.validation_report: dict = {}
        self.validation_samples: list = []
        self.sampling_validation = False
        self.diagnostics = deque(maxlen=1800)
        self._screen_connections: set[int] = set()
        self._build_ui()
        self.restore_settings()
        self.refresh_screens()
        self.global_toggle = GlobalToggle()
        self.global_toggle.toggled.connect(self.toggle_manual)
        self.shortcut = QShortcut(QKeySequence('F8'), self)
        self.shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.shortcut.activated.connect(self.toggle_manual)
        # Native grab consumes F8 in X11/Windows, so the local shortcut is only a fallback.
        self.shortcut.setEnabled(not self.global_toggle.status.startswith('Global F8 etkin'))
        self.shortcut_info.setText(self.global_toggle.status)
        app = QApplication.instance()
        app.screenAdded.connect(self.screens_changed)
        app.screenRemoved.connect(self.screens_changed)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        if demo:
            QTimer.singleShot(100, lambda: self.start_camera(simulate=True))

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        title = QLabel('PROJECTION PEN   •   Yerel kamera takibi ve dijital çizim')
        title.setStyleSheet('font-size: 19px; font-weight: 600; padding: 12px;')
        layout.addWidget(title)
        splitter = QSplitter()
        layout.addWidget(splitter, 1)
        left = QWidget()
        ll = QVBoxLayout(left)
        self.preview = Preview()
        self.preview.clicked.connect(self.preview_clicked)
        ll.addWidget(self.preview, 3)
        self.debug_preview = Preview()
        self.debug_preview.setMaximumHeight(230)
        ll.addWidget(self.debug_preview, 1)
        self.debug_preview.hide()
        self.stats = QLabel('Kamera kapalı')
        self.stats.setWordWrap(True)
        ll.addWidget(self.stats)
        self.device_info = QLabel('')
        self.device_info.setWordWrap(True)
        ll.addWidget(self.device_info)
        splitter.addWidget(left)
        tabs = QTabWidget()
        tabs.setMinimumWidth(390)
        splitter.addWidget(tabs)
        splitter.setSizes([720, 440])

        def tab(name: str):
            content = QWidget()
            form = QFormLayout(content)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(content)
            tabs.addTab(scroll, name)
            return form

        camera = tab('Kamera')
        self.camera_choice = QComboBox()
        self.camera_choice.setEditable(True)
        self.camera_choice.addItem('0', 0)
        camera.addRow('USB kamera', self.camera_choice)
        self.button(camera, 'Kameraları bul', self.refresh_cameras)
        self.resolution = QComboBox()
        self.resolution.addItems(['640x480', '1280x720', '1920x1080'])
        self.resolution.setCurrentIndex(1)
        camera.addRow('İstenen çözünürlük', self.resolution)
        self.fps = self.spin(15, 120, 30)
        camera.addRow('İstenen FPS', self.fps)
        self.button(camera, 'Kamerayı başlat', lambda: self.start_camera())
        self.button(camera, 'Durdur', self.stop_camera)
        self.button(camera, 'Video dosyası aç', self.open_video)
        self.button(camera, 'Donanımsız simülasyon', lambda: self.start_camera(simulate=True))
        self.sample_color = QCheckBox('Önizlemeye tıklayarak renk örnekle')
        camera.addRow(self.sample_color)
        self.hsv = []
        for name, maximum, value in [('H alt', 179, 35), ('S alt', 255, 80), ('V alt', 255, 65),
                                      ('H üst', 179, 90), ('S üst', 255, 255), ('V üst', 255, 255)]:
            widget = self.spin(0, maximum, value)
            widget.valueChanged.connect(self.tracking_changed)
            self.hsv.append(widget)
            camera.addRow(name, widget)
        self.show_mask = QCheckBox('HSV maskesi / aday nesneler')
        self.show_mask.toggled.connect(self.debug_preview.setVisible)
        camera.addRow(self.show_mask)
        self.auto_exposure = QCheckBox('Otomatik pozlama')
        self.auto_exposure.setChecked(True)
        camera.addRow(self.auto_exposure)
        self.exposure = self.real_spin(-20, 10000, -6)
        camera.addRow('Pozlama (cihaza özgü)', self.exposure)
        self.auto_wb = QCheckBox('Otomatik beyaz dengesi')
        self.auto_wb.setChecked(True)
        camera.addRow(self.auto_wb)
        self.wb = self.spin(1000, 12000, 4500)
        camera.addRow('Beyaz dengesi (K)', self.wb)
        self.button(camera, 'Kamera ışık ayarlarını uygula', self.apply_camera_controls)

        projection = tab('Projeksiyon')
        self.screen_choice = QComboBox()
        self.screen_choice.currentIndexChanged.connect(self.output_changed)
        projection.addRow('Hedef ekran', self.screen_choice)
        self.screen_info = QLabel('')
        self.screen_info.setWordWrap(True)
        projection.addRow(self.screen_info)
        self.button(projection, 'Projeksiyonu tam ekran aç', self.show_projection)
        self.button(projection, 'Projeksiyonu gizle', self.hide_projection)
        self.overlay = QCheckBox('Başka uygulamaların üzerine çiz (şeffaf)')
        self.overlay.toggled.connect(self.overlay_changed)
        projection.addRow(self.overlay)
        platform = QGuiApplication.platformName()
        warning = QLabel('Wayland: üstte kalma ve global kısayollar garanti edilmez. Görüntü/PDF arka planını kullanın.'
                         if platform.startswith('wayland') else 'Overlay tıklamaları alttaki uygulamaya geçirir. Çizimi panel veya F8 ile yönetin.')
        warning.setWordWrap(True)
        projection.addRow(warning)
        self.button(projection, '1. Kalibrasyon hedeflerini göster', self.begin_calibration)
        self.button(projection, '2. Manuel köşe seçimini başlat', self.begin_manual)
        self.button(projection, 'Son seçilen köşeyi geri al', self.undo_corner)
        self.button(projection, '2. ArUco ile otomatik kalibre et', self.auto_calibrate)
        self.button(projection, 'Kalibrasyonu iptal et', self.cancel_calibration)
        self.button(projection, 'Kalibrasyon profili kaydet', self.save_calibration)
        self.button(projection, 'Kalibrasyon profili yükle', self.load_calibration)
        self.calibration_info = QLabel('Kalibrasyon gerekli')
        self.calibration_info.setWordWrap(True)
        projection.addRow(self.calibration_info)
        self.button(projection, '5 noktalı doğrulama başlat', self.begin_validation)
        self.button(projection, 'Hedefte 15 kare örnekle', self.sample_validation)
        self.surface_width = self.real_spin(0, 20000, 0)
        self.surface_height = self.real_spin(0, 20000, 0)
        projection.addRow('Tam yansıtılan genişlik (mm)', self.surface_width)
        projection.addRow('Tam yansıtılan yükseklik (mm)', self.surface_height)

        drawing = tab('Çizim')
        self.mode = QComboBox()
        self.mode.addItems(['Manuel', 'Sürekli', 'Deneysel temas'])
        self.mode.currentIndexChanged.connect(self.break_stroke)
        drawing.addRow('Çizim modu', self.mode)
        self.manual = QCheckBox('Çizim etkin (F8 ile aç/kapat)')
        self.manual.toggled.connect(self.break_stroke)
        drawing.addRow(self.manual)
        self.shortcut_info = QLabel('')
        self.shortcut_info.setWordWrap(True)
        drawing.addRow(self.shortcut_info)
        self.color_button = self.button(drawing, 'Mürekkep rengi: #ff3030', self.choose_color)
        self.brush = self.real_spin(1, 100, 5)
        self.brush.valueChanged.connect(self.brush_changed)
        drawing.addRow('Kalınlık (projeksiyon px)', self.brush)
        self.eraser = QCheckBox('Silgi')
        self.eraser.toggled.connect(self.brush_changed)
        drawing.addRow(self.eraser)
        self.button(drawing, 'Geri al', self.document.undo)
        self.button(drawing, 'Yinele', self.document.redo)
        self.button(drawing, 'Tüm çizimleri temizle', self.clear_document)
        self.background = QComboBox()
        self.background.addItems(['Beyaz', 'Siyah', 'Özel renk', 'Kareli', 'Çizgili'])
        self.background.currentTextChanged.connect(self.background_changed)
        drawing.addRow('Zemin', self.background)
        self.button(drawing, 'Özel zemin rengi', self.choose_background)
        self.button(drawing, 'Görüntü veya PDF aç', self.open_content)
        self.pdf_page = self.spin(1, 10000, 1)
        self.pdf_page.valueChanged.connect(self.pdf_page_changed)
        drawing.addRow('PDF sayfası', self.pdf_page)
        self.button(drawing, 'Arka plan içeriğini kaldır', self.clear_content)
        self.button(drawing, 'PNG dışa aktar', lambda: self.export_png(False))
        self.button(drawing, 'Şeffaf PNG dışa aktar', lambda: self.export_png(True))
        self.button(drawing, 'Oturumu kaydet', self.save_session)
        self.button(drawing, 'Oturumu yükle', self.load_session)

        advanced = tab('Gelişmiş')
        self.min_area = self.real_spin(1, 100000, 25)
        self.max_area = self.real_spin(1, 1000000, 15000)
        self.kernel = self.spin(1, 15, 3)
        self.max_speed = self.real_spin(1, 20000, 1800)
        self.max_lost = self.real_spin(0, 3, .25)
        self.offset_x = self.real_spin(-1000, 1000, 0)
        self.offset_y = self.real_spin(-1000, 1000, 0)
        for name, widget in [('Minimum alan (kamera px²)', self.min_area), ('Maksimum alan', self.max_area),
                             ('Morfoloji çekirdeği', self.kernel), ('Takip hızı sınırı (px/s)', self.max_speed),
                             ('Kimlik koruma kayıp süresi (s)', self.max_lost), ('Uç ofseti X (kamera px)', self.offset_x),
                             ('Uç ofseti Y', self.offset_y)]:
            advanced.addRow(name, widget)
            widget.valueChanged.connect(self.tracking_changed)
        self.smoothing = QCheckBox('Adaptif yumuşatma')
        self.smoothing.setChecked(True)
        self.smoothing.toggled.connect(self.break_stroke)
        advanced.addRow(self.smoothing)
        self.cutoff = self.real_spin(.1, 30, 1.5)
        self.beta = self.real_spin(0, 1, .02)
        advanced.addRow('One Euro min cutoff (Hz)', self.cutoff)
        advanced.addRow('One Euro beta', self.beta)
        self.contact_speed = self.real_spin(1, 10000, 700)
        advanced.addRow('Deneysel temas hız sınırı (px/s)', self.contact_speed)
        self.actual_contact = QCheckBox('Gerçek temas var (elle etiket)')
        self.record_contact = QCheckBox('Temas etiketlerini kare başına kaydet')
        advanced.addRow(self.actual_contact)
        advanced.addRow(self.record_contact)
        self.button(advanced, 'Temas ölçümlerini sıfırla', self.reset_metrics)
        self.button(advanced, 'Tanılama ve hata raporu kaydet', self.export_diagnostics)
        note = QLabel('Tek RGB kamera teması kesin ölçmez. Deneysel mod yalnızca hareket hızına dayanır. Kayıp her zaman çizgiyi keser; kayıp süresi çizgi birleştirme süresi değildir.')
        note.setWordWrap(True)
        advanced.addRow(note)
        self.setCentralWidget(root)
        self.statusBar().showMessage('Hazır — kamera veya simülasyon başlatın.')

    @staticmethod
    def button(form, label, callback):
        button = QPushButton(label)
        button.clicked.connect(callback)
        form.addRow(button)
        return button

    @staticmethod
    def spin(minimum, maximum, value):
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setValue(value)
        return widget

    @staticmethod
    def real_spin(minimum, maximum, value):
        widget = QDoubleSpinBox()
        widget.setDecimals(3)
        widget.setRange(minimum, maximum)
        widget.setValue(value)
        return widget

    def error(self, message: str) -> None:
        QMessageBox.warning(self, 'Projection Pen', message)

    def notify(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def break_stroke(self, *args) -> None:
        self.document.end()
        self.filter.reset()
        self.contact.reset()

    def toggle_manual(self) -> None:
        self.manual.setChecked(not self.manual.isChecked())

    def tracking_config(self) -> TrackingConfig:
        return TrackingConfig(tuple(w.value() for w in self.hsv[:3]), tuple(w.value() for w in self.hsv[3:]),
                              self.min_area.value(), self.max_area.value(), self.kernel.value(),
                              self.max_speed.value(), self.max_lost.value(), (self.offset_x.value(), self.offset_y.value()))

    def tracking_changed(self, *args) -> None:
        self.break_stroke()
        if self.pipeline:
            self.pipeline.configure(self.tracking_config(), self.calibration.surface_points if self.calibration else None)

    def refresh_cameras(self) -> None:
        # Enumeration may open devices on Windows, so run it outside the GUI loop.
        from threading import Thread
        from .camera import LatestSlot
        self.camera_scan = LatestSlot()
        def scan():
            try:
                self.camera_scan.put(available_cameras())
            except Exception as exc:
                self.camera_scan.put(str(exc))
        Thread(target=scan, daemon=True).start()
        self.notify('Kameralar aranıyor…')

    def open_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Takip videosu', '', 'Video (*.mp4 *.avi *.mkv *.mov);;Tümü (*)')
        if path:
            self.start_camera(source=path)

    def start_camera(self, source=None, simulate: bool = False) -> None:
        if source is None:
            value = self.camera_choice.currentData()
            text = self.camera_choice.currentText().strip()
            source = int(text) if text.isdecimal() else value
            if not isinstance(source, int):
                self.error('USB kamera indeksi girin (örneğin 0).')
                return
        self.stop_camera()
        self.retired_pipelines = [p for p in self.retired_pipelines if any(t.is_alive() for t in p.threads)]
        if self.retired_pipelines:
            self.error('Önceki kamera sürücüsü henüz kapanmadı. Biraz bekleyin; sürerse uygulamayı yeniden başlatın.')
            return
        self.last_track_id = None
        self.invalidate_calibration('Yeni kamera oturumu; kalibrasyon yapın veya profil yükleyin.')
        self.generation += 1
        self.source_id = 'simulation' if simulate else str(source)
        width, height = map(int, self.resolution.currentText().split('x'))
        self.pipeline = CameraPipeline(source, width, height, self.fps.value(), self.generation, simulate)
        self.last_result, self.last_frame, self.camera_size = None, None, None
        self.last_sequence = -1
        self.tracking_changed()
        self.pipeline.start()
        if simulate:
            self.calibration = Calibration(targets(width, height), targets(self.document.width, self.document.height),
                                           (width, height), (self.document.width, self.document.height),
                                           self.source_id, self.screen_signature(), (self.offset_x.value(), self.offset_y.value()))
            self.calibration_info.setText('Simülasyon eşlemesi etkin — fiziksel kalibrasyon değildir.')
            self.tracking_changed()
        self.notify('Kamera başlatılıyor…')

    def stop_camera(self) -> None:
        self.break_stroke()
        self.sampling_validation = False
        if self.pipeline:
            if not self.pipeline.stop():
                self.retired_pipelines.append(self.pipeline)
            self.pipeline = None
        self.projection.cursor = None
        self.projection.update()
        self.notify('Kamera durduruldu.')

    def apply_camera_controls(self) -> None:
        if not self.pipeline:
            self.error('Önce kamerayı başlatın.')
            return
        # V4L2: 0.75 auto, 0.25 manual. DirectShow commonly uses 1/0.
        import sys
        auto = (1 if self.auto_exposure.isChecked() else 0) if sys.platform == 'win32' else (.75 if self.auto_exposure.isChecked() else .25)
        values = [(cv2.CAP_PROP_AUTO_EXPOSURE, auto), (cv2.CAP_PROP_AUTO_WB, float(self.auto_wb.isChecked()))]
        if not self.auto_exposure.isChecked():
            values.append((cv2.CAP_PROP_EXPOSURE, self.exposure.value()))
        if not self.auto_wb.isChecked():
            values.append((cv2.CAP_PROP_WB_TEMPERATURE, self.wb.value()))
        self.pipeline.camera_controls.put(values)

    def selected_screen(self):
        screens = QGuiApplication.screens()
        index = self.screen_choice.currentIndex()
        return screens[index] if 0 <= index < len(screens) else None

    def screen_signature(self) -> str:
        screen = self.selected_screen()
        if not screen:
            return ''
        g = screen.geometry()
        return f'{screen.name()}|{g.x()},{g.y()},{g.width()},{g.height()}|{screen.devicePixelRatio():.3f}'

    def refresh_screens(self) -> None:
        previous = self.screen_choice.currentText()
        self.screen_choice.blockSignals(True)
        self.screen_choice.clear()
        screens = QGuiApplication.screens()
        for screen in screens:
            self.screen_choice.addItem(screen.name())
            if id(screen) not in self._screen_connections:
                screen.geometryChanged.connect(self.screens_changed)
                screen.logicalDotsPerInchChanged.connect(self.screens_changed)
                self._screen_connections.add(id(screen))
        index = self.screen_choice.findText(previous)
        self.screen_choice.setCurrentIndex(index if index >= 0 else max(0, len(screens)-1))
        self.screen_choice.blockSignals(False)
        self.output_changed()

    def screens_changed(self, *args) -> None:
        self.hide_projection()
        self.invalidate_calibration('Ekran düzeni değişti; yeniden kalibrasyon gerekli.')
        self.refresh_screens()

    def output_changed(self, *args) -> None:
        screen = self.selected_screen()
        if not screen:
            return
        g, dpr = screen.geometry(), screen.devicePixelRatio()
        width, height = round(g.width()*dpr), round(g.height()*dpr)
        self.document.resize_canvas(width, height)
        self.screen_info.setText(f'{width} × {height} fiziksel px · ölçek {dpr:.2f} · {QGuiApplication.platformName()}')
        self.invalidate_calibration('Ekran seçimi değişti; kalibrasyon gerekli.')
        if self.projection.isVisible():
            self.projection.present(screen)

    def show_projection(self) -> None:
        screen = self.selected_screen()
        if screen:
            self.projection.present(screen)
            self.notify('Projeksiyon açık. Aynı ekranda çalışıyorsanız Alt+Tab ile panele dönün; Esc projeksiyonu gizler.')

    def hide_projection(self) -> None:
        self.projection.hide()
        self.projection_hidden()

    def projection_hidden(self) -> None:
        self.manual.setChecked(False)
        self.break_stroke()
        self.cancel_calibration()
        self.validation_index = None
        self.sampling_validation = False
        self.projection.validation_target = None

    def overlay_changed(self, enabled: bool) -> None:
        self.break_stroke()
        self.projection.set_overlay(enabled)
        if self.projection.calibrating:
            self.projection.set_overlay(False)

    def invalidate_calibration(self, reason: str) -> None:
        self.calibration = None
        self.break_stroke()
        self.validation_index = None
        self.sampling_validation = False
        self.projection.validation_target = None
        self.calibration_info.setText(reason)
        if self.pipeline:
            self.pipeline.configure(self.tracking_config(), None)

    def begin_calibration(self) -> None:
        if self.pipeline is None or self.last_frame is None:
            self.error('Önce kamerayı başlatıp canlı görüntü alın.')
            return
        self.invalidate_calibration('Hedefler açık. Manuel veya otomatik seçim yapın.')
        self.collecting = False
        self.preview.points.clear()
        self.projection.calibrating = True
        self.projection.set_overlay(False)
        self.show_projection()

    def begin_manual(self) -> None:
        if not self.projection.calibrating or self.last_frame is None:
            self.error('Önce kalibrasyon hedeflerini gösterin.')
            return
        self.frozen_frame = self.last_frame.copy()
        self.preview.image = frame_image(self.frozen_frame)
        self.preview.points = []
        self.preview.update()
        self.collecting = True
        self.calibration_info.setText('Görüntü donduruldu. Hedef merkezlerini sırayla seçin: sol üst, sağ üst, sağ alt, sol alt.')

    def undo_corner(self) -> None:
        if self.collecting and self.preview.points:
            self.preview.points.pop()
            self.preview.update()

    def preview_clicked(self, x: float, y: float) -> None:
        if self.collecting:
            self.preview.points.append((x, y))
            self.preview.update()
            if len(self.preview.points) == 4:
                self.finish_calibration(np.array(self.preview.points))
            return
        if self.sample_color.isChecked() and self.last_frame is not None:
            lo, hi = sample_hsv(self.last_frame, (round(x), round(y)))
            for widget, value in zip(self.hsv, (*lo, *hi)):
                widget.blockSignals(True)
                widget.setValue(value)
                widget.blockSignals(False)
            self.tracking_changed()
            self.sample_color.setChecked(False)
            self.notify(f'Renk örneklendi: HSV {lo} – {hi}')

    def auto_calibrate(self) -> None:
        if not self.projection.calibrating or self.last_frame is None:
            self.error('Önce hedefleri gösterin; kamerada dört hedef görünmeli.')
            return
        try:
            self.finish_calibration(detect_markers(self.last_frame))
        except (ValueError, cv2.error) as exc:
            self.error(str(exc))

    def finish_calibration(self, points: np.ndarray) -> None:
        try:
            if self.camera_size is None:
                raise ValueError('Kamera boyutu bilinmiyor.')
            self.calibration = Calibration(points, targets(self.document.width, self.document.height), self.camera_size,
                                           (self.document.width, self.document.height), self.source_id,
                                           self.screen_signature(), (self.offset_x.value(), self.offset_y.value()))
        except ValueError as exc:
            self.preview.points = []
            self.error(str(exc))
            return
        self.cancel_calibration()
        self.tracking_changed()
        self.calibration_info.setText('Kalibrasyon etkin. Bağımsız 5 noktalı doğrulamayı çalıştırın.')

    def cancel_calibration(self) -> None:
        self.collecting = False
        self.frozen_frame = None
        self.preview.points = []
        self.preview.update()
        self.projection.calibrating = False
        self.projection.set_overlay(self.overlay.isChecked())
        self.projection.update()
        self.break_stroke()

    def save_calibration(self) -> None:
        if not self.calibration:
            self.error('Kaydedilecek kalibrasyon yok.')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Kalibrasyon profili', '', 'JSON (*.json)')
        if path:
            try:
                self.calibration.offset = (self.offset_x.value(), self.offset_y.value())
                self.calibration.save(Path(path))
            except (OSError, ValueError) as exc:
                self.error(str(exc))

    def load_calibration(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Kalibrasyon profili', '', 'JSON (*.json)')
        if not path:
            return
        try:
            calibration = Calibration.load(Path(path))
            if (tuple(calibration.camera_size) != self.camera_size or tuple(calibration.output_size) != (self.document.width, self.document.height)
                or calibration.camera_id != self.source_id or calibration.screen_id != self.screen_signature()):
                raise ValueError('Profil kamera/ekran düzeniyle eşleşmiyor. Kamerayı başlatın veya yeniden kalibre edin.')
            self.calibration = calibration
            self.offset_x.setValue(calibration.offset[0])
            self.offset_y.setValue(calibration.offset[1])
            self.tracking_changed()
            self.calibration_info.setText('Profil yüklendi. Kamera fiziksel olarak taşındıysa yeniden kalibre edin.')
        except (OSError, ValueError, TypeError, KeyError, cv2.error) as exc:
            self.error(f'Profil yüklenemedi: {exc}')

    def begin_validation(self) -> None:
        if not self.calibration or self.projection.calibrating:
            self.error('Önce kalibrasyon yapın.')
            return
        self.break_stroke()
        self.validation_camera, self.validation_output = [], []
        self.validation_report = {}
        self.validation_index = 0
        # Inset from fit points: these are independent physical pen measurements.
        w, h = self.document.width, self.document.height
        self.validation_targets = [(w*.2, h*.2), (w*.8, h*.2), (w*.8, h*.8), (w*.2, h*.8), (w*.5, h*.5)]
        self.projection.validation_target = self.validation_targets[0]
        self.show_projection()
        self.projection.update()
        self.calibration_info.setText('Doğrulama 1/5: kalem ucunu hedef merkezine götürüp örnekleyin.')

    def sample_validation(self) -> None:
        if self.validation_index is None:
            self.error('Önce 5 noktalı doğrulamayı başlatın.')
            return
        self.validation_samples = []
        self.sampling_validation = True
        self.notify('Kalemi hedefte sabit tutun; 15 ardışık tespit bekleniyor…')

    def record_validation_point(self, point) -> None:
        if point is None:
            self.validation_samples.clear()
            return
        self.validation_samples.append(point)
        if len(self.validation_samples) < 15:
            return
        self.sampling_validation = False
        self.validation_camera.append(np.mean(self.validation_samples, axis=0).tolist())
        self.validation_output.append(self.validation_targets[self.validation_index])
        self.validation_index += 1
        if self.validation_index < 5:
            self.projection.validation_target = self.validation_targets[self.validation_index]
            self.calibration_info.setText(f'Doğrulama {self.validation_index+1}/5: sonraki hedefi örnekleyin.')
        else:
            self.validation_index = None
            self.projection.validation_target = None
            self.validation_report = self.calibration.errors(np.array(self.validation_camera), np.array(self.validation_output))
            self.validation_report.update(camera_points=self.validation_camera, output_points=self.validation_output)
            message = f"Ortalama: {self.validation_report['mean_px']:.2f} px · maksimum: {self.validation_report['max_px']:.2f} px"
            if self.surface_width.value() and self.surface_height.value():
                mapped = np.array([self.calibration.map(tuple(p), False) for p in self.validation_camera])
                delta = (mapped-np.array(self.validation_output))*[self.surface_width.value()/self.document.width, self.surface_height.value()/self.document.height]
                mm = np.linalg.norm(delta, axis=1)
                self.validation_report.update(mean_mm=float(mm.mean()), max_mm=float(mm.max()))
                message += f' · {mm.mean():.2f} / {mm.max():.2f} mm (ort./maks.)'
            self.calibration_info.setText(message)
        self.projection.update()

    def tick(self) -> None:
        if hasattr(self, 'camera_scan'):
            cameras = self.camera_scan.take()
            if cameras is not None:
                if isinstance(cameras, str):
                    self.notify(cameras)
                else:
                    self.camera_choice.clear()
                    for name, index in cameras:
                        self.camera_choice.addItem(f'{index} — {name}', index)
                    if not cameras:
                        self.camera_choice.addItem('0', 0)
                    self.notify(f'{len(cameras)} kamera aygıtı bulundu. Bazı Linux düğümleri görüntü sağlamayabilir.')
        if not self.pipeline:
            return
        error = self.pipeline.errors.take()
        if error:
            self.stop_camera()
            self.stats.setText(error)
            self.notify(error)
            return
        info = self.pipeline.info.take()
        if info:
            self.device_info.setText(info)
        result = self.pipeline.results.take()
        if result is None:
            if self.last_result and time.monotonic()-self.last_result.frame.timestamp > .25:
                self.break_stroke()
                self.projection.cursor = None
                self.projection.update()
            return
        frame, detection = result.frame, result.detection
        if (frame.generation != self.generation or frame.sequence <= self.last_sequence
                or result.config_revision != self.pipeline.revision):
            return
        if self.last_result is None:
            self.notify('Kamera akışı etkin.')
        self.last_sequence = frame.sequence
        self.last_result, self.last_frame = result, frame.image
        height, width = frame.image.shape[:2]
        size = (width, height)
        if self.camera_size is not None and size != self.camera_size:
            self.invalidate_calibration('Kamera çözünürlüğü değişti; yeniden kalibrasyon gerekli.')
            self.cancel_calibration()
        self.camera_size = size
        if self.calibration and tuple(self.calibration.camera_size) != size:
            self.invalidate_calibration('Profil kamera boyutuyla eşleşmiyor.')
        if not self.collecting:
            self.preview.image = frame_image(frame.image)
            self.preview.cursor = detection.point
            self.preview.candidates = detection.candidates if self.show_mask.isChecked() else []
            self.preview.update()
        if self.show_mask.isChecked():
            self.debug_preview.image = frame_image(cv2.cvtColor(detection.mask, cv2.COLOR_GRAY2BGR))
            self.debug_preview.update()
        age_ms = (time.monotonic()-frame.timestamp)*1000
        valid = age_ms < 250
        point = self.calibration.map(detection.point) if self.calibration and detection.point and valid else None
        fresh_track = detection.new_track or detection.track_id != self.last_track_id
        self.last_track_id = detection.track_id
        if fresh_track or point is None:
            self.break_stroke()
        self.filter.min_cutoff, self.filter.beta = self.cutoff.value(), self.beta.value()
        self.contact.speed_threshold = self.contact_speed.value()
        self.predicted_contact = self.contact.update(point, frame.timestamp) if point is not None else False
        if self.record_contact.isChecked():
            self.contact_metrics.add(self.predicted_contact, self.actual_contact.isChecked())
        if self.sampling_validation and self.validation_index is not None:
            self.record_validation_point(detection.point if valid else None)
        filtered = self.filter.apply(point, frame.timestamp) if point and self.smoothing.isChecked() else point
        mode = self.mode.currentIndex()
        enabled = (mode == 1 or (mode == 0 and self.manual.isChecked()) or (mode == 2 and self.predicted_contact))
        enabled = enabled and self.projection.isVisible() and not self.projection.calibrating and self.validation_index is None
        self.document.feed(filtered, enabled, fresh_track)
        self.projection.cursor = filtered
        self.projection.update()
        location = 'yok' if point is None else f'{point[0]:.1f}, {point[1]:.1f}'
        self.stats.setText(f'{result.fps:.1f} işlenen FPS · {result.processing_ms:.1f} ms işleme · {age_ms:.1f} ms yazılım yaşı\n'
                           f'Kalem: {location} · aday: {len(detection.candidates)} · temas tahmini: {self.predicted_contact}')
        self.diagnostics.append({'sequence': frame.sequence, 'time': frame.timestamp, 'fps': result.fps,
                                 'processing_ms': result.processing_ms, 'software_age_ms': age_ms,
                                 'point': point, 'candidates': len(detection.candidates), 'contact': self.predicted_contact})

    def brush_changed(self, *args) -> None:
        self.break_stroke()
        self.document.brush_width = self.brush.value()
        self.document.eraser = self.eraser.isChecked()

    def choose_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.document.color), self, 'Dijital mürekkep')
        if color.isValid():
            self.break_stroke()
            self.document.color = color.name()
            self.color_button.setText(f'Mürekkep rengi: {color.name()}')
            pixel = np.array([[[color.blue(), color.green(), color.red()]]], np.uint8)
            hsv = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)[0, 0]
            lower, upper = self.tracking_config().lower, self.tracking_config().upper
            hue_matches = lower[0] <= hsv[0] <= upper[0] if lower[0] <= upper[0] else hsv[0] >= lower[0] or hsv[0] <= upper[0]
            if hue_matches and lower[1] <= hsv[1] <= upper[1] and lower[2] <= hsv[2] <= upper[2]:
                self.notify('Uyarı: mürekkep takip renginde. Projeksiyon fiziksel kalemle karışabilir.')

    def background_changed(self, text: str) -> None:
        self.document.background = text
        if text == 'Beyaz':
            self.document.background_color = '#ffffff'
        elif text == 'Siyah':
            self.document.background_color = '#000000'
        self.document.changed.emit()

    def choose_background(self) -> None:
        color = QColorDialog.getColor(QColor(self.document.background_color), self, 'Zemin rengi')
        if color.isValid():
            self.background.setCurrentText('Özel renk')
            self.document.background_color = color.name()
            self.document.changed.emit()

    def clear_document(self) -> None:
        if QMessageBox.question(self, 'Çizimleri temizle', 'Tüm çizimler silinsin mi? Bu işlem geri alınamaz.') == QMessageBox.StandardButton.Yes:
            self.document.clear()

    def open_content(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Arka plan içeriği', '', 'İçerik (*.png *.jpg *.jpeg *.bmp *.webp *.pdf)')
        if path:
            try:
                self.set_content(path, 0)
                self.overlay.setChecked(False)
                self.pdf_page.setValue(1)
            except (ValueError, OSError) as exc:
                self.error(str(exc))

    def set_content(self, path: str, page: int = 0) -> None:
        if not Path(path).is_file():
            raise ValueError('Arka plan dosyası bulunamadı. Oturum dosyası içeriği gömmez; dosyayı yeniden seçin.')
        if path.lower().endswith('.pdf'):
            pdf = QPdfDocument(self)
            try:
                error = pdf.load(path)
                if error != QPdfDocument.Error.None_ or not 0 <= page < pdf.pageCount():
                    raise ValueError('PDF açılamadı veya sayfa geçersiz (şifreli PDF desteklenmez).')
                from PySide6.QtCore import QSize
                image = pdf.render(page, QSize(self.document.width, self.document.height))
                if image.isNull():
                    raise ValueError('PDF sayfası oluşturulamadı.')
                self.pdf_page.setMaximum(pdf.pageCount())
            finally:
                pdf.close()
                pdf.deleteLater()
        else:
            from PySide6.QtGui import QImageReader
            reader = QImageReader(path)
            size = reader.size()
            if size.isValid():
                reader.setScaledSize(size.scaled(self.document.width, self.document.height, Qt.AspectRatioMode.KeepAspectRatio))
            image = reader.read()
            if image.isNull():
                raise ValueError('Görüntü açılamadı.')
        self.document.content = image
        self.document.content_path, self.document.content_page = path, page
        self.document.changed.emit()

    def pdf_page_changed(self, number: int) -> None:
        path = self.document.content_path
        if path and path.lower().endswith('.pdf'):
            try:
                self.set_content(path, number-1)
            except (ValueError, OSError) as exc:
                self.error(str(exc))

    def clear_content(self) -> None:
        self.document.content = QImage()
        self.document.content_path = None
        self.document.changed.emit()

    def export_png(self, transparent: bool) -> None:
        path, _ = QFileDialog.getSaveFileName(self, 'PNG dışa aktar', '', 'PNG (*.png)')
        if path:
            try:
                self.document.export_png(Path(path), transparent)
                self.notify('PNG kaydedildi.')
            except OSError as exc:
                self.error(str(exc))

    def save_session(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, 'Çizim oturumu', '', 'JSON (*.json)')
        if path:
            try:
                self.document.save(Path(path))
                self.notify('Oturum kaydedildi. Arka plan dosyası ayrı tutulur.')
            except (OSError, ValueError) as exc:
                self.error(str(exc))

    def load_session(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Çizim oturumu', '', 'JSON (*.json)')
        if not path:
            return
        self.break_stroke()
        try:
            self.document.load(Path(path))
            screen = self.selected_screen()
            if screen:
                g, dpr = screen.geometry(), screen.devicePixelRatio()
                self.document.resize_canvas(round(g.width()*dpr), round(g.height()*dpr))
            self.background.setCurrentText(self.document.background)
            if self.document.content_path:
                self.set_content(self.document.content_path, self.document.content_page)
            self.notify('Oturum yüklendi.')
        except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
            self.error(f'Oturum yüklenemedi veya arka plan eksik: {exc}')

    def reset_metrics(self) -> None:
        self.contact_metrics = ContactMetrics()
        self.notify('Temas ölçümleri sıfırlandı.')

    def export_diagnostics(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, 'Tanılama raporu', '', 'JSON (*.json)')
        if path:
            try:
                write_json(Path(path), {'version': 1, 'platform': QGuiApplication.platformName(),
                                       'contact': self.contact_metrics.report(), 'validation': self.validation_report,
                                       'frames': list(self.diagnostics),
                                       'note': 'software_age_ms excludes camera exposure, driver buffering and projector latency'})
                self.notify('Tanılama raporu kaydedildi.')
            except (OSError, ValueError) as exc:
                self.error(str(exc))

    def persisted_widgets(self) -> dict:
        names = ['fps', 'brush', 'min_area', 'max_area', 'kernel', 'max_speed', 'max_lost', 'offset_x', 'offset_y',
                 'cutoff', 'beta', 'contact_speed', 'surface_width', 'surface_height', 'exposure', 'wb']
        return {name: getattr(self, name) for name in names} | {f'hsv_{i}': widget for i, widget in enumerate(self.hsv)}

    def restore_settings(self) -> None:
        path = self.config_dir/'settings.json'
        if not path.exists():
            return
        try:
            data = read_json(path)
            for name, widget in self.persisted_widgets().items():
                if name in data:
                    widget.setValue(data[name])
            self.resolution.setCurrentText(data.get('resolution', '1280x720'))
            self.camera_choice.setEditText(str(data.get('camera', '0')))
            color = data.get('color', '#ff3030')
            if QColor(color).isValid():
                self.document.color = color
                self.color_button.setText(f'Mürekkep rengi: {color}')
            self.background.setCurrentText(data.get('background', 'Beyaz'))
            color = data.get('background_color', '#ffffff')
            if QColor(color).isValid():
                self.document.background_color = color
            self.smoothing.setChecked(bool(data.get('smoothing', True)))
            self.mode.setCurrentIndex(max(0, min(2, int(data.get('mode', 0)))))
            # Never restore an armed manual gate, experimental mode, or active overlay.
            if self.mode.currentIndex() == 2:
                self.mode.setCurrentIndex(0)
        except (OSError, ValueError, TypeError, OverflowError) as exc:
            self.notify(f'Ayarlar okunamadı; varsayılanlar kullanılıyor: {exc}')

    def closeEvent(self, event) -> None:
        self.timer.stop()
        self.stop_camera()
        self.global_toggle.close()
        self.projection.close()
        data = {name: widget.value() for name, widget in self.persisted_widgets().items()}
        data.update(version=1, resolution=self.resolution.currentText(), camera=self.camera_choice.currentText().split(' — ')[0],
                    color=self.document.color, background=self.document.background,
                    background_color=self.document.background_color, smoothing=self.smoothing.isChecked(), mode=self.mode.currentIndex())
        try:
            write_json(self.config_dir/'settings.json', data)
        except (OSError, ValueError) as exc:
            self.error(f'Ayarlar kaydedilemedi: {exc}')
        event.accept()
