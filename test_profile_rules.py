"""Offline profile switching, duplicate-port rejection and download cancellation."""
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from qt_ui import create_application
from tunnel_core import EngineStore, Cancelled


with tempfile.TemporaryDirectory() as temp:
    app, engine, manager, window = create_application(Path(temp) / 'prefs.json')
    try:
        manager.setField('server', 'one.example.com')
        manager.setField('token', 'one-secret')
        manager.saveServer('One', False)
        one = manager.state['serverId']
        manager.setField('server', 'two.example.com')
        manager.setField('token', 'two-secret')
        manager.saveServer('Two', True)
        two = manager.state['serverId']
        assert one != two
        manager.selectServer(one)
        assert manager.fields['server'] == 'one.example.com' and manager.fields['token'] == 'one-secret'
        first = manager.selected
        manager.addTunnel()
        manager.selectServer(two)
        assert manager.fields['server'] == 'two.example.com'
        manager.selectServer(one)
        manager.sessions[first].active = True
        messages = []
        manager.errorRaised.connect(messages.append)
        manager.start()
        assert messages and not manager.active
        manager.sessions[first].active = False
        manager.deleteServer()
        assert not any(p['serverId'] == one for p in manager.profiles.values())
        assert all(s['id'] != one for s in manager.servers)
        # A cancelled second download cannot enter the same engine's installer.
        entered, release, cancelled = threading.Event(), threading.Event(), threading.Event()
        first_store = EngineStore(Path(temp)/'engines', lambda *args: None, threading.Event())
        second_cancel = threading.Event()
        second_store = EngineStore(Path(temp)/'engines', lambda *args: None, second_cancel)
        def install(_self, _engine):
            entered.set()
            assert release.wait(3)
            return Path('fake-engine')
        def second_call():
            try: second_store.ensure('frpc')
            except Cancelled: cancelled.set()
        with patch.object(EngineStore, '_ensure', install):
            t1 = threading.Thread(target=lambda: first_store.ensure('frpc'))
            t1.start(); assert entered.wait(2)
            t2 = threading.Thread(target=second_call); t2.start()
            second_cancel.set()
            assert cancelled.wait(2)
            release.set(); t1.join(2); t2.join(2)
        print('PASS multiple FRPS profiles, duplicate remote port guard, deletion and cancellable serialized engine installation')
    finally:
        manager.close(); window.close(); app.processEvents()
