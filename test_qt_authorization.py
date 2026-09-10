"""Offline authorization UI regression; no real certificates or account operations."""
import tempfile
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QObject
from PySide6.QtGui import QWindow
from PySide6.QtTest import QTest
from qt_ui import create_application


def main():
    with tempfile.TemporaryDirectory() as temp:
        app, engine, c, w = create_application(Path(temp) / 'prefs.json')
        c.cloudflare.cert = Path(temp) / 'test-cert.pem'
        c.setPreference('motion', False)
        errors = []
        engine.warnings.connect(lambda values: errors.extend(str(v) for v in values))
        try:
            w.setProperty('settingsOpen', True)
            QTest.qWait(100)
            assert w.findChild(QObject, 'quickAddressHelp').property('visible')
            assert not w.findChild(QObject, 'fixedDomainSetup').property('visible')
            c.setCloudflare('enabled', True)
            c.setCloudflare('hostname', 'hello.example.com')
            QTest.qWait(100)
            assert w.findChild(QObject, 'fixedDomainSetup').property('visible')
            assert not w.findChild(QObject, 'bindDomainButton').property('enabled')
            for language in ('zh_CN', 'en'):
                c.setPreference('language', language)
                w.resize(1240, 780)
                QTest.qWait(100)
                w.grabWindow().save(f'.tools/auth-setup-{language}.png')
            # Actual worker-to-GUI success path, with only external credential delivery mocked.
            w.showMinimized()
            with patch('cloudflare_account.EngineStore.ensure', return_value=Path('fake-engine')), \
                 patch.object(c.cloudflare, 'command', side_effect=lambda *a: c.cloudflare.cert.write_text('offline fixture')):
                c.cloudflare.begin('login')
                c.cloudflare.worker.join(2)
                assert not c.cloudflare.worker.is_alive()
            c.pump()
            QTest.qWait(100)
            assert w.visibility() != QWindow.Minimized
            assert not c.cloudflare.busy
            assert c.cloudflare.login_url == ''
            assert w.findChild(QObject, 'bindDomainButton').property('enabled')
            # Cancellation must not reactivate the window on a queued late success.
            w.showMinimized()
            c.cloudflare.cancel.set()
            c.cloudflare.events.put(('authorized', None))
            c.pump()
            QTest.qWait(50)
            assert w.visibility() == QWindow.Minimized
            w.showNormal()
            c.cloudflare.busy = True
            c.cloudflare.operation = 'login'
            c.cloudflareAction('temporary')
            assert c.cloudflare.cancel.is_set()
            assert not c.cloudflare.data['enabled']
            assert not w.property('settingsOpen')
            c.cloudflare.events.put(('finished', None))
            c.pump()
            assert not c.cloudflare.busy
            assert not errors, errors
            print('PASS progressive setup, binding guard, success return, cancellation and temporary-address fallback')
        finally:
            c.close()
            w.close()
            app.processEvents()


if __name__ == '__main__':
    main()
