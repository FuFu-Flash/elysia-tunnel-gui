# -*- coding: utf-8 -*-
"""Qt Quick presentation and a GUI-thread bridge to the tunnel worker."""
from __future__ import annotations

import atexit
import ctypes
import json
import math
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
import time
import webbrowser

from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QSurfaceFormat, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle

from tunnel_core import APP_NAME, TunnelCore, error_text, friendly_error, listening_ports
from cloudflare_account import CloudflareAccount, hostname

THEMES = {"爱莉粉": "#C24C86", "薰衣紫": "#6750A4", "玫瑰粉": "#984568", "薄荷绿": "#286B58", "晴空蓝": "#355F98"}
DEFAULTS = {"theme": "爱莉粉", "speed": 1.0, "motion": True}
FIELDS = {"mode": "自动", "protocol": "HTTP", "port": "8080", "server": "",
          "server_port": "7000", "remote_port": "18080", "token": "", "public_host": ""}


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def read_preferences(path):
    result = DEFAULTS.copy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return result
        if isinstance(data.get("theme"), str) and data["theme"] in THEMES:
            result["theme"] = data["theme"]
        speed = data.get("speed")
        if type(speed) in (int, float) and math.isfinite(speed) and .5 <= speed <= 2:
            result["speed"] = float(speed)
        if isinstance(data.get("motion"), bool):
            result["motion"] = data["motion"]
    except (OSError, ValueError):
        pass
    return result


def system_motion_enabled():
    value = ctypes.c_int(1)
    try:
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(value), 0)
    except (AttributeError, OSError):
        pass
    return bool(value.value)


