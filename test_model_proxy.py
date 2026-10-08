"""Real local HTTP relay tests, including incremental SSE and cancellation."""
from contextlib import contextmanager
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import threading
import time
import unittest
from unittest.mock import patch

from model_proxy import ModelProxy


@contextmanager
def upstream(*, require_key=False, stream_gate=None, slow_gate=None, ipv6=False):
    seen = []
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_args):
            pass
        def send_payload(self, status, payload, content_type="application/octet-stream"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close, X-Upstream-Hop")
            self.send_header("X-Upstream-Hop", "discard")
            self.send_header("X-End-To-End", "preserve")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)
                self.wfile.flush()
        def handle_method(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            seen.append({"method": self.command, "path": self.path, "host": self.headers.get("Host"), "auth": self.headers.get("Authorization"), "body": body, "content_type": self.headers.get("Content-Type"), "hop": self.headers.get("X-Client-Hop")})
            expected_host = f"[::1]:{self.server.server_port}" if ipv6 else f"127.0.0.1:{self.server.server_port}"
            try:
                if self.headers.get("Host") != expected_host:
                    self.send_payload(403, b"foreign host")
                elif require_key and self.headers.get("Authorization") != "Bearer caller-key":
                    self.send_payload(401, b'{"error":{"code":"invalid_api_key"}}', "application/json")
                elif self.path == "/sse":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.write(b'data: {"choices":[{"delta":{"content":"A"}}]}\n\n')
                    self.wfile.flush()
                    if stream_gate is not None:
                        stream_gate.wait(3)
                    self.wfile.write(b'data: {"choices":[{"delta":{"content":"B"}}]}\n\ndata: [DONE]\n\n')
                    self.wfile.flush()
                elif self.path == "/slow":
                    if slow_gate is not None:
                        slow_gate.wait(3)
                    self.send_payload(200, b"ready")
                elif self.path == "/empty":
                    self.send_response(204)
                    self.send_header("Connection", "close")
                    self.end_headers()
                elif self.path == "/bad-gateway":
                    self.send_payload(429, b'{"error":"rate limit"}', "application/json")
                else:
                    self.send_payload(200, body if body else b"\x00\xffbinary\x80")
            except OSError:
                pass
        do_GET = do_POST = do_HEAD = do_OPTIONS = do_DELETE = do_PUT = do_PATCH = handle_method
    class Server(ThreadingHTTPServer):
        daemon_threads = True
        address_family = socket.AF_INET6 if ipv6 else socket.AF_INET
        def handle_error(self, *_args):
            pass
    host = "::1" if ipv6 else "127.0.0.1"
    server = Server((host, 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .05}, daemon=True)
    thread.start()
    try:
        yield host, server.server_port, seen
    finally:
        if stream_gate is not None:
            stream_gate.set()
        if slow_gate is not None:
            slow_gate.set()
        server.shutdown()
        server.server_close()
        thread.join(1)


class ProxyTests(unittest.TestCase):
    def test_rewrites_host_preserves_auth_binary_headers_and_keepalive(self):
        with upstream(require_key=True) as (host, port, seen), ModelProxy(host, port) as relay:
            client = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=2)
            try:
                headers = {"Host": "model.example.com", "Authorization": "Bearer caller-key", "Content-Type": "application/octet-stream", "Connection": "keep-alive, X-Client-Hop", "X-Client-Hop": "discard"}
                client.request("POST", "/v1/test?binary=1", body=b"\x00\xff\x80payload", headers=headers)
                before_socket = client.sock
                response = client.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b"\x00\xff\x80payload")
                self.assertEqual(response.getheader("X-End-To-End"), "preserve")
                self.assertIsNone(response.getheader("X-Upstream-Hop"))
                client.request("GET", "/second", headers={"Authorization": "Bearer caller-key"})
                response = client.getresponse()
                self.assertEqual(response.status, 200)
                response.read()
                self.assertIs(before_socket, client.sock)
                self.assertEqual(seen[0]["host"], f"127.0.0.1:{port}")
                self.assertEqual(seen[0]["auth"], "Bearer caller-key")
                self.assertEqual(seen[0]["path"], "/v1/test?binary=1")
                self.assertEqual(seen[0]["content_type"], "application/octet-stream")
                self.assertIsNone(seen[0]["hop"])
            finally:
                client.close()

    def test_does_not_add_auth_or_follow_upstream_errors(self):
        with upstream(require_key=True) as (host, port, seen), ModelProxy(host, port) as relay:
            client = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=2)
            try:
                client.request("GET", "/v1/models", headers={"Host": "foreign.example.com"})
                response = client.getresponse()
                self.assertEqual(response.status, 401)
                self.assertEqual(json.loads(response.read())["error"]["code"], "invalid_api_key")
                self.assertIsNone(seen[0]["auth"])
            finally:
                client.close()
        with upstream() as (host, port, _), ModelProxy(host, port) as relay:
            client = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=2)
            try:
                client.request("GET", "/bad-gateway")
                response = client.getresponse()
                self.assertEqual(response.status, 429)
                self.assertEqual(response.read(), b'{"error":"rate limit"}')
            finally:
                client.close()

    def test_sse_first_event_arrives_before_last_and_done_survives(self):
        gate = threading.Event()
        with upstream(stream_gate=gate) as (host, port, _), ModelProxy(host, port) as relay:
            client = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=2)
            try:
                started = time.monotonic()
                client.request("GET", "/sse")
                response = client.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader("Transfer-Encoding"), "chunked")
                first = response.read1(16384)
                self.assertIn(b'"content":"A"', first)
                self.assertFalse(gate.is_set())
                self.assertLess(time.monotonic() - started, 1)
                gate.set()
                remaining = response.read()
                self.assertIn(b'"content":"B"', remaining)
                self.assertIn(b"data: [DONE]", remaining)
            finally:
                gate.set()
                client.close()

    def test_chunked_request_decodes_binary_and_forwards_methods(self):
        with upstream() as (host, port, seen), ModelProxy(host, port) as relay:
            client = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=2)
            try:
                client.request("PATCH", "/v1/data?q=1", body=iter((b"\x00first", b"\xffsecond")), encode_chunked=True, headers={"Content-Type": "application/octet-stream"})
                response = client.getresponse()
                self.assertEqual(response.read(), b"\x00first\xffsecond")
                self.assertEqual(seen[-1]["method"], "PATCH")
                for method in ("OPTIONS", "DELETE", "PUT", "HEAD"):
                    client.request(method, "/v1/models")
                    response = client.getresponse()
                    self.assertEqual(response.status, 200)
                    payload = response.read()
                    self.assertEqual(payload, b"" if method == "HEAD" else b"\x00\xffbinary\x80")
                client.request("GET", "/empty")
                response = client.getresponse()
                self.assertEqual(response.status, 204)
                self.assertEqual(response.read(), b"")
            finally:
                client.close()

    def test_invalid_framing_body_bounds_and_headers(self):
        with upstream() as (host, port, seen), ModelProxy(host, port, max_body=8) as relay:
            messages = [
                (b"POST / HTTP/1.1\r\nHost: local\r\nContent-Length: 9\r\n\r\n", 413),
                (b"POST / HTTP/1.1\r\nHost: local\r\nContent-Length: 1\r\nTransfer-Encoding: chunked\r\n\r\n", 400),
                (b"POST / HTTP/1.1\r\nHost: local\r\nTransfer-Encoding: chunked\r\n\r\nZ\r\n", 400),
                (b"GET http://example.com/ HTTP/1.1\r\nHost: local\r\n\r\n", 400),
                (b"GET / HTTP/1.1\r\nHost: local\r\nUpgrade: websocket\r\n\r\n", 501),
                (b"GET / HTTP/1.1\r\nHost: local\r\nX-Large: " + b"x" * 65536 + b"\r\n\r\n", 431),
            ]
            for raw, status in messages:
                with self.subTest(status=status), socket.create_connection(("127.0.0.1", relay.port), timeout=2) as sock:
                    sock.sendall(raw)
                    response = http.client.HTTPResponse(sock)
                    response.begin()
                    self.assertEqual(response.status, status)
                    response.read()
            self.assertEqual(seen, [])

    def test_upstream_timeout_returns_504_and_close_is_quick(self):
        gate = threading.Event()
        with upstream(slow_gate=gate) as (host, port, _), ModelProxy(host, port, timeout=.15) as relay:
            client = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=2)
            try:
                client.request("GET", "/slow")
                response = client.getresponse()
                self.assertEqual(response.status, 504)
                response.read()
            finally:
                client.close()
                gate.set()
        relay.close()
        with self.assertRaises(RuntimeError):
            relay.start()

    def test_cancellation_interrupts_pending_headers_and_sse_no_threads(self):
        for path in ("/slow", "/sse"):
            cancel, gate = threading.Event(), threading.Event()
            kwargs = {"slow_gate": gate} if path == "/slow" else {"stream_gate": gate}
            with self.subTest(path=path), upstream(**kwargs) as (host, port, _):
                relay = ModelProxy(host, port, cancel).start()
                client = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=2)
                try:
                    client.request("GET", path)
                    if path == "/sse":
                        response = client.getresponse()
                        self.assertIn(b"data:", response.read1(16384))
                    time.sleep(.05)
                    started = time.monotonic()
                    cancel.set()
                    self.assertTrue(relay._closed.wait(1.5))
                    relay.close()
                    self.assertLess(time.monotonic() - started, 1.5)
                    self.assertFalse(relay._threads)
                    self.assertFalse(relay._sockets)
                    self.assertFalse(relay._server_thread.is_alive())
                finally:
                    relay.close()
                    gate.set()
                    client.close()

    def test_no_proxy_dns_and_ipv6_target(self):
        with upstream() as (host, port, _), patch("socket.getaddrinfo", side_effect=AssertionError("DNS should not be used")), patch("socket.getfqdn", side_effect=AssertionError("DNS should not be used")):
            with ModelProxy(host, port) as relay:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    sock.settimeout(2)
                    sock.connect(("127.0.0.1", relay.port))
                    sock.sendall(b"GET / HTTP/1.1\r\nHost: foreign.example\r\nConnection: close\r\n\r\n")
                    response = http.client.HTTPResponse(sock)
                    response.begin()
                    self.assertEqual(response.status, 200)
                    response.read()
                finally:
                    sock.close()
        try:
            with upstream(ipv6=True) as (host, port, seen), ModelProxy(host, port) as relay:
                client = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=2)
                try:
                    client.request("GET", "/")
                    response = client.getresponse()
                    self.assertEqual(response.status, 200)
                    response.read()
                    self.assertEqual(seen[0]["host"], f"[::1]:{port}")
                finally:
                    client.close()
        except OSError as exc:
            self.skipTest(f"IPv6 unavailable: {exc}")

    def test_rejects_non_loopback_targets_and_pre_cancelled_start(self):
        for host in ("example.com", "localhost", "0.0.0.0", "192.168.0.1", "::", "::1%1"):
            with self.subTest(host=host), self.assertRaises(ValueError):
                ModelProxy(host, 8080)
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(RuntimeError):
            ModelProxy("127.0.0.1", 8080, cancel).start()


if __name__ == "__main__":
    unittest.main()
