"""Preserve Windows window behavior beneath the app's custom Qt Quick frame."""
import ctypes
import os
import sys
from ctypes import wintypes
from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QColor


class _Margins(ctypes.Structure):
    _fields_ = [(name, ctypes.c_int) for name in ('left', 'right', 'top', 'bottom')]


class _MonitorInfo(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('monitor', wintypes.RECT),
                ('work', wintypes.RECT), ('flags', wintypes.DWORD)]


class WindowChrome(QObject):
    def __init__(self, window, controller, themes):
        super().__init__(window)
        self.window, self.controller, self.themes = window, controller, themes
        self.last_color = None
        self.supported = os.name == 'nt'
        self.rounded_supported = self.supported and sys.getwindowsversion().build >= 22000
        self._updating = False
        self._extended_hwnd = None
        if not self.supported:
            return
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self.user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        self.user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        self.user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        self.user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        self.user32.SetWindowPos.restype = ctypes.c_int
        self.user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user32.GetWindowRect.restype = wintypes.BOOL
        self.user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        self.user32.MonitorFromWindow.restype = wintypes.HANDLE
        self.user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MonitorInfo)]
        self.user32.GetMonitorInfoW.restype = wintypes.BOOL
        self.dwm = ctypes.WinDLL('dwmapi')
        self.dwm.DwmSetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        self.dwm.DwmSetWindowAttribute.restype = ctypes.c_long
        self.dwm.DwmExtendFrameIntoClientArea.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Margins)]
        self.dwm.DwmExtendFrameIntoClientArea.restype = ctypes.c_long
        controller.changed.connect(self.update)
        window.visibleChanged.connect(lambda: self.update(force=True))
        window.activeChanged.connect(lambda: self.update(force=True))
        window.flagsChanged.connect(lambda: self.update(force=True))
        window.windowStateChanged.connect(lambda: self.update(force=True))
        self.update(force=True)

    def update(self, force=False):
        if not self.supported or self.controller.closing or self._updating:
            return
        if self.window.flags() & Qt.FramelessWindowHint:
            self._update_custom_frame(force)
            return
        if not self.rounded_supported:
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

    def _update_custom_frame(self, force):
        # Qt 6's Windows backend consumes WM_NCCALCSIZE for frameless windows,
        # keeps their client area at the full window size and supplies monitor
        # work-area limits on maximize. Retain native capability bits so the OS
        # can still provide Snap, minimize/maximize and an ordinary system menu.
        # All content hit testing and resize edges remain in Qt Quick; no native
        # caption/resize hit-test region can steal presses from app controls.
        self._updating = True
        try:
            hwnd = int(self.window.winId())
            style = self.user32.GetWindowLongPtrW(hwnd, -16)  # GWL_STYLE
            expanded = bool(self.window.windowState() & (Qt.WindowMaximized | Qt.WindowFullScreen))
            desired = style | 0x00080000 | 0x00020000 | 0x00010000
            if expanded:
                # A native sizing frame expands maximized popup bounds past the
                # monitor's work area. It is unnecessary in either expanded
                # state, and returns automatically when the window is restored.
                desired &= ~0x00C40000
            else:
                desired |= 0x00C40000  # WS_CAPTION | WS_THICKFRAME
            if desired != style:
                ctypes.set_last_error(0)
                result = self.user32.SetWindowLongPtrW(hwnd, -16, desired)
                if result == 0 and ctypes.get_last_error():
                    return
                # SWP_NOSIZE | NOMOVE | NOZORDER | NOACTIVATE | FRAMECHANGED
                self.user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0037)
            if self.window.windowState() & Qt.WindowMaximized:
                monitor = self.user32.MonitorFromWindow(hwnd, 2)  # nearest
                info, actual = _MonitorInfo(), wintypes.RECT()
                info.size = ctypes.sizeof(info)
                if (self.user32.GetMonitorInfoW(monitor, ctypes.byref(info))
                        and self.user32.GetWindowRect(hwnd, ctypes.byref(actual))):
                    work = info.work
                    if tuple((actual.left, actual.top, actual.right, actual.bottom)) != tuple((work.left, work.top, work.right, work.bottom)):
                        self.user32.SetWindowPos(hwnd, None, work.left, work.top,
                                                 work.right - work.left, work.bottom - work.top, 0x0014)
            if self._extended_hwnd != hwnd:
                # One physical pixel requests the DWM shadow without adding a
                # visible title bar or a second surface behind the Qt controls.
                margins = _Margins(1, 1, 1, 1)
                if self.dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins)) >= 0:
                    self._extended_hwnd = hwnd
            if self.rounded_supported and (force or desired != style):
                for attribute, setting in ((33, 2), (34, 0xFFFFFFFE)):
                    value = ctypes.c_uint32(setting)  # ROUND; COLOR_NONE
                    self.dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
        finally:
            self._updating = False