class Controller(QObject):
    changed = Signal()
    logsChanged = Signal()
    errorRaised = Signal(str)

    def __init__(self, preference_path=None):
        super().__init__()
        self.core = TunnelCore()
        core = self.core
        core.events = queue.Queue()
        core.logs = queue.Queue(maxsize=2500)
        core.cancel = threading.Event()
        core.job = None
        core.job_lock = threading.Lock()
        core.run_id = 0
        base = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "OneClickTunnelGUI"
        core.cache = base / "engines"
        self.preference_path = Path(preference_path) if preference_path else base / "appearance.json"
        self.cloudflare = CloudflareAccount(self.preference_path.parent / "cloudflare", core.cache)
        self.preferences = read_preferences(self.preference_path)
        self.fields = FIELDS.copy()
        self.active = self.scan_busy = self.closing = self.restart_pending = False
        self.worker = None
        self.address = ""
        self.status = "准备就绪"
        self.ports = []
        self.save_error = ""
        self.refresh_rate = 60.0
        self.screen = None
        self.system_motion = system_motion_enabled()
        self.lines = ["嗨，我在这里哦♪ 点下「开始穿透」，我们就一起出发吧。"]
        self.timer = QTimer(self)
        self.timer.setInterval(100)  # Network/log delivery only; never drives animation.
        self.timer.timeout.connect(self.pump)
        self.timer.start()
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(300)
        self.save_timer.timeout.connect(self.save)
        self.dirty = False

    @Property("QVariantMap", notify=changed)
    def state(self):
        words = {"准备就绪": "准备好啦，随时可以出发♪", "已连接": "连接好啦，把小小世界分享出去吧♪",
                 "已停止": "先歇一会儿，我会在这里等你", "连接失败": "哎呀，这次没连上，一起看看日志吧"}
        return {**self.fields, **self.preferences, **self.cloudflare.state(), "accent": THEMES[self.preferences["theme"]],
                "active": self.active, "scanBusy": self.scan_busy, "ports": self.ports,
                "status": words.get(self.status, self.status), "rawStatus": self.status,
                "address": self.address, "saveError": self.save_error,
                "systemMotion": self.system_motion, "refreshRate": self.refresh_rate,
                "stopping": self.active and self.core.cancel.is_set()}

    @Property(str, notify=logsChanged)
    def logText(self):
        return "\n".join(self.lines)

    @Slot(str, str)
    def setField(self, name, value):
        if self.active or name not in FIELDS:
            return
        if name == "mode" and value not in ("自动", "Cloudflare", "FRP"):
            return
        if name == "protocol" and value not in ("HTTP", "HTTPS", "TCP"):
            return
        self.fields[name] = value
        self.changed.emit()

    @Slot(str, "QVariant")
    def setPreference(self, name, value):
        if name == "theme" and value in THEMES:
            self.preferences[name] = value
        elif name == "speed" and type(value) in (int, float) and math.isfinite(value):
            self.preferences[name] = round(max(.5, min(2., value)), 1)
        elif name == "motion" and isinstance(value, bool):
            self.preferences[name] = value
        else:
            return
        self.dirty = True
        self.save_timer.start()
        self.changed.emit()

    @Slot()
    def resetPreferences(self):
        self.preferences = DEFAULTS.copy()
        self.dirty = True
        self.save_timer.start()
        self.changed.emit()

    @Slot()
    def save(self):
        if not self.dirty:
            return
        temp = None
        try:
            self.preference_path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(prefix="appearance-", suffix=".tmp", dir=self.preference_path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self.preferences, stream, ensure_ascii=False)
            os.replace(temp, self.preference_path)
            self.dirty = False
            self.save_error = ""
        except OSError as exc:
            self.save_error = "哎呀，设置没能保存：" + error_text(exc)
        finally:
            if temp and os.path.exists(temp):
                try:
                    os.unlink(temp)
                except OSError:
                    pass
        self.changed.emit()

    def notify_error(self, exc):
        self.errorRaised.emit(friendly_error(error_text(exc)))

    @Slot()
    def start(self):
        if self.active or self.closing or self.cloudflare.busy:
            return
        for name, value in self.fields.items():
            setattr(self.core, name, Value(value))
        try:
            if self.cloudflare.data["enabled"] and self.fields["mode"] == "自动":
                self.core.mode = Value("Cloudflare")
            config = self.core.snapshot()
            fixed = self.cloudflare.snapshot() if config["mode"] != "FRP" else None
            if fixed:
                if config["protocol"] == "tcp":
                    raise ValueError("固定域名模式用于 HTTP / HTTPS 网站，TCP 请切换到 FRP。")
                config["cloudflare_fixed"] = fixed
        except Exception as exc:
            self.notify_error(exc)
            return
        self.core.run_id += 1
        self.core.cancel = threading.Event()
        self.restart_pending = False
        self.active = True
        self.address = ""
        self.status = "检测本地服务…"
        self.worker = threading.Thread(target=self.core.run,
                                       args=(self.core.run_id, config, self.core.cancel), daemon=True)
        self.worker.start()
        self.changed.emit()

    @Slot()
    def stop(self):
        self.restart_pending = False
        if not self.active:
            return
        self.core.cancel.set()
        self.status = "正在收好这次连接，稍等我一下…"
        self.address = ""
        self.core.kill_job()
        self.changed.emit()

    @Slot()
    def restart(self):
        if not self.active:
            self.start()
        else:
            self.stop()
            self.restart_pending = True

    @Slot()
    def scan(self):
        if self.active or self.scan_busy or self.closing:
            return
        self.scan_busy = True
        run_id = self.core.run_id

        def work():
            try:
                self.core.emit(run_id, "ports", listening_ports())
            except Exception as exc:
                self.core.emit(run_id, "scan_error", error_text(exc))
            finally:
                self.core.emit(run_id, "scan_done", None)

        threading.Thread(target=work, daemon=True).start()
        self.changed.emit()

    @Slot()
    def pump(self):
        if self.closing:
            return
        changed = False
        for _ in range(200):
            try:
                kind, value = self.cloudflare.events.get_nowait()
            except queue.Empty:
                break
            changed = True
            if kind == "log":
                self.core.log(value)
            elif kind == "login_url":
                self.cloudflare.login_url = value
            elif kind == "finished":
                self.cloudflare.busy = False
            elif kind == "error":
                self.cloudflare.status = "这次操作没有完成，看看提示吧。"
                self.notify_error(value)
            elif kind == "status":
                self.cloudflare.status = value
        for _ in range(300):
            try:
                run_id, kind, value = self.core.events.get_nowait()
            except queue.Empty:
                break
            if kind == "scan_done":
                self.scan_busy = False
                changed = True
                continue
            if run_id != self.core.run_id:
                continue
            changed = True
            if kind in ("status", "connected"):
                self.status = value
            elif kind == "engine":
                self.status = f"准备 {value}，稍等一下哦…"
            elif kind == "address":
                self.address = value
            elif kind == "ports":
                self.ports = [str(port) for port in value]
                if self.ports and not self.active and self.fields["port"] not in self.ports:
                    self.fields["port"] = next((str(p) for p in (8080, 3000, 8000, 5000, 80, 5173, 8888, 443)
                                                if str(p) in self.ports), self.ports[0])
                self.core.log("找到这些端口啦：" + "、".join(self.ports) if self.ports else "先启动本地服务，再让我找找吧♪")
            elif kind in ("scan_error", "error"):
                self.core.log(value)
                if kind == "error":
                    self.status = "连接失败"
                    self.address = ""
                if not self.core.cancel.is_set():
                    self.notify_error(value)
            elif kind == "done":
                self.active = False
                if self.core.cancel.is_set():
                    self.status = "已停止"
                    self.address = ""
                if self.restart_pending:
                    self.restart_pending = False
                    QTimer.singleShot(100, self.start)
        incoming = []
        for _ in range(200):
            try:
                run_id, line = self.core.logs.get_nowait()
            except queue.Empty:
                break
            if run_id == self.core.run_id:
                incoming.append(f"{time.strftime('%H:%M:%S')}  {line}")
        if incoming:
            self.lines = (self.lines + incoming)[-1500:]
            self.logsChanged.emit()
        if changed:
            self.changed.emit()

    @Slot()
    def copyAddress(self):
        if self.address:
            QGuiApplication.clipboard().setText(self.address)
            self.core.log("外网地址帮你复制好啦，记得分享给想见的人哦♪")

    @Slot()
    def openAddress(self):
        if self.address.startswith(("http://", "https://")):
            webbrowser.open(self.address)
        elif self.address:
            self.errorRaised.emit("这是 TCP 地址哦，要在对应客户端里使用。点一下「复制地址」，我帮你收好♪")

    def updateScreen(self, screen):
        if screen:
            self.refresh_rate = screen.refreshRate()
            self.changed.emit()

    @Slot(str)
    def cloudflareAction(self, action):
        if self.closing:
            return
        if action == "cancel":
            self.cloudflare.stop()
        elif action == "dashboard":
            webbrowser.open("https://dash.cloudflare.com/")
        elif action == "browser" and self.cloudflare.login_url:
            webbrowser.open(self.cloudflare.login_url)
        elif action in ("login", "prepare") and not self.active and not self.cloudflare.busy:
            try:
                if action == "prepare":
                    self.cloudflare.data["hostname"] = hostname(self.cloudflare.data["hostname"])
                self.cloudflare.begin(action)
            except Exception as exc:
                self.notify_error(exc)
        self.changed.emit()

    @Slot(str, "QVariant")
    def setCloudflare(self, name, value):
        if self.active or self.cloudflare.busy:
            return
        if name == "enabled" and isinstance(value, bool):
            self.cloudflare.data[name] = value
        elif name == "hostname" and isinstance(value, str):
            self.cloudflare.data[name] = value.strip()
        else:
            return
        try:
            self.cloudflare.save()
        except OSError as exc:
            self.notify_error(exc)
        self.changed.emit()

    def bindScreen(self, screen):
        if self.screen is not None:
            try:
                self.screen.refreshRateChanged.disconnect(self.screenRateChanged)
            except (RuntimeError, TypeError):
                pass
        self.screen = screen
        if screen is not None:
            screen.refreshRateChanged.connect(self.screenRateChanged)
        self.updateScreen(screen)

    @Slot(float)
    def screenRateChanged(self, _rate):
        self.updateScreen(self.screen)

    def refreshSystemMotion(self, _state):
        self.system_motion = system_motion_enabled()
        self.changed.emit()

    @Slot()
    def close(self):
        if self.closing:
            return
        self.closing = True
        self.timer.stop()
        self.save_timer.stop()
        self.save()
        self.restart_pending = False
        self.cloudflare.stop()
        self.core.cancel.set()
        self.core.kill_job()


