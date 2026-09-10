"""Manage isolated tunnel sessions and reusable FRPS profiles on the GUI thread."""
import re
import uuid
from pathlib import Path
from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer
from profile_store import ProfileStore

SERVER_FIELDS = ('server', 'server_port', 'token', 'public_host')


class TunnelManager(QObject):
    changed = Signal()
    logsChanged = Signal()
    errorRaised = Signal(str)
    authorizationCompleted = Signal()
    temporarySelected = Signal()
    backgroundRequested = Signal()

    def __init__(self, session_class, preference_path=None):
        super().__init__()
        self.session_class = session_class
        self.sessions = {}
        self.profiles = {}
        self.servers = []
        self.selected = ''
        self.closing = False
        self.profile_error = ''
        first = session_class(preference_path)
        self.preference_path = first.preference_path
        self.store = ProfileStore(self.preference_path.parent / 'tunnels.json')
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(350)
        self.save_timer.timeout.connect(self.save_profiles)
        try:
            saved = self.store.load()
            rows = saved.get('tunnels', []) if saved else []
            if len(rows) > 256:
                raise ValueError('Too many saved tunnel profiles.')
            self.servers = saved.get('servers', []) if saved else []
            ids = set()
            for row in self.servers + rows:
                if not re.fullmatch('[a-f0-9]{32}', row['id']) or row['id'] in ids:
                    raise ValueError('Invalid or duplicate profile ID.')
                ids.add(row['id'])
                if not isinstance(row['name'], str) or not isinstance(row['fields'], dict):
                    raise ValueError('Invalid profile fields.')
                if any(not isinstance(v, str) for v in row['fields'].values()):
                    raise ValueError('Invalid profile field value.')
            if not rows:
                rows = [{'id': uuid.uuid4().hex, 'name': 'Tunnel 1', 'fields': {}, 'serverId': '', 'legacyCloudflare': True}]
            for index, row in enumerate(rows):
                session = first if index == 0 else session_class(self.preference_path)
                if not row.get('legacyCloudflare', False):
                    from cloudflare_account import CloudflareAccount
                    session.cloudflare = CloudflareAccount(self.preference_path.parent / 'cloudflare' / 'tunnels' / row['id'], session.core.cache)
                session.fields.update({k: v for k, v in row['fields'].items() if k in session.fields})
                self._attach(row, session)
            selected = saved.get('selected') if saved else None
            self.selected = selected if selected in self.sessions else rows[0]['id']
            self.primary = self.sessions[rows[0]['id']]
            for session in self.sessions.values():
                session.preferences = self.primary.preferences
        except Exception:
            first.close()
            for session in self.sessions.values():
                session.close()
            raise

    def _attach(self, profile, session):
        key = profile['id']
        profile.setdefault('serverId', '')
        self.sessions[key], self.profiles[key] = session, profile
        session.changed.connect(self.changed.emit)
        session.logsChanged.connect(lambda: self.logsChanged.emit() if self.selected == key else None)
        session.errorRaised.connect(lambda detail: self.errorRaised.emit(profile['name'] + '\n' + session.tr_text(detail)))
        session.authorizationCompleted.connect(lambda: self._authorized(key))
        session.temporarySelected.connect(lambda: self.temporarySelected.emit() if self.selected == key else None)

    def _authorized(self, key):
        if self.closing:
            return
        self.selectTunnel(key)
        self.authorizationCompleted.emit()

    @property
    def current(self):
        return self.sessions[self.selected]

    def __getattr__(self, name):
        # Python callers retain access to the selected session's diagnostics.
        if name.startswith('_'):
            raise AttributeError(name)
        return getattr(self.current, name)

    @property
    def active(self):
        return self.current.active

    @active.setter
    def active(self, value):
        self.current.active = value

    @property
    def preferences(self):
        return self.primary.preferences

    @Property('QVariantMap', notify=changed)
    def state(self):
        state = dict(self.current.state)
        row = self.profiles[self.selected]
        server = next((s for s in self.servers if s['id'] == row['serverId']), None)
        state.update({'tunnels': [{'id': key, 'name': self.profiles[key]['name'], 'active': s.active,
                                   'port': s.fields['port'], 'status': s.state['status'], 'address': s.address}
                                  for key, s in self.sessions.items()],
                      'selectedTunnel': self.selected, 'tunnelName': row['name'],
                      'runningCount': sum(s.active for s in self.sessions.values()),
                      'servers': [{'id': '', 'name': self.tr_text('手动配置')}] + [{'id': s['id'], 'name': s['name']} for s in self.servers],
                      'serverId': row['serverId'], 'serverName': server['name'] if server else '',
                      'accountBusy': any(s.cloudflare.busy for s in self.sessions.values()),
                      'saveError': self.profile_error or state['saveError']})
        return state

    @Property(str, notify=logsChanged)
    def logText(self):
        return self.current.logText

    def tr_text(self, text):
        return self.primary.tr_text(text)

    @Slot(str, str, result=str)
    def translate(self, text, language):
        return self.primary.translate(text, language)

    @Slot(str)
    def selectTunnel(self, key):
        if key in self.sessions and not self.closing:
            self.selected = key
            self.changed.emit(); self.logsChanged.emit()
            self.save_timer.start()

    @Slot()
    def addTunnel(self):
        if self.closing:
            return
        if len(self.sessions) >= 256:
            return
        key = uuid.uuid4().hex
        session = self.session_class(self.preference_path)
        from cloudflare_account import CloudflareAccount
        session.cloudflare = CloudflareAccount(self.preference_path.parent / 'cloudflare' / 'tunnels' / key, session.core.cache)
        session.preferences = self.preferences
        if self.primary.screen is not None:
            session.bindScreen(self.primary.screen)
        self._attach({'id': key, 'name': 'Tunnel ' + str(len(self.sessions) + 1), 'fields': {}, 'serverId': ''}, session)
        self.selectTunnel(key)

    @Slot(str)
    def renameTunnel(self, name):
        if name.strip():
            self.profiles[self.selected]['name'] = name.strip()[:80]
            self.changed.emit(); self.save_timer.start()

    @Slot()
    def deleteTunnel(self):
        if len(self.sessions) == 1 or self.current.active or self.current.cloudflare.busy:
            return
        key = self.selected
        session = self.sessions.pop(key)
        self.profiles.pop(key)
        session.close()
        self.selected = next(iter(self.sessions))
        if session is self.primary:
            self.primary = self.current
        session.deleteLater()
        self.changed.emit(); self.logsChanged.emit(); self.save_timer.start()

    @Slot(str, str)
    def setField(self, name, value):
        if self.current.active:
            return
        self.current.setField(name, value)
        self.changed.emit(); self.save_timer.start()

    @Slot(str)
    def selectServer(self, key):
        if self.current.active:
            return
        server = next((s for s in self.servers if s['id'] == key), None)
        if key and server is None:
            return
        self.profiles[self.selected]['serverId'] = key
        if server:
            self.current.fields.update({k: server['fields'].get(k, '') for k in SERVER_FIELDS})
        self.changed.emit(); self.save_timer.start()

    @Slot(str, bool)
    def saveServer(self, name, as_new=False):
        if self.current.active or not name.strip():
            return
        key = '' if as_new else self.profiles[self.selected]['serverId']
        if key and any(s.active and self.profiles[k]['serverId'] == key for k, s in self.sessions.items()):
            self.errorRaised.emit(self.tr_text('请先停止使用此服务端的隧道。')); return
        fields = {k: self.current.fields[k] for k in SERVER_FIELDS}
        server = next((s for s in self.servers if s['id'] == key), None)
        if server is None:
            server = {'id': uuid.uuid4().hex}
            self.servers.append(server)
        server.update(name=name.strip()[:80], fields=fields)
        self.profiles[self.selected]['serverId'] = server['id']
        for k, s in self.sessions.items():
            if self.profiles[k]['serverId'] == server['id']:
                s.fields.update(fields)
        self.changed.emit(); self.save_timer.start()

    @Slot()
    def deleteServer(self):
        key = self.profiles[self.selected]['serverId']
        if not key:
            return
        if any(s.active and self.profiles[k]['serverId'] == key for k, s in self.sessions.items()):
            self.errorRaised.emit(self.tr_text('请先停止使用此服务端的隧道。')); return
        self.servers = [s for s in self.servers if s['id'] != key]
        for p in self.profiles.values():
            if p['serverId'] == key: p['serverId'] = ''
        self.changed.emit(); self.save_timer.start()

    def save_profiles(self):
        try:
            self.store.save({'version': 1, 'selected': self.selected, 'servers': self.servers,
                             'tunnels': [{**self.profiles[k], 'fields': s.fields.copy()} for k, s in self.sessions.items()]})
            self.profile_error = ''
        except Exception as exc:
            self.profile_error = self.tr_text('配置保存失败：') + str(exc)
        self.changed.emit()

    def _start(self, key):
        session = self.sessions[key]
        if self.closing or session.active:
            return
        # Reject collisions before starting a second connector or remote proxy.
        for other in self.sessions.values():
            if other is session or not other.active:
                continue
            fixed = session.cloudflare.data
            existing = other.cloudflare.data
            if session.fields['mode'] != 'FRP' and other.fields['mode'] != 'FRP' and fixed['enabled'] and existing['enabled'] and (fixed['id'] and fixed['id'] == existing['id'] or fixed['hostname'] and fixed['hostname'] == existing['hostname']):
                self.errorRaised.emit(self.tr_text('此固定域名已被另一条运行中的隧道使用。')); return
            if session.fields['server'] and session.fields['mode'] != 'Cloudflare' and other.fields['mode'] != 'Cloudflare':
                keys = ('server', 'server_port', 'remote_port')
                if all(session.fields[k].strip().lower() == other.fields[k].strip().lower() for k in keys):
                    self.errorRaised.emit(self.tr_text('同一服务端的远程端口已被另一条隧道使用。')); return
        session.start()

    @Slot()
    def start(self): self._start(self.selected)
    @Slot(str)
    def startTunnel(self, key):
        if key in self.sessions: self._start(key)
    @Slot(str)
    def stopTunnel(self, key):
        if key in self.sessions: self.sessions[key].stop()
    @Slot()
    def stop(self): self.current.stop()
    @Slot()
    def restart(self):
        if self.current.active: self.current.restart()
        else: self.start()
    @Slot()
    def startAll(self):
        for key in tuple(self.sessions): self._start(key)
    @Slot()
    def stopAll(self):
        for session in self.sessions.values(): session.stop()
    @Slot()
    def scan(self): self.current.scan()
    @Slot()
    def copyAddress(self): self.current.copyAddress()
    @Slot()
    def openAddress(self): self.current.openAddress()
    @Slot()
    def background(self): self.backgroundRequested.emit()
    @Slot(result=bool)
    def handleClose(self):
        if self.closing: return True
        self.backgroundRequested.emit()
        return False
    @Slot()
    def exitApplication(self): self.shell.exit()
    @Slot(str, 'QVariant')
    def setPreference(self, name, value):
        self.primary.setPreference(name, value)
        for session in self.sessions.values(): session.preferences = self.primary.preferences
        self.changed.emit(); self.logsChanged.emit()
    @Slot()
    def resetPreferences(self):
        self.primary.resetPreferences()
        for session in self.sessions.values(): session.preferences = self.primary.preferences
        self.changed.emit(); self.logsChanged.emit()
    @Slot()
    def save(self): self.primary.save(); self.save_profiles()
    @Slot(str, 'QVariant')
    def setCloudflare(self, name, value): self.current.setCloudflare(name, value)
    @Slot(str)
    def cloudflareAction(self, action):
        if action in ('login', 'prepare') and any(s.cloudflare.busy for s in self.sessions.values()): return
        if action == 'prepare':
            domain = self.current.cloudflare.data['hostname'].strip().lower().rstrip('.')
            if domain and any(s is not self.current and s.cloudflare.data['hostname'].strip().lower().rstrip('.') == domain for s in self.sessions.values()):
                self.errorRaised.emit(self.tr_text('此固定域名已分配给另一条隧道。')); return
        self.current.cloudflareAction(action)

    def pump(self):
        for session in tuple(self.sessions.values()): session.pump()
    def bindScreen(self, screen):
        for session in self.sessions.values(): session.bindScreen(screen)
    def refreshSystemMotion(self, state):
        for session in self.sessions.values(): session.refreshSystemMotion(state)
    def notify_error(self, error): self.current.notify_error(error)
    @Slot()
    def close(self):
        if self.closing: return
        self.save_timer.stop()
        self.save()
        self.closing = True
        for session in self.sessions.values(): session.close()
        if 'shell' in self.__dict__:
            self.shell.tray.hide()
