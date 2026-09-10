"""Offline manager integration with real isolated Windows child processes."""
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch
from PySide6.QtTest import QTest
from PySide6.QtGui import QWindow
from qt_ui import create_application, Controller
from tunnel_manager import TunnelManager
from tunnel_core import WindowsJob


def main():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'appearance.json'
        app, engine, manager, window = create_application(path)
        failures, processes = [], {}
        manager.errorRaised.connect(failures.append)
        try:
            first = manager.selected
            manager.setField('mode', 'FRP')
            manager.setField('server', '127.0.0.1')
            manager.setField('token', 'secret-regression-token')
            manager.saveServer('Local test A', False)
            server_id = manager.state['serverId']
            manager.addTunnel()
            second = manager.selected
            manager.setField('mode', 'FRP')
            manager.selectServer(server_id)
            manager.setField('remote_port', '18081')
            assert manager.sessions[first].core is not manager.sessions[second].core
            assert manager.sessions[first].cloudflare.credentials != manager.sessions[second].cloudflare.credentials
            assert manager.sessions[first].cloudflare.cert == manager.sessions[second].cloudflare.cert

            def install_runner(key):
                core = manager.sessions[key].core
                def run(run_id, config, cancel):
                    job = WindowsJob()
                    with core.job_lock:
                        core.job = job
                    process = None
                    try:
                        process = job.launch([sys.executable, '-c', 'import time; time.sleep(60)'], folder, dict(__import__('os').environ), cancel)
                        processes[key] = process
                        core.emit(run_id, 'address', 'tcp://127.0.0.1:' + str(config['remote_port']))
                        core.emit(run_id, 'connected', '已连接')
                        core.log('isolated-log-' + key)
                        cancel.wait(10)
                    finally:
                        job.close()
                        if process:
                            process.wait(timeout=5)
                            process.stdout.close()
                        with core.job_lock:
                            core.job = None
                        core.emit(run_id, 'done', None)
                core.run = run
            install_runner(first); install_runner(second)
            manager.startAll()
            deadline = time.monotonic() + 5
            while len(processes) < 2 and time.monotonic() < deadline:
                QTest.qWait(25)
            QTest.qWait(150)
            assert len(processes) == 2 and manager.state['runningCount'] == 2
            manager.selectTunnel(first)
            assert '18080' in manager.address and 'isolated-log-' + first in manager.logText
            assert second not in manager.logText
            manager.setField('port', '9999')
            assert manager.fields['port'] != '9999'
            # Closing the GUI hides it; it must not terminate either child.
            with patch('tray_shell.QSystemTrayIcon.isSystemTrayAvailable', return_value=True):
                window.close()
                QTest.qWait(50)
                assert not window.isVisible() and not manager.closing
                assert all(p.poll() is None for p in processes.values())
            with patch('tray_shell.QSystemTrayIcon.isSystemTrayAvailable', return_value=False):
                manager.shell.hide()
                QTest.qWait(50)
                assert window.visibility() == QWindow.Minimized
            manager.stop()
            manager.sessions[first].worker.join(5)
            manager.pump()
            assert processes[first].poll() is not None and processes[second].poll() is None
            manager.saveServer('Blocked update', False)
            assert failures, 'Updating a profile used by a running tunnel should be rejected'
            manager.selectTunnel(second)
            assert '18081' in manager.address and first not in manager.logText
            manager.stopAll()
            manager.sessions[second].worker.join(5)
            manager.pump()
            assert manager.state['runningCount'] == 0
            manager.save()
            raw = manager.store.path.read_text(encoding='utf-8')
            assert 'secret-regression-token' not in raw
            assert 'protected_token' in raw
            reopened = TunnelManager(Controller, path)
            try:
                assert len(reopened.sessions) == 2
                assert reopened.fields['token'] == 'secret-regression-token'
                assert reopened.state['runningCount'] == 0
                assert reopened.state['serverId'] == server_id
            finally:
                reopened.close()
            manager.shell.exit()
            assert manager.closing and all(p.poll() is not None for p in processes.values())
            print('PASS concurrent independent jobs/logs, single stop, tray close/fallback/exit, profile switching and encrypted persistence')
        finally:
            manager.close()
            for session in manager.sessions.values():
                if session.worker: session.worker.join(5)
            window.close(); app.processEvents()


if __name__ == '__main__':
    main()