def create_application(preference_path=None):
    # Use the render-thread animation driver and vsync. No Python animation timer.
    os.environ["QSG_RENDER_LOOP"] = "threaded"
    fmt = QSurfaceFormat()
    fmt.setSwapInterval(1)
    QSurfaceFormat.setDefaultFormat(fmt)
    QQuickStyle.setStyle("Material")
    application = QGuiApplication.instance() or QGuiApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setWindowIcon(QIcon(str(Path(__file__).resolve().parent / "assets" / "app.ico")))
    if os.name == "nt":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Elysia.Tunnel.GUI")
    controller = Controller(preference_path)
    engine = QQmlApplicationEngine()
    load_errors = []
    engine.warnings.connect(lambda messages: load_errors.extend(message.toString() for message in messages))
    engine.rootContext().setContextProperty("bridge", controller)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent / "qml" / "Main.qml")))
    if not engine.rootObjects():
        controller.close()
        raise RuntimeError("界面没有加载成功：\n" + "\n".join(load_errors))
    window = engine.rootObjects()[0]
    controller.bindScreen(window.screen())
    window.screenChanged.connect(controller.bindScreen)
    application.applicationStateChanged.connect(lambda: controller.refreshSystemMotion(None))
    application.aboutToQuit.connect(controller.close)
    atexit.register(controller.close)
    return application, engine, controller, window


def main():
    if os.name != "nt":
        raise RuntimeError("这次旅程需要 Windows 10 / 11 哦。")
    application, engine, controller, window = create_application()
    old_hook = sys.excepthook
    def exception_hook(kind, value, traceback):
        old_hook(kind, value, traceback)
        controller.notify_error(value)
    sys.excepthook = exception_hook
    try:
        return application.exec()
    finally:
        controller.close()
        sys.excepthook = old_hook
