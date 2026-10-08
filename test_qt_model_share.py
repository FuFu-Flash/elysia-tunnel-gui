"""Actual Qt model-share page regression using read-only loopback fixtures.

No public tunnel, account login, engine download, or inference is performed.
Screenshots contain only this application's client area and fixture metadata.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import tempfile
import threading
import time
from unittest.mock import patch

from PySide6.QtCore import QPoint, QPointF, Qt, qInstallMessageHandler
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

import model_share
from qt_ui import create_application


TEST_KEY = "model-ui-fixture-key"


class FixtureApi(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, kind):
        super().__init__(("127.0.0.1", 0), FixtureHandler)
        self.kind = kind
        self.requests = []
        self.posts = 0
        self.worker = threading.Thread(target=self.serve_forever, daemon=True)
        self.worker.start()

    @property
    def port(self):
        return self.server_address[1]

    def close(self):
        self.shutdown()
        self.server_close()
        self.worker.join(2)


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.server.requests.append((self.path, self.headers.get("Authorization", "")))
        status, body = 404, {"error": "not found"}
        if self.server.kind == "ollama" and self.path == "/api/tags":
            status, body = 200, {"models": [{"name": "qwen3:8b", "model": "qwen3:8b", "digest": "fixture"}]}
        elif self.server.kind in ("openai", "protected") and self.path == "/v1/models":
            if self.server.kind == "protected" and self.headers.get("Authorization") != "Bearer " + TEST_KEY:
                status, body = 401, {"error": {"code": "invalid_api_key", "message": "An API key is required"}}
            else:
                status, body = 200, {"object": "list", "data": [
                    {"id": "local-model-alpha", "object": "model"},
                    {"id": "local-model-beta", "object": "model"}]}
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        self.server.posts += 1
        self.send_response(405)
        self.end_headers()


def wait_for(predicate, timeout=7):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(20)
    assert predicate(), "Timed out waiting for a Qt-thread result"


def descendants(item):
    for child in item.childItems():
        yield child
        yield from descendants(child)


def variant(value):
    return value.toVariant() if hasattr(value, "toVariant") else value


def is_drawn(item):
    while item is not None:
        if not item.isVisible() or item.opacity() < .01:
            return False
        item = item.parentItem()
    return True


def main():
    output = Path(".tools/model-share-pixels")
    output.mkdir(parents=True, exist_ok=True)
    servers = [FixtureApi(kind) for kind in ("openai", "ollama", "protected")]
    openai, ollama, protected = servers
    warnings, layout_failures, errors, configs, layout_results = [], [], [], [], []
    previous_handler = qInstallMessageHandler(lambda _kind, _context, text: warnings.append(text))
    manager = None
    try:
        with tempfile.TemporaryDirectory() as folder:
            app, engine, manager, window = create_application(Path(folder) / "appearance.json")
            manager.errorRaised.connect(errors.append)
            share = manager.model_share
            window.resize(1240, 780)
            QTest.qWait(300)

            def item(name):
                found = window.findChild(QQuickItem, name)
                assert found is not None, name + " is missing"
                return found

            def by_text(scope, text):
                found = next((child for child in descendants(scope)
                              if child.property("text") == text and child.metaObject().indexOfSignal("clicked()") >= 0), None)
                assert found is not None, "No clickable control: " + text
                return found

            def click(control):
                target = item(control) if isinstance(control, str) else control
                assert target.isEnabled(), str(target.property("text")) + " is disabled"
                ancestor = target.parentItem()
                while ancestor is not None:
                    if ancestor.metaObject().indexOfProperty("contentY") >= 0:
                        top = target.mapToScene(QPointF(0, 0)).y()
                        viewport_top = ancestor.mapToScene(QPointF(0, 0)).y()
                        viewport_bottom = viewport_top + ancestor.height()
                        delta = top - viewport_top - 12 if top < viewport_top else top + target.height() - viewport_bottom + 12 if top + target.height() > viewport_bottom else 0
                        if delta:
                            maximum = max(0, float(ancestor.property("contentHeight")) - ancestor.height())
                            ancestor.setProperty("contentY", max(0, min(maximum, float(ancestor.property("contentY")) + delta)))
                            QTest.qWait(120)
                    ancestor = ancestor.parentItem()
                location = target.mapToScene(QPointF(target.width() / 2, target.height() / 2)).toPoint()
                assert 0 <= location.x() < window.width() and 0 <= location.y() < window.height(), "Control is outside the viewport"
                QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, location)

            def snapshot(name):
                QTest.qWait(80)
                image = window.grabWindow()
                assert not image.isNull(), name + ": no rendered frame"
                image.save(str(output / (name + ".png")))
                # Exclude the persistent toolbar: it must not disguise a blank
                # page during a transition.
                header = round(88 * image.height() / window.height())
                body = image.copy(0, header, image.width(), image.height() - header)
                small = body.scaled(160, 120).convertToFormat(QImage.Format.Format_RGB32)
                raw = bytes(small.constBits())
                dark = sum(max(raw[index:index + 3]) < 145 for index in range(0, len(raw), 4))
                assert dark > 35, name + ": page is blank or its content disappeared"
                return raw

            def bounds(control):
                target = item(control)
                top = target.mapToScene(QPointF(0, 0))
                return tuple(round(value, 1) for value in (top.x(), top.y(), target.width(), target.height()))

            def check_layout(size, language):
                window.resize(*size)
                manager.setPreference("language", language)
                QTest.qWait(350)
                page = item("modelSharePage")
                assert float(page.property("contentWidth")) <= page.width() + 1, "Horizontal scrolling is required"
                for name in ("scanModelsButton", "shareModelSelector", "startModelShareButton", "stopModelShareButton", "copyModelBaseUrl", "copyModelSnippet"):
                    x, y, width, height = bounds(name)
                    layout_results.append({"size": size, "language": language, "control": name, "bounds": (x, y, width, height)})
                    if x < 0 or x + width > window.width() + 1 or y < 88 or y + height > window.height():
                        layout_failures.append(f"{size}, {language}, {name}: bounds {(x, y, width, height)}")
                snapshot(f"layout-{size[0]}x{size[1]}-{language}")
                (output / "layout-bounds.json").write_text(json.dumps(layout_results, indent=2), encoding="utf-8")

            navigation = item("mainNavigation")
            with patch("model_share.listening_ports", return_value=[server.port for server in servers]):
                click(by_text(navigation, "模型分享"))
                assert window.property("modelOpen") and share.scan_busy, "Actual navigation must initiate discovery"
                wait_for(lambda: not share.scan_busy)
            QTest.qWait(450)
            assert len(share.state["services"]) == 3
            assert {row["kind"] for row in share.state["services"]} == {"openai", "ollama", "candidate"}
            snapshot("zh-detected-quick")

            def select_service(port):
                listing = item("modelServiceList")
                index = next(index for index, row in enumerate(share.state["services"]) if row["port"] == port)
                listing.setProperty("contentY", min(index * 82, max(0, float(listing.property("contentHeight")) - listing.height())))
                QTest.qWait(100)
                target = next((child for child in descendants(listing)
                               if isinstance(variant(child.property("modelData")), dict)
                               and variant(child.property("modelData")).get("port") == port
                               and child.metaObject().indexOfSignal("clicked()") >= 0), None)
                assert target is not None, "The service delegate was not instantiated"
                click(target)
                QTest.qWait(100)
                assert share.state["selectedService"]["port"] == port

            select_service(protected.port)
            assert not item("startModelShareButton").isEnabled()
            snapshot("zh-auth-candidate")
            item("modelPortField").setProperty("text", "0")
            click("probeModelButton")
            assert not share.scan_busy and share.notice
            snapshot("zh-invalid-port")
            item("modelPortField").setProperty("text", str(protected.port))
            item("modelApiKeyField").setProperty("text", TEST_KEY)
            click("probeModelButton")
            assert item("modelApiKeyField").property("text") == "", "Probe key must be cleared after dispatch"
            wait_for(lambda: not share.scan_busy)
            assert share.state["selectedService"]["verified"]
            assert TEST_KEY not in json.dumps(share.state)

            original_discover = model_share.discover_services
            release_scan = threading.Event()
            def delayed_discover(ports, cancel=None):
                release_scan.wait(2)
                return original_discover(ports, cancel=cancel)
            with patch("model_share.discover_services", side_effect=delayed_discover), patch("model_share.listening_ports", return_value=[openai.port, ollama.port]):
                click("scanModelsButton")
                assert share.scan_busy and not item("scanModelsButton").isEnabled()
                snapshot("zh-scan-busy")
                release_scan.set()
                wait_for(lambda: not share.scan_busy)
            with patch("model_share.discover_services", side_effect=OSError("fixture failure")), patch("model_share.listening_ports", return_value=[]):
                click("scanModelsButton")
                wait_for(lambda: not share.scan_busy)
            assert share.state["scanError"] and len(share.state["services"]) == 2
            snapshot("zh-scan-error-recovery")

            with patch("model_share.listening_ports", return_value=[openai.port, ollama.port]):
                click("scanModelsButton")
                wait_for(lambda: not share.scan_busy)

            select_service(openai.port)
            click(by_text(item("modelTransportChoice"), "FRP"))
            assert share.state["transport"] == "FRP"
            manager.setField("server", "fixture-frps.example")
            manager.setField("remote_port", "18080")
            manager.saveServer("Fixture FRPS", False)
            QTest.qWait(100)
            snapshot("zh-frp")
            for size in ((1240, 780), (1180, 720)):
                for language in ("zh_CN", "en"):
                    check_layout(size, language)
            window.resize(1240, 780)
            manager.setPreference("language", "en")
            QTest.qWait(180)

            # Every new static translatable string has an English catalog
            # entry, and the rendered page uses it immediately after switching.
            qml_text = Path("qml/ModelSharePage.qml").read_text(encoding="utf-8")
            phrases = re.findall(r'\.tr\("([^"\\]*(?:\\.[^"\\]*)*)"\)', qml_text)
            missing = [phrase for phrase in phrases if re.search(r"[\u3400-\u9fff]", phrase)
                       and manager.translate(phrase, "en") == phrase]
            assert not missing, "Missing English model-page strings: " + repr(missing)
            visible_text = [str(child.property("text")) for child in descendants(item("modelSharePage"))
                            if is_drawn(child) and child.property("text")]
            assert "Detect again" in visible_text or "Scan again" in visible_text or manager.translate("重新检测", "en") in visible_text
            assert manager.translate("开始分享 ♪", "en") in visible_text
            snapshot("en-frp")

            def run(run_id, config, cancel):
                configs.append(config.copy())
                try:
                    manager.current.core.emit(run_id, "address", "http://fixture.example:18080")
                    manager.current.core.emit(run_id, "connected", "已连接")
                    cancel.wait(20)
                finally:
                    manager.current.core.emit(run_id, "done", None)
            manager.current.core.run = run
            click("shareModelSelector")
            QTest.keyClick(window, Qt.Key.Key_End)
            QTest.keyClick(window, Qt.Key.Key_Return)
            QTest.qWait(250)
            assert share.state["selectedModel"] == "local-model-beta", "Model dropdown did not update the share selection"
            click("startModelShareButton")
            wait_for(lambda: bool(share.state["shareBaseUrl"]))
            assert configs[-1]["api_host"] == "127.0.0.1" and configs[-1]["mode"] == "FRP"
            assert not item("startModelShareButton").isEnabled() and item("stopModelShareButton").isEnabled()
            click("copyModelBaseUrl")
            assert app.clipboard().text() == "http://fixture.example:18080/v1"
            click(by_text(item("modelSharePage"), manager.translate("复制模型 ID", "en")))
            assert app.clipboard().text() == "local-model-beta"
            click("copyModelSnippet")
            assert app.clipboard().text() == share.state["snippet"]
            assert '"stream": False' in app.clipboard().text() and TEST_KEY not in app.clipboard().text()
            snapshot("en-sharing-client")
            click("stopModelShareButton")
            wait_for(lambda: not manager.active)

            # Settings returns to the model page and never replaces it with a
            # blank frame. Reduced motion changes destination immediately.
            manager.setPreference("motion", True)
            manager.setPreference("speed", 1.)
            before_settings = snapshot("model-before-settings")
            click("settingsButton")
            QTest.qWait(170)
            enter_middle = snapshot("settings-enter-midframe")
            QTest.qWait(700)
            assert window.property("settingsOpen") and window.property("modelOpen")
            settings_pixels = snapshot("settings-enter-complete")
            difference = lambda first, second: sum(abs(a - b) for a, b in zip(first, second)) / len(first)
            assert difference(enter_middle, before_settings) > 1 and difference(enter_middle, settings_pixels) > 1, "Settings did not render an intermediate animation frame"
            click("backButton")
            QTest.qWait(170)
            return_middle = snapshot("settings-return-midframe")
            QTest.qWait(700)
            assert not window.property("settingsOpen") and window.property("modelOpen")
            restored_pixels = snapshot("model-restored-from-settings")
            assert difference(return_middle, settings_pixels) > 1 and difference(return_middle, restored_pixels) > 1, "Return did not render an intermediate animation frame"
            manager.setPreference("motion", False)
            click("settingsButton")
            QTest.qWait(25)
            assert float(item("pageStrip").property("x")) == -window.width()
            click("backButton")
            QTest.qWait(25)
            assert float(item("pageStrip").property("x")) == 0 and window.property("modelOpen")

            with patch("model_share.listening_ports", return_value=[]) as empty_scan:
                click("scanModelsButton")
                # An empty scan can finish during QTest.mouseClick's event pump.
                # Assert that the click dispatched discovery, then await completion.
                wait_for(lambda: empty_scan.called)
                wait_for(lambda: not share.scan_busy)
            assert not share.state["services"] and not item("startModelShareButton").isEnabled()
            snapshot("en-empty")
            manager.setPreference("language", "zh_CN")
            window.resize(640, 560)
            QTest.qWait(150)
            page = item("modelSharePage")
            assert float(page.property("contentWidth")) <= page.width() + 1
            flickable = next((child for child in descendants(page)
                             if child.metaObject().indexOfProperty("contentY") >= 0
                             and child.metaObject().indexOfProperty("contentHeight") >= 0
                             and float(child.property("contentHeight")) > page.height()), None)
            assert flickable is not None, "Narrow layout must retain vertical scrolling"
            snapshot("zh-narrow-top")
            flickable.setProperty("contentY", max(0, float(flickable.property("contentHeight")) - flickable.height()))
            QTest.qWait(100)
            snapshot("zh-narrow-bottom")
            x, y, width, height = bounds("copyModelSnippet")
            assert 0 <= x and x + width <= window.width() + 1 and 88 <= y and y + height <= window.height(), "Bottom sharing actions are inaccessible in the narrow layout"

            assert not errors, errors
            assert all(server.posts == 0 for server in servers), "Discovery triggered inference"
            assert all(path in ("/api/tags", "/v1/models") for server in servers for path, _auth in server.requests)
            actionable = [text for text in warnings if "qml" in text.lower()
                          and any(token in text.lower() for token in ("warning", "error", "unable", "cannot", "binding loop"))]
            assert not actionable, "QML warnings: " + repr(actionable)
            if layout_failures:
                raise AssertionError("Landscape primary-action layout:\n" + "\n".join(layout_failures))
            print("PASS real Qt model-page navigation, read-only detection, auth candidates, port/key probe, loading/error/empty states, English switching, bound client clipboard, transitions, reduced motion and landscape/narrow layouts")
    finally:
        if warnings:
            (output / "qt-warnings.json").write_text(json.dumps(warnings, ensure_ascii=False, indent=2), encoding="utf-8")
        if manager is not None:
            manager.close()
            for session in manager.sessions.values():
                if session.worker:
                    session.worker.join(2)
        qInstallMessageHandler(previous_handler)
        for server in servers:
            server.close()


if __name__ == "__main__":
    main()
