"""Real relay/process integration: health follows the model, then cleans up.

An isolated Python child provides FRPC-style readiness messages. It never makes
an external tunnel connection or downloads an engine.
"""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
from unittest.mock import patch

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from qt_ui import Controller
from tunnel_core import EngineStore, WindowsJob


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        raw = b'{"object":"list","data":[{"id":"fixture-model","object":"model"}]}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class Upstream(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port=0):
        super().__init__(("127.0.0.1", port), Handler)
        self.worker = threading.Thread(target=self.serve_forever, daemon=True)
        self.worker.start()

    def close(self):
        self.shutdown()
        self.server_close()
        self.worker.join(2)


def main():
    app = QApplication.instance() or QApplication([])
    real_monotonic = time.monotonic
    offset = [0.0]
    def accelerated_clock():
        return real_monotonic() + offset[0]
    def wait_for(predicate, timeout=5):
        deadline = real_monotonic() + timeout
        while not predicate() and real_monotonic() < deadline:
            QTest.qWait(20)
        assert predicate(), "Timed out waiting for a worker or GUI status"
    def relay_status(port):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
        try:
            connection.request("GET", "/v1/models")
            response = connection.getresponse()
            response.read()
            return response.status
        finally:
            connection.close()
    upstream = Upstream()
    original_port = upstream.server_port
    upstream_stopped = False
    restored = None
    processes, proxy_ports, failures = [], [], []
    original_launch = WindowsJob.launch
    with tempfile.TemporaryDirectory() as folder:
        controller = Controller(Path(folder) / "appearance.json")
        controller.fields.update(mode="FRP", protocol="HTTP", port=str(original_port),
                                 server="fixture.example", remote_port="18080")
        controller.api_target = "127.0.0.1"
        controller.errorRaised.connect(failures.append)
        def launch_fixture(job, args, cwd, env, cancel):
            config = json.loads(Path(args[-1]).read_text(encoding="utf-8"))
            proxy_ports.append(config["proxies"][0]["localPort"])
            assert config["proxies"][0]["localIP"] == "127.0.0.1"
            script = ("import time\n"
                      "print('start proxy success', flush=True)\n"
                      "while True:\n"
                      "    time.sleep(.15)\n"
                      "    print('fixture heartbeat', flush=True)\n")
            process = original_launch(job, [sys.executable, "-u", "-c", script], cwd, env, cancel)
            processes.append(process)
            return process
        try:
            with patch.object(EngineStore, "ensure", return_value=Path(sys.executable)), \
                    patch.object(WindowsJob, "launch", new=launch_fixture), \
                    patch("tunnel_core.time.monotonic", side_effect=accelerated_clock):
                controller.start()
                wait_for(lambda: controller.status == "已连接")
                assert len(proxy_ports) == 1 and proxy_ports[0] != original_port
                proxy_port = proxy_ports[0]
                assert relay_status(proxy_port) == 200
                upstream.close()
                upstream_stopped = True
                # The relay remains reachable, so checking its listening port
                # instead of the original upstream would incorrectly succeed.
                with socket.create_connection(("127.0.0.1", proxy_port), timeout=2):
                    pass
                offset[0] += 11
                wait_for(lambda: controller.status == "隧道已连接 · 本地服务不可用")
                assert relay_status(proxy_port) in (502, 504)
                wait_for(lambda: "本地服务已停止或无法连接" in controller.logText)
                assert controller.active and processes[0].poll() is None

                restored = Upstream(original_port)
                offset[0] += 11
                wait_for(lambda: controller.status == "已连接")
                wait_for(lambda: "本地服务已恢复" in controller.logText)
                assert relay_status(proxy_port) == 200

                controller.stop()
                controller.worker.join(4)
                controller.pump()
                assert not controller.worker.is_alive() and not controller.active
                assert processes[0].poll() is not None
                try:
                    with socket.create_connection(("127.0.0.1", proxy_port), timeout=.5):
                        pass
                except OSError:
                    pass
                else:
                    raise AssertionError("The model relay listener survived tunnel stop")
                assert not failures, failures
            print("PASS original model health loss/restoration behind a live relay, Windows child termination and relay cleanup")
        finally:
            controller.close()
            if controller.worker:
                controller.worker.join(4)
            app.processEvents()
            if not upstream_stopped:
                upstream.close()
            if restored is not None:
                restored.close()


if __name__ == "__main__":
    main()
