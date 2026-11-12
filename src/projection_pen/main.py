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
    args = parser.parse_args()
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
