"""Theme the native Windows 11 caption without replacing system window controls."""
import ctypes
import os
import sys
from PySide6.QtCore import QObject
from PySide6.QtGui import QColor


class WindowChrome(QObject):
    def __init__(self, window, controller, themes):
        super().__init__(window)
        self.window, self.controller, self.themes = window, controller, themes
        self.last_color = None
        self.supported = os.name == 'nt' and sys.getwindowsversion().build >= 22000
        if not self.supported:
            return  # Older Windows retains its native, functional title bar.
        self.dwm = ctypes.WinDLL('dwmapi')
        self.dwm.DwmSetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        self.dwm.DwmSetWindowAttribute.restype = ctypes.c_long
        controller.changed.connect(self.update)
        window.visibleChanged.connect(lambda: self.update(force=True))
        window.activeChanged.connect(lambda: self.update(force=True))
        self.update(force=True)

    def update(self, force=False):
        if not self.supported or self.controller.closing:
            return
        accent = QColor(self.themes[self.controller.preferences['theme']])
        # Same 13% tint over white as the UI's tonal surfaces.
        rgb = tuple(round(255 * .87 + component * .13) for component in (accent.red(), accent.green(), accent.blue()))
        caption = rgb[0] | rgb[1] << 8 | rgb[2] << 16
        if caption == self.last_color and not force:
            return
        hwnd = int(self.window.winId())
        for attribute, color in ((35, caption), (36, 0x291D21)):
            value = ctypes.c_uint32(color)
            if self.dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)) < 0:
                return
        self.last_color = caption
