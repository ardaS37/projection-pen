"""Entry point: projection-pen [--demo] [--smoke-test]."""
from __future__ import annotations

import argparse
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication


def main() -> None:
    parser = argparse.ArgumentParser(description='Projection Pen — yerel interaktif projeksiyon')
    parser.add_argument('--demo', action='store_true', help='Sentetik yeşil işaretleyiciyle başlat')
    parser.add_argument('--smoke-test', action='store_true', help='Simülasyonu aç, 2 saniye sonra çık')
    parser.add_argument('--list-cameras', action='store_true', help='Sistemde listelenen kameraları ve yöntemlerini göster')
    args = parser.parse_args()
    if args.list_cameras:
        import json
        from dataclasses import asdict
        from .camera_devices import available_cameras
        try:
            print(json.dumps([asdict(device) for device in available_cameras()], ensure_ascii=False, indent=2))
        except Exception as exc:
            parser.exit(1, f'Kamera listesi alınamadı: {exc}\n')
        return
    app = QApplication(sys.argv[:1])
    app.setApplicationName('ProjectionPen')
    app.setOrganizationName('ProjectionPen')
    app.setStyle('Fusion')
    app.setStyleSheet('''
        QWidget { background: #1b2330; color: #e4eaf3; font-size: 12px; }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #111925; padding: 5px; border: 1px solid #3c4c63; border-radius: 4px; }
        QPushButton { background: #29394e; padding: 8px; border: 1px solid #405674; border-radius: 5px; }
        QPushButton:hover { background: #364f6c; }
        QPushButton:pressed { background: #1679a8; }
        QTabBar::tab { padding: 9px; }
        QTabBar::tab:selected { background: #245778; }
        QCheckBox { padding: 5px 0; }
        QStatusBar { background: #111925; }
    ''')
    from .gui import MainWindow
    window = MainWindow(demo=args.demo or args.smoke_test)
    window.show()
    if args.smoke_test:
        QTimer.singleShot(400, window.show_projection)
        QTimer.singleShot(700, lambda: window.mode.setCurrentIndex(1))
        QTimer.singleShot(2000, window.close)
    sys.exit(app.exec())
