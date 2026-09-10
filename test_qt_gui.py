"""Local Qt regression; no external tunnel is opened."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tempfile, traceback, json, socket, threading, os
from qt_ui import create_application, read_preferences, DEFAULTS
from PySide6.QtCore import QTimer, QObject, Qt, QPoint, Signal, QMetaObject
from PySide6.QtTest import QTest
from tunnel_core import WindowsJob, listening_ports

def main():
    with tempfile.TemporaryDirectory() as temporary:
        app, engine, c, w = create_application(Path(temporary) / 'prefs.json')
        errors = []
        c.errorRaised.connect(errors.append)
        failures = []

        def stage1():
            try:
                c.setField('port', 'invalid')
                c.start()
                assert errors and (not c.active)
                c.setField('port', '8080')
                c.setField('mode', 'Cloudflare')
                c.setField('protocol', 'TCP')
                c.start()
                assert len(errors) == 2 and (not c.active)
                c.setField('protocol', 'HTTP')
                c.setPreference('theme', '薄荷绿')
                c.setPreference('speed', 0.5)
                c.save()
                assert read_preferences(c.preference_path) == {'theme': '薄荷绿', 'speed': 0.5, 'motion': True, 'language': 'zh_CN'}
                c.setPreference('motion', False)
                w.setProperty('settingsOpen', True)
                assert w.property('settingsOpen')
                c.core.emit(c.core.run_id - 1, 'address', 'stale')
                c.pump()
                assert c.address == ''
                c.core.emit(c.core.run_id, 'address', 'https://example.com')
                c.pump()
                c.copyAddress()
                assert app.clipboard().text() == 'https://example.com'
                with socket.socket() as s:
                    s.bind(('127.0.0.1', 0))
                    s.listen()
                    assert s.getsockname()[1] in listening_ports()
                QMetaObject.invokeMethod(w.findChild(QObject, 'messageDialog'), 'close')

                class ScreenDouble(QObject):
                    refreshRateChanged = Signal(float)
                    hz = 60.0

                    def refreshRate(self):
                        return self.hz

                    def setRate(self, value):
                        self.hz = value
                        self.refreshRateChanged.emit(value)
                first, second = (ScreenDouble(), ScreenDouble())
                c.bindScreen(first)
                for rate in (59.94, 60, 75, 90, 120, 144, 160, 165, 240, 360, 500):
                    first.setRate(rate)
                    assert c.state['refreshRate'] == rate
                c.bindScreen(second)
                first.setRate(100)
                assert c.state['refreshRate'] == 60.0
                second.setRate(144)
                assert c.state['refreshRate'] == 144
                c.bindScreen(w.screen())
                w.resize(640, 560)
            except Exception:
                failures.append(traceback.format_exc())

        def stage2():
            try:
                w.grabWindow().save('.tools/qt-small-settings.png')
                assert w.findChild(QObject, 'pageStrip').property('x') == -w.width()
                c.setPreference('motion', True)
                c.setPreference('speed', 2.0)
                w.setProperty('settingsOpen', False)
            except Exception:
                failures.append(traceback.format_exc())

        def stage3():
            try:
                w.setProperty('settingsOpen', True)
                QTimer.singleShot(75, lambda: w.setProperty('settingsOpen', False))
                QTimer.singleShot(160, lambda: w.setProperty('settingsOpen', True))
            except Exception:
                failures.append(traceback.format_exc())

        def stage4():
            try:
                assert w.findChild(QObject, 'pageStrip').property('x') == -w.width()
                assert w.findChild(QObject, 'settingsPage').property('x') == w.width()
                c.setPreference('motion', False)
                w.setProperty('settingsOpen', False)
                c.resetPreferences()
                c.save()
                assert read_preferences(c.preference_path) == DEFAULTS
                c.preference_path.write_text('{bad', encoding='utf-8')
                assert read_preferences(c.preference_path) == DEFAULTS
                job = WindowsJob()
                c.core.job = job
                child = job.launch([sys.executable, '-c', 'import time; print("READY",flush=True); time.sleep(60)'], Path.cwd(), os.environ.copy(), threading.Event())
                assert child.stdout.readline().strip() == b'READY'
                c.active = True
                c.stop()
                child.wait(timeout=5)
                child.stdout.close()
                assert c.core.cancel.is_set()
                c.core.emit(c.core.run_id, 'done', None)
                c.pump()
                assert not c.active
                job = WindowsJob()
                c.core.job = job
                child = job.launch([sys.executable, '-c', 'import time; print("READY",flush=True); time.sleep(60)'], Path.cwd(), os.environ.copy(), threading.Event())
                assert child.stdout.readline().strip() == b'READY'
                c.close()
                child.wait(timeout=5)
                child.stdout.close()
                print('PASS automatic refresh signal tracking and screen reassignment; validation, state delivery, stale events, clipboard, port discovery, settings persistence/corruption/reset, page reversal, reduced motion, small window, stop/close process cleanup', flush=True)
            except Exception:
                failures.append(traceback.format_exc())
            finally:
                app.quit()
        QTimer.singleShot(500, stage1)
        QTimer.singleShot(1100, stage2)
        QTimer.singleShot(1700, stage3)
        QTimer.singleShot(2600, stage4)
        app.exec()
        if failures:
            print('\n'.join(failures))
            sys.exit(1)
if __name__ == '__main__':
    main()
