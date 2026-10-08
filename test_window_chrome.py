"""Exercise the real Windows frameless HWND and Qt window controls, offline."""
import ctypes
from ctypes import wintypes
import tempfile
from pathlib import Path
import threading
import time

from PySide6.QtCore import QPointF, Qt
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QSystemTrayIcon

from qt_ui import THEMES, create_application, read_preferences


class _MouseInput(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('data', wintypes.DWORD),
                ('flags', wintypes.DWORD), ('time', wintypes.DWORD), ('extra', ctypes.c_size_t)]


class _InputUnion(ctypes.Union):
    _fields_ = [('mouse', _MouseInput)]


class _Input(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('value', _InputUnion)]


def main():
    with tempfile.TemporaryDirectory() as temp:
        app, engine, controller, window = create_application(Path(temp) / 'preferences.json')
        try:
            controller.setPreference('motion', False)
            QTest.qWait(250)
            chrome = window.chrome
            assert chrome.supported
            assert window.flags() & Qt.FramelessWindowHint
            user32, hwnd = chrome.user32, int(window.winId())
            user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            user32.GetClientRect.restype = wintypes.BOOL
            user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
            user32.ClientToScreen.restype = wintypes.BOOL
            user32.GetSystemMenu.argtypes = [wintypes.HWND, wintypes.BOOL]
            user32.GetSystemMenu.restype = wintypes.HMENU
            user32.GetMenuItemCount.argtypes = [wintypes.HMENU]
            user32.GetMenuItemCount.restype = ctypes.c_int
            user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user32.SendMessageW.restype = ctypes.c_ssize_t
            user32.IsIconic.argtypes = [wintypes.HWND]
            user32.IsIconic.restype = wintypes.BOOL
            user32.GetForegroundWindow.restype = wintypes.HWND
            user32.SetForegroundWindow.argtypes = [wintypes.HWND]
            user32.SetForegroundWindow.restype = wintypes.BOOL
            user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
            user32.SetCursorPos.restype = wintypes.BOOL
            user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_Input), ctypes.c_int]
            user32.SendInput.restype = wintypes.UINT

            def control(name):
                item = window.findChild(QQuickItem, name)
                assert item is not None, name
                return item

            def click(name):
                item = control(name)
                point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
                QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
                QTest.qWait(100)

            def full_client():
                frame, client, origin = wintypes.RECT(), wintypes.RECT(), wintypes.POINT()
                assert user32.GetWindowRect(hwnd, ctypes.byref(frame))
                assert user32.GetClientRect(hwnd, ctypes.byref(client))
                assert user32.ClientToScreen(hwnd, ctypes.byref(origin))
                assert (origin.x, origin.y) == (frame.left, frame.top), 'A native caption/border took client space'
                assert (frame.right - frame.left, frame.bottom - frame.top) == (client.right, client.bottom)
                return frame, client

            def native_pointer(x, y, delta=None, clicks=1):
                # Native system move/resize enters a Windows modal loop. Drive
                # its matching physical release from a helper thread so the GUI
                # thread remains inside Qt/Windows event handling throughout.
                window.raise_()
                window.requestActivate()
                user32.SetForegroundWindow(hwnd)
                QTest.qWait(70)
                assert user32.GetForegroundWindow() == hwnd, 'Native input target is not this test window'
                errors = []
                def send(flags):
                    value = _Input(0, _InputUnion(mouse=_MouseInput(0, 0, 0, flags, 0, 0)))
                    assert user32.SendInput(1, ctypes.byref(value), ctypes.sizeof(value)) == 1
                def drive():
                    pressed = False
                    try:
                        assert user32.GetForegroundWindow() == hwnd
                        assert user32.SetCursorPos(x, y)
                        time.sleep(.06)
                        for index in range(clicks):
                            send(0x0002)
                            pressed = True
                            time.sleep(.08)
                            if delta is not None:
                                for fraction in (.25, .5, .75, 1.):
                                    assert user32.SetCursorPos(x + round(delta[0] * fraction), y + round(delta[1] * fraction))
                                    time.sleep(.045)
                            send(0x0004)
                            pressed = False
                            if index + 1 < clicks:
                                time.sleep(.075)
                    except BaseException as exc:
                        errors.append(repr(exc))
                    finally:
                        if pressed:
                            send(0x0004)
                driver = threading.Thread(target=drive, daemon=True)
                driver.start()
                QTest.qWait(900)
                driver.join(2)
                assert not driver.is_alive() and not errors, errors

            style = user32.GetWindowLongPtrW(hwnd, -16)
            for flag in (0x00040000, 0x00080000, 0x00020000, 0x00010000):
                assert style & flag, 'Native resize/system/minimize/maximize capability was lost'
            menu = user32.GetSystemMenu(hwnd, False)
            assert menu and user32.GetMenuItemCount(menu) >= 6
            frame, client = full_client()
            assert chrome._extended_hwnd == hwnd, 'DWM shadow request failed'

            image = window.grabWindow()
            pixel_scale = image.width() / window.width()
            for name in ('minimizeButton', 'maximizeButton', 'closeWindowButton'):
                item = control(name)
                center = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
                # Keep the sample inside the glyph, away from hover/focus/ripple
                # outlines, so a blank icon cannot pass due to its decoration.
                left, upper = round((center.x() - 8) * pixel_scale), round((center.y() - 8) * pixel_scale)
                extent = round(16 * pixel_scale)
                ink = sum(max(image.pixelColor(x, y).red(), image.pixelColor(x, y).green(),
                              image.pixelColor(x, y).blue()) < 170
                          for x in range(left, left + extent) for y in range(upper, upper + extent))
                assert ink >= 8, name + ': rendered glyph is missing'

            # The native sizing/caption capability bits must not convert any
            # client control, including the outer edge strips, into a native
            # hit-test target. Qt Quick owns all app control and resize presses.
            samples = [(0, 0), (1, 20), (client.right - 1, 20),
                       (20, client.bottom - 1), (client.right // 2, 15)]
            for name in ('minimizeButton', 'maximizeButton', 'closeWindowButton', 'settingsButton'):
                item = control(name)
                position = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
                samples.append((round(position.x() * window.devicePixelRatio()),
                                round(position.y() * window.devicePixelRatio())))
            for x, y in samples:
                packed = ((frame.top + y) & 0xFFFF) << 16 | ((frame.left + x) & 0xFFFF)
                assert user32.SendMessageW(hwnd, 0x0084, 0, packed) == 1, 'Native hit test stole a client press'

            original_setter = chrome.dwm.DwmSetWindowAttribute
            calls = []
            def record(handle, attribute, pointer, size):
                result = original_setter(handle, attribute, pointer, size)
                value = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32)).contents.value
                calls.append((attribute, value, result))
                return result
            chrome.dwm.DwmSetWindowAttribute = record
            colors = []
            for theme in THEMES:
                controller.setPreference('theme', theme)
                chrome.update(force=True)
                QTest.qWait(60)
                colors.append(control('windowBar').property('color').name())
                if chrome.rounded_supported:
                    assert calls[-2:] == [(33, 2, 0), (34, 0xFFFFFFFE, 0)]
            assert len(set(colors)) == 5
            assert not any(attribute in (35, 36) for attribute, _value, _result in calls), 'A native caption was themed'

            control('minimizeButton').forceActiveFocus(Qt.TabFocusReason)
            QTest.keyClick(window, Qt.Key_Tab)
            assert control('maximizeButton').hasActiveFocus(), 'Window controls lost their keyboard tab order'
            assert control('maximizeButton').property('visualFocus')
            QTest.keyClick(window, Qt.Key_Space)
            QTest.qWait(70)
            assert window.windowState() & Qt.WindowMaximized
            QTest.keyClick(window, Qt.Key_Space)
            QTest.qWait(70)
            assert window.windowState() == Qt.WindowNoState

            original_geometry = window.geometry()
            click('maximizeButton')
            assert window.windowState() & Qt.WindowMaximized
            assert window.geometry() == window.screen().availableGeometry(), 'Maximize covers the taskbar or clips controls'
            full_client()
            click('maximizeButton')
            assert window.windowState() == Qt.WindowNoState
            assert window.geometry() == original_geometry
            full_client()

            # Real native pointer input, rather than invoking QML handlers, must
            # preserve drag and resize. Capture only this app's rendered client.
            frame, _ = full_client()
            drag = control('windowDragArea')
            drag_point = drag.mapToScene(QPointF(min(150, drag.width() / 2), drag.height() / 2))
            pixel_x = frame.left + round(drag_point.x() * window.devicePixelRatio())
            pixel_y = frame.top + round(drag_point.y() * window.devicePixelRatio())
            before = window.geometry()
            native_pointer(pixel_x, pixel_y, delta=(75, 45))
            assert window.geometry().topLeft() != before.topLeft(), 'Actual title-strip drag failed'
            assert window.size() == before.size()
            frame, _ = full_client()
            before = window.geometry()
            resize_corners = []
            def record_resize_corner():
                resize_corners.append((window.x(), window.y()))
            window.xChanged.connect(record_resize_corner)
            window.yChanged.connect(record_resize_corner)
            try:
                native_pointer(frame.right - 3, (frame.top + frame.bottom) // 2, delta=(90, 0))
            finally:
                window.xChanged.disconnect(record_resize_corner)
                window.yChanged.disconnect(record_resize_corner)
            assert window.width() > before.width() and window.height() == before.height(), 'Actual edge resize failed'
            assert window.geometry().topLeft() == before.topLeft(), 'Right-edge resize moved its stationary left/top corner'
            assert all(corner == (before.x(), before.y()) for corner in resize_corners), (
                'Right-edge resize recentered the window during pointer motion', resize_corners)
            frame, _ = full_client()
            native_pointer(frame.left + round(drag_point.x() * window.devicePixelRatio()),
                           frame.top + round(drag_point.y() * window.devicePixelRatio()), clicks=2)
            assert window.windowState() & Qt.WindowMaximized, 'Actual title-strip double-click failed'
            click('maximizeButton')
            assert window.windowState() == Qt.WindowNoState
            window.setGeometry(original_geometry)
            QTest.qWait(80)

            for language in ('en', 'zh_CN'):
                controller.setPreference('language', language)
                QTest.qWait(50)
                click('maximizeButton')
                assert window.geometry() == window.screen().availableGeometry()
                click('maximizeButton')
                click('minimizeButton')
                assert user32.IsIconic(hwnd)
                window.showNormal()
                window.requestActivate()
                QTest.qWait(70)
            controller.setPreference('theme', '爱莉粉')
            QTest.qWait(100)
            output = Path('.tools/window-chrome-pixels')
            output.mkdir(parents=True, exist_ok=True)
            image = window.grabWindow()
            image.save(str(output / 'custom-window.png'))
            image.copy(max(0, image.width() - round(190 * window.devicePixelRatio())), 0,
                       round(190 * window.devicePixelRatio()), round(32 * window.devicePixelRatio())).save(str(output / 'window-controls.png'))
            close_button = control('closeWindowButton')
            close_point = close_button.mapToScene(QPointF(close_button.width() / 2, close_button.height() / 2)).toPoint()
            QTest.mouseMove(window, close_point)
            QTest.qWait(100)
            hover = window.grabWindow()
            close_corner = close_button.mapToScene(QPointF(0, 0))
            hover_color = hover.pixelColor(round((close_corner.x() + 6) * pixel_scale),
                                           round((close_corner.y() + close_button.height() / 2) * pixel_scale))
            assert (hover_color.red() > 150 and hover_color.green() < 100
                    and hover_color.blue() < 130), 'Reduced-motion close hover lost its contrast background'
            close_center = close_button.mapToScene(QPointF(close_button.width() / 2, close_button.height() / 2))
            white = sum(min(hover.pixelColor(x, y).red(), hover.pixelColor(x, y).green(),
                            hover.pixelColor(x, y).blue()) > 225
                        for x in range(round((close_center.x() - 8) * pixel_scale), round((close_center.x() + 8) * pixel_scale))
                        for y in range(round((close_center.y() - 8) * pixel_scale), round((close_center.y() + 8) * pixel_scale)))
            assert white >= 8, 'Close hover lost its visible white glyph'
            hover.copy(max(0, hover.width() - round(190 * window.devicePixelRatio())), 0,
                       round(190 * window.devicePixelRatio()), round(32 * window.devicePixelRatio())).save(str(output / 'window-controls-close-hover.png'))
            controller.setPreference('motion', True)
            QTest.mouseMove(window, control('windowDragArea').mapToScene(QPointF(100, 16)).toPoint())
            QTest.qWait(260)
            QTest.mouseMove(window, close_point)
            QTest.qWait(280)
            animated_hover = window.grabWindow()
            animated_color = animated_hover.pixelColor(round((close_corner.x() + 6) * pixel_scale),
                                                       round((close_corner.y() + close_button.height() / 2) * pixel_scale))
            assert (animated_color.red() > 150 and animated_color.green() < 100
                    and animated_color.blue() < 130), 'Animated close hover lost its final contrast background'
            controller.setPreference('motion', False)
            click('minimizeButton')
            assert window.windowState() & Qt.WindowMinimized and user32.IsIconic(hwnd)
            window.showNormal()
            window.requestActivate()
            QTest.qWait(100)
            assert window.geometry() == original_geometry
            full_client()

            # The custom close control must retain the existing tray lifecycle.
            click('closeWindowButton')
            assert not controller.closing
            if QSystemTrayIcon.isSystemTrayAvailable():
                assert not window.isVisible() and controller.shell.tray.isVisible()
            else:
                assert window.windowState() & Qt.WindowMinimized
            controller.shell.restore()
            QTest.qWait(100)
            assert window.isVisible() and window.windowState() == Qt.WindowNoState

            controller.resetPreferences()
            controller.save()
            assert read_preferences(controller.preference_path)['theme'] == '爱莉粉'
            print('PASS real Windows frameless client bounds, native capabilities/system menu, safe hit tests, '
                  'rendered glyphs/five themes/DWM rounding and shadow, native drag/resize/double-click, '
                  'keyboard tab/space, bilingual min/max/restore controls and close-to-tray lifecycle')
        finally:
            controller.close()
            window.hide()
            app.quit()


if __name__ == '__main__':
    main()
