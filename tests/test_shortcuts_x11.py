"""Run under xvfb-run with QT_QPA_PLATFORM=xcb to exercise actual passive grabs."""
import ctypes
import time
import pytest
from PySide6.QtGui import QGuiApplication
from projection_pen.shortcuts import GlobalToggle


def test_global_f8_grab_release_and_repeat(app):
    if QGuiApplication.platformName() != 'xcb':
        pytest.skip('Native X11 integration requires an X server and QT_QPA_PLATFORM=xcb')
    toggle = GlobalToggle()
    assert toggle.status == 'Global F8 etkin (X11).'
    events = []
    toggle.toggled.connect(lambda: events.append(True))
    xlib = toggle.xlib
    xtest = ctypes.CDLL('libXtst.so.6')
    xtest.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    xlib.XFlush.argtypes = [ctypes.c_void_p]
    emitter = xlib.XOpenDisplay(None)
    assert emitter

    def emit(down):
        xtest.XTestFakeKeyEvent(emitter, toggle.keycode, down, 0)
        xlib.XFlush(emitter)
        until = time.monotonic()+.15
        while time.monotonic() < until:
            app.processEvents()
            time.sleep(.003)

    try:
        emit(True)
        assert len(events) == 1
        emit(True)
        assert len(events) == 1  # repeated KeyPress must not flip the gate again
        emit(False)
        emit(True)
        assert len(events) == 2
    finally:
        emit(False)
        xlib.XCloseDisplay(emitter)
        toggle.close()
