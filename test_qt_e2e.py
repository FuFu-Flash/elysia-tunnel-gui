"""Explicit opt-in: briefly expose a fixed test response through Cloudflare."""
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PySide6.QtCore import QTimer
from qt_ui import create_application


def main():
    marker = b"elysia-qt-migration-test-only"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(marker)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory() as temporary:
        application, engine, controller, window = create_application(Path(temporary) / "appearance.json")
        controller.setField("mode", "Cloudflare")
        controller.setField("port", str(server.server_port))
        controller.core.cache = Path(__file__).resolve().parent / ".test-engines"
        errors = []
        controller.errorRaised.connect(errors.append)
        fetched = threading.Event()
        fetch_error = []
        state = {"phase": "connect", "fetching": False, "deadline": time.monotonic() + 120, "passed": False}

        def fetch(address):
            try:
                for attempt in range(8):
                    try:
                        with urllib.request.urlopen(address, timeout=10) as response:
                            assert response.read() == marker
                        break
                    except Exception:
                        if attempt == 7:
                            raise
                        time.sleep(1)
            except Exception as exc:
                fetch_error.append(repr(exc))
            finally:
                fetched.set()

        def tick():
            if errors or fetch_error or time.monotonic() > state["deadline"]:
                print("FAIL", errors, fetch_error, controller.status, flush=True)
                controller.close()
                application.quit()
                return
            if state["phase"] == "connect" and controller.address and controller.status == "已连接":
                if not state["fetching"]:
                    state["fetching"] = True
                    threading.Thread(target=fetch, args=(controller.address,), daemon=True).start()
                elif fetched.is_set():
                    print("PASS public HTTPS response through Qt controller", flush=True)
                    controller.stop()
                    state["phase"] = "stop"
            elif state["phase"] == "stop" and not controller.active:
                assert controller.core.job is None
                print("PASS stop cleanup", flush=True)
                controller.start()
                state["phase"] = "restart"
            elif state["phase"] == "restart" and controller.status == "已连接" and controller.address:
                controller.restart()
                state["phase"] = "reconnect"
                state["run_id"] = controller.core.run_id
            elif state["phase"] == "reconnect" and controller.core.run_id > state["run_id"] and controller.status == "已连接":
                print("PASS restart reconnect", flush=True)
                controller.close()
                state["phase"] = "close"
            elif state["phase"] == "close" and not controller.worker.is_alive():
                assert controller.core.job is None
                state["passed"] = True
                print("PASS close worker/job cleanup", flush=True)
                application.quit()

        timer = QTimer()
        timer.setInterval(100)
        timer.timeout.connect(tick)
        timer.start()
        QTimer.singleShot(200, controller.start)
        try:
            application.exec()
        finally:
            controller.close()
            server.shutdown()
            server.server_close()
        return 0 if state["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
