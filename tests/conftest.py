import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('XDG_CONFIG_HOME', '/tmp/projection-pen-tests')
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope='session')
def app():
    application = QApplication.instance() or QApplication([])
    application.setApplicationName('ProjectionPenTests')
    return application
