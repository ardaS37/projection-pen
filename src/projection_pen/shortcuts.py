"""Optional native global F8: Windows RegisterHotKey, X11 passive key grab.

No global key hook is attempted under Wayland. Linux libX11 is loaded lazily.
"""
from __future__ import annotations

import ctypes
import os
import sys
from PySide6.QtCore import QAbstractNativeEventFilter, QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication


class _WindowsFilter(QAbstractNativeEventFilter):
    def __init__(self, callback) -> None:
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, event_type, message):
        from ctypes.wintypes import MSG
        msg = MSG.from_address(int(message))
        if msg.message == 0x0312 and msg.wParam == 0x50A1:
            self.callback()
            return True, 0
        return False, 0


class GlobalToggle(QObject):
    toggled = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.status = 'Global F8 yok; panel düğmesi veya odak içi F8 kullanın.'
        self.display = None
        self.filter = None
        self.timer = QTimer(self)
        if sys.platform == 'win32':
            if ctypes.windll.user32.RegisterHotKey(None, 0x50A1, 0x4000, 0x77):
                self.filter = _WindowsFilter(self.toggled.emit)
                QGuiApplication.instance().installNativeEventFilter(self.filter)
                self.status = 'Global F8 etkin (Windows).'
            return
        if QGuiApplication.platformName() != 'xcb' or not os.environ.get('DISPLAY'):
            return
        try:
            self.xlib = ctypes.CDLL('libX11.so.6')
            x = self.xlib
            x.XOpenDisplay.argtypes, x.XOpenDisplay.restype = [ctypes.c_char_p], ctypes.c_void_p
            x.XDefaultRootWindow.argtypes, x.XDefaultRootWindow.restype = [ctypes.c_void_p], ctypes.c_ulong
            x.XKeysymToKeycode.argtypes, x.XKeysymToKeycode.restype = [ctypes.c_void_p, ctypes.c_ulong], ctypes.c_uint
            x.XGrabKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int]
            x.XUngrabKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong]
            x.XPending.argtypes = [ctypes.c_void_p]
            x.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            x.XCloseDisplay.argtypes = [ctypes.c_void_p]
            x.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
            self.display = x.XOpenDisplay(None)
            if not self.display:
                return
            self.root = x.XDefaultRootWindow(self.display)
            self.keycode = x.XKeysymToKeycode(self.display, 0xFFC5)  # XK_F8
            errors = []
            callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
            callback = callback_type(lambda display, error: errors.append(True) or 0)
            x.XSetErrorHandler.argtypes, x.XSetErrorHandler.restype = [ctypes.c_void_p], ctypes.c_void_p
            previous = x.XSetErrorHandler(ctypes.cast(callback, ctypes.c_void_p))
            for modifiers in (0, 2, 16, 18):  # CapsLock / NumLock
                x.XGrabKey(self.display, self.keycode, modifiers, self.root, False, 1, 1)
            x.XSync(self.display, False)
            x.XSetErrorHandler(previous)
            if errors:
                self.close()
                self.status = 'F8 başka uygulamaya ayrılmış; panel düğmesini kullanın.'
                return
            self.key_down = False
            if hasattr(x, 'XkbSetDetectableAutoRepeat'):
                x.XkbSetDetectableAutoRepeat.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
                x.XkbSetDetectableAutoRepeat(self.display, True, None)
            self.timer.timeout.connect(self.poll)
            self.timer.start(20)
            self.status = 'Global F8 etkin (X11).'
        except (OSError, AttributeError):
            self.close()

    def poll(self) -> None:
        # XEvent union is 24 longs on both 32 and 64 bit Xlib.
        event = (ctypes.c_long * 24)()
        while self.display and self.xlib.XPending(self.display):
            self.xlib.XNextEvent(self.display, ctypes.byref(event))
            event_type = ctypes.cast(ctypes.byref(event), ctypes.POINTER(ctypes.c_int))[0]
            if event_type == 2 and not self.key_down:
                self.key_down = True
                self.toggled.emit()
            elif event_type == 3:
                self.key_down = False

    def close(self) -> None:
        self.timer.stop()
        if self.display:
            for modifiers in (0, 2, 16, 18):
                self.xlib.XUngrabKey(self.display, self.keycode, modifiers, self.root)
            self.xlib.XCloseDisplay(self.display)
            self.display = None
        if self.filter:
            QGuiApplication.instance().removeNativeEventFilter(self.filter)
            ctypes.windll.user32.UnregisterHotKey(None, 0x50A1)
            self.filter = None
