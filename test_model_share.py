"""Model sharing integration with real loopback APIs and isolated tunnel events.

No Cloudflare login, engine download, public tunnel, or inference request is made.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import time
from unittest.mock import patch
import urllib.error

from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import i18n
from model_share import MODEL_EN, ModelShare, model_binding_matches
from qt_ui import Controller
from tunnel_manager import TunnelManager


SECRET = "integration-test-key-not-for-publication"


class LocalApi(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, kind):
        super().__init__(("127.0.0.1", 0), Handler)
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


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        auth = self.headers.get("Authorization", "")
        self.server.requests.append((self.path, auth))
        status, body = 404, {"error": "not found"}
        if self.server.kind == "protected" and self.path == "/v1/models":
            if auth == "Bearer " + SECRET:
                status, body = 200, {"object": "list", "data": [
                    {"id": "local-chat-model", "object": "model"},
                    {"id": "another-model", "object": "model"}]}
            else:
                status, body = 401, {"error": {"code": "invalid_api_key", "message": "check your key"}}
        elif self.server.kind == "ollama" and self.path == "/api/tags":
            status, body = 200, {"models": [{"name": "qwen:latest", "model": "qwen:latest", "digest": "fixture"}]}
        elif self.server.kind == "ordinary":
            status, body = 200, {"data": ["this is not a model API"]}
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


def wait_for(predicate, timeout=6):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(20)
    assert predicate(), "Timed out waiting for a GUI-thread result"


def install_runner(session, configs, name):
    def run(run_id, config, cancel):
        configs.append((name, config.copy()))
        try:
            address = "http://fixture.example:" + str(config["remote_port"]) if config["mode"] == "FRP" else "https://fixture.example"
            session.core.emit(run_id, "address", address)
            session.core.emit(run_id, "connected", "已连接")
            session.core.log("fixture-" + name)
            cancel.wait(15)
        finally:
            session.core.emit(run_id, "done", None)
    session.core.run = run


def stop_runner(manager):
    manager.stopAll()
    for session in manager.sessions.values():
        if session.worker:
            session.worker.join(3)
    manager.pump()


def check_client_redirect_guard(share):
    """A copied client must never carry its key to a second HTTP origin."""
    hits = []
    initial_auth = []
    class Sink(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass
        def do_GET(self):
            hits.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()
    sink = ThreadingHTTPServer(("127.0.0.1", 0), Sink)
    class Redirect(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            initial_auth.append(self.headers.get("Authorization"))
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{sink.server_port}/capture")
            self.send_header("Content-Length", "0")
            self.end_headers()
    redirect = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    workers = [threading.Thread(target=server.serve_forever, daemon=True) for server in (sink, redirect)]
    for worker in workers:
        worker.start()
    try:
        snippet = share._snippet(f"http://127.0.0.1:{redirect.server_port}/v1", "fixture-model")
        with patch.dict(os.environ, {"MODEL_API_KEY": SECRET}), patch("urllib.request.getproxies", return_value={}):
            try:
                exec(compile(snippet, "copied-client", "exec"), {})
            except urllib.error.HTTPError as error:
                assert error.code == 302
                error.close()
            else:
                raise AssertionError("The client followed an API redirect")
        assert initial_auth == ["Bearer " + SECRET]
        assert hits == [], "The second origin received a redirected request"
    finally:
        for server in (sink, redirect):
            server.shutdown()
            server.server_close()
        for worker in workers:
            worker.join(2)


def main():
    app = QApplication.instance() or QApplication([])
    i18n.EN.update(MODEL_EN)
    servers = [LocalApi(kind) for kind in ("protected", "ollama", "ordinary")]
    protected, ollama, ordinary = servers
    with tempfile.TemporaryDirectory() as folder:
        manager = TunnelManager(Controller, Path(folder) / "appearance.json")
        share = manager.__dict__.get("model_share") or ModelShare(manager)
        failures, configs = [], []
        manager.errorRaised.connect(failures.append)
        try:
            assert share.state["services"] == [] and not share.state["scanComplete"]
            with patch("model_share.listening_ports", return_value=[server.port for server in servers]):
                share.scan()
                assert share.state["scanBusy"]
                wait_for(lambda: not share.state["scanBusy"])
            rows = share.state["services"]
            assert len(rows) == 2
            assert not any(row["port"] == ordinary.port for row in rows)
            candidate = next(row for row in rows if row["port"] == protected.port)
            assert not candidate["verified"] and candidate["authRequired"]
            share.selectService(candidate["id"])
            before = manager.fields.copy()
            share.startShare()
            assert not manager.active and manager.fields == before
            assert "verified" in manager.tr_text(share.notice) if manager.preferences["language"] == "en" else share.notice

            # Explicit port accepts digits only; it cannot be used as a URL or
            # trick discovery into contacting a remote host.
            share.probePort("https://remote.example:8080", SECRET)
            assert not share.scan_busy and not manager.active
            share.probePort("9" * 5000, SECRET)
            assert not share.scan_busy
            share.probePort(str(protected.port), SECRET + "\nHeader: value")
            assert not share.scan_busy
            share.probePort(str(protected.port), SECRET)
            wait_for(lambda: not share.state["scanBusy"])
            selected = share.state["selectedService"]
            assert selected["verified"] and selected["authRequired"]
            assert selected["models"] == ["local-chat-model", "another-model"]
            assert SECRET not in json.dumps(share.state)
            assert all(not auth for path, auth in protected.requests if path == "/api/tags")

            # Failed scans keep a previously verified selection and results.
            previous = share.state["services"]
            with patch("model_share.discover_services", side_effect=OSError("test only")), patch("model_share.listening_ports", return_value=[]):
                share.scan()
                wait_for(lambda: not share.scan_busy)
            assert share.state["services"] == previous and share.state["scanError"]

            # FRP is explicitly selected and only the chosen session is bound.
            manager.setField("server", "frps.example")
            manager.setField("remote_port", "18080")
            manager.saveServer("Fixture server", False)
            first = manager.selected
            install_runner(manager.current, configs, "one")
            share.setTransport("FRP")
            share.selectModel("another-model")
            share.startShare()
            wait_for(lambda: bool(share.state["shareBaseUrl"]))
            assert manager.active and share.state["shareActive"]
            assert manager.fields["mode"] == "FRP" and manager.fields["protocol"] == "HTTP"
            assert configs[-1][1]["api_host"] == "127.0.0.1"
            assert share.state["shareBaseUrl"] == "http://fixture.example:18080/v1"
            assert share.state["selectedModel"] == "another-model"
            assert "\"stream\": False" in share.state["snippet"]
            assert "MODEL_API_KEY" in share.state["snippet"] and SECRET not in share.state["snippet"]
            compile(share.state["snippet"], "client-example", "exec")
            check_client_redirect_guard(share)
            QTest.qWait(80)
            share.copyBaseUrl()
            wait_for(lambda: QGuiApplication.clipboard().text() == share.state["shareBaseUrl"], 2)
            QTest.qWait(80)
            share.copySnippet()
            wait_for(lambda: QGuiApplication.clipboard().text() == share.state["snippet"], 2)
            QTest.qWait(80)
            share.copyModel()
            wait_for(lambda: QGuiApplication.clipboard().text() == "another-model", 2)
            manager.save()
            raw = manager.store.path.read_text(encoding="utf-8")
            assert "modelService" in raw and SECRET not in raw and SECRET not in manager.logText
            assert model_binding_matches(manager.profiles[first]["modelService"], manager.current)

            # Active target selection stays pinned; discovery must not silently
            # reconfigure its port or transport underneath the running tunnel.
            pinned_fields = manager.fields.copy()
            share.selectService(next(row["id"] for row in rows if row["kind"] == "ollama"))
            share.setTransport("quick")
            assert manager.fields == pinned_fields and share.state["transport"] == "FRP"

            # Create a model session while the first runs: FRPS settings are
            # reused, remote ports are unique, and old output never leaks in.
            share.createTunnel()
            second = manager.selected
            assert second != first and manager.fields["remote_port"] == "18081"
            assert manager.fields["server"] == "frps.example"
            assert not share.state["shareActive"] and not share.state["shareBaseUrl"]
            share.copyBaseUrl()
            assert QGuiApplication.clipboard().text() == "another-model"
            manager.current.address = "http://unrelated.example:18081"
            manager.current.active = True
            assert not share.state["shareBaseUrl"]
            share.stopShare()
            assert manager.current.active, "Sharing controls must not stop an unrelated tunnel"
            manager.current.active = False
            manager.current.address = ""
            ollama_row = next(row for row in rows if row["kind"] == "ollama")
            share.selectService(ollama_row["id"])
            share.setTransport("fixed")
            share.startShare()
            assert not manager.active and not manager.profiles[second].get("modelService")
            assert share.notice == "请先在设置中准备好固定域名，再来分享模型。"
            share.setTransport("quick")
            install_runner(manager.current, configs, "two")
            share.startShare()
            wait_for(lambda: bool(share.state["shareBaseUrl"]))
            assert share.state["shareBaseUrl"] == "https://fixture.example/v1"
            assert configs[-1][1]["mode"] == "Cloudflare" and "cloudflare_fixed" not in configs[-1][1]
            assert not manager.current.cloudflare.data["enabled"]
            assert "SSE" in share.state["notice"]
            manager.selectTunnel(first)
            assert share.state["shareBaseUrl"] == "http://fixture.example:18080/v1"
            assert share.state["selectedModel"] == "another-model"
            share.stopShare()
            wait_for(lambda: not manager.current.active)
            assert manager.sessions[second].active and not share.state["shareBaseUrl"]
            manager.selectTunnel(second)
            stop_runner(manager)
            assert not share.state["shareBaseUrl"]
            original_port = manager.fields["port"]
            manager.setField("port", "8089")
            assert not model_binding_matches(manager.profiles[second]["modelService"], manager.current)
            manager.setField("port", original_port)
            manager.save()

            # Metadata survives restart without a remembered API key, without
            # automatically claiming a live service, and without auto-start.
            reopened = TunnelManager(Controller, Path(folder) / "appearance.json")
            reopened_share = reopened.__dict__.get("model_share") or ModelShare(reopened)
            try:
                assert not any(session.active for session in reopened.sessions.values())
                assert reopened_share.state["selectedService"] == {}
                assert not reopened_share.state["shareBaseUrl"]
                assert reopened.profiles[second]["modelService"]["models"] == ["qwen:latest"]
                reopened_configs = []
                install_runner(reopened.current, reopened_configs, "restored")
                reopened.start()
                wait_for(lambda: bool(reopened_share.state["shareBaseUrl"]))
                assert reopened_configs[-1][1]["api_host"] == "127.0.0.1"
                restarted = reopened.current.core.run_id
                reopened.restart()
                wait_for(lambda: reopened.current.core.run_id > restarted and bool(reopened_share.state["shareBaseUrl"]))
                assert reopened_configs[-1][1]["api_host"] == "127.0.0.1"
                stop_runner(reopened)
                reopened.setField("port", "8089")
                assert reopened.current.api_target is None
                reopened.current.start()
                wait_for(lambda: reopened.current.active and len(reopened_configs) == 3)
                assert "api_host" not in reopened_configs[-1][1]
                assert not reopened_share.state["shareBaseUrl"]
                stop_runner(reopened)
            finally:
                reopened_share.close()
                reopened.close()

            # Closing cancels discovery and ignores already queued/stale data.
            entered, finished = threading.Event(), threading.Event()
            def cancellable(_ports, cancel=None):
                entered.set()
                cancel.wait(3)
                finished.set()
                return [selected]
            with patch("model_share.discover_services", side_effect=cancellable), patch("model_share.listening_ports", return_value=[]):
                share.scan()
                assert entered.wait(2)
                before_close = list(share.services)
                share.close()
                assert finished.wait(2)
                share.worker.join(2)
                share._pump()
                assert share.services == before_close
            assert all(server.posts == 0 for server in servers), "Discovery must never trigger inference"
            assert not failures, failures
            print("PASS local API discovery, explicit key verification, scan recovery, isolated sharing, transport guards, safe client examples, secret-free persistence and cancellation")
        finally:
            share.close()
            manager.close()
            for session in manager.sessions.values():
                if session.worker:
                    session.worker.join(3)
            app.processEvents()
    for server in servers:
        server.close()


if __name__ == "__main__":
    main()
