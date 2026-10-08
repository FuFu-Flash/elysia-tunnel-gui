"""Local HTTP fixture tests: discovery must never run model inference."""
from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import socket
import threading
import time
import unittest
from unittest.mock import patch

import model_api


@contextmanager
def fixture(routes, *, ipv6=False):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_args):
            pass
        def do_GET(self):
            requests.append((self.command, self.path, self.headers.get("Authorization")))
            result = routes(self.path, self.headers) if callable(routes) else routes.get(self.path)
            if result is None:
                result = (404, "text/plain", b"not found", {})
            status, content_type, body, headers = result
            if callable(body):
                try:
                    body(self)
                except OSError:
                    pass
                return
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            for name, value in headers.items():
                self.send_header(name, value)
            self.end_headers()
            try:
                self.wfile.write(body)
            except OSError:
                pass
    class Server(ThreadingHTTPServer):
        daemon_threads = True
        address_family = socket.AF_INET6 if ipv6 else socket.AF_INET
    host = "::1" if ipv6 else "127.0.0.1"
    server = Server((host, 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield host, server.server_port, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def json_response(value, status=200, headers=None):
    return status, "application/json", value, headers or {}


OPENAI_MODELS = {"object": "list", "data": [{"id": "local-model", "object": "model"}]}


class DiscoveryTests(unittest.TestCase):
    def test_openai_recognition_does_not_guess_vendor_or_use_proxy(self):
        with fixture({"/v1/models": json_response(OPENAI_MODELS)}) as (host, port, requests):
            with patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:1", "HTTPS_PROXY": "http://127.0.0.1:1", "NO_PROXY": ""}):
                rows = model_api.discover_services([port, str(port), 0, True, "bad"])
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual((row["host"], row["port"], row["kind"]), (host, port, "openai"))
            self.assertEqual(row["models"], ["local-model"])
            self.assertTrue(row["verified"])
            self.assertFalse(row["authRequired"])
            self.assertEqual(row["name"], "OpenAI compatible")
            self.assertEqual(row["basePath"], "/v1")
            json.dumps(row)
            self.assertEqual([(method, path) for method, path, _ in requests], [("GET", "/api/tags"), ("GET", "/v1/models")])

    def test_ollama_tags_and_empty_model_lists(self):
        payload = {"models": [{"name": "llama3:latest", "model": "llama3:latest", "digest": "test"}]}
        with fixture({"/api/tags": json_response(payload)}) as (host, port, requests):
            row = model_api.probe_service(host, port)
            self.assertEqual(row["kind"], "ollama")
            self.assertEqual(row["models"], ["llama3:latest"])
            self.assertEqual(len(requests), 1)
        for path, payload in (("/api/tags", {"models": []}), ("/v1/models", {"object": "list", "data": []})):
            with fixture({path: json_response(payload)}) as (host, port, _):
                self.assertEqual(model_api.probe_service(host, port)["models"], [])

    def test_unauthorized_candidate_and_explicit_key_verification(self):
        secret = "private-model-key"
        def routes(path, headers):
            if path != "/v1/models":
                return None
            if headers.get("Authorization") == "Bearer " + secret:
                return json_response(OPENAI_MODELS)
            return json_response({"error": {"message": "Invalid key", "code": "invalid_api_key"}}, 401)
        with fixture(routes) as (host, port, requests):
            row = model_api.probe_service(host, port)
            self.assertFalse(row["verified"])
            self.assertEqual(row["kind"], "candidate")
            self.assertTrue(row["authRequired"])
            self.assertEqual(row["models"], [])
            verified = model_api.probe_service(host, port, secret)
            self.assertTrue(verified["verified"])
            self.assertTrue(verified["authRequired"])
            self.assertNotIn(secret, json.dumps(verified))
            keyed = [(path, auth) for _, path, auth in requests if auth]
            self.assertEqual(keyed, [("/v1/models", "Bearer " + secret)])
            self.assertFalse(model_api.probe_service(host, port, "wrong-key")["verified"])

    def test_generic_web_apps_and_malformed_shapes_are_rejected(self):
        for payload in ({"data": []}, {"object": "list", "data": ["x"]}, {"object": "list", "data": [{"id": "model", "object": "user"}]}, {"object": "list", "data": [{"id": ""}]}, {"object": "list", "data": [{"id": "unsafe\nname"}]}):
            with self.subTest(payload=payload), fixture({"/v1/models": json_response(payload)}) as (host, port, _):
                self.assertIsNone(model_api.probe_service(host, port))
        with fixture({"/api/tags": json_response({"models": [{"name": "an unrelated item"}]})}) as (host, port, _):
            self.assertIsNone(model_api.probe_service(host, port))
        with fixture({"/v1/models": json_response({"detail": "Not authenticated"}, 401)}) as (host, port, _):
            self.assertNotIn(port, model_api.KNOWN_MODEL_PORTS)
            self.assertIsNone(model_api.probe_service(host, port))

    def test_known_port_auth_is_only_a_candidate(self):
        reply = model_api._Reply(401, {"detail": "Not authenticated"})
        self.assertTrue(model_api._auth_candidate(reply, 8080))
        self.assertFalse(model_api._auth_candidate(model_api._Reply(200, reply.value), 8080))

    def test_invalid_json_html_oversized_and_compressed_responses(self):
        bodies = [
            (200, "application/json", b"{broken", {}),
            (200, "text/html", b"<html>Sign in</html>", {}),
            (200, "application/json", b" " * (model_api.MAX_RESPONSE_BYTES + 1), {}),
            (200, "application/json", b"{\"object\":\"list\",\"data\":[]}", {"Content-Encoding": "gzip"}),
        ]
        for body in bodies:
            with self.subTest(body=body[:2]), fixture({"/v1/models": body}) as (host, port, _):
                self.assertIsNone(model_api.probe_service(host, port))

    def test_redirects_are_not_followed_or_given_credentials(self):
        with fixture({"/v1/models": json_response(OPENAI_MODELS)}) as (_, target_port, target_requests):
            location = f"http://127.0.0.1:{target_port}/v1/models"
            with fixture({"/v1/models": (302, "application/json", b"{}", {"Location": location})}) as (host, port, _):
                self.assertIsNone(model_api.probe_service(host, port, "never-forward-this"))
            self.assertEqual(target_requests, [])

    def test_unknown_length_response_is_still_bounded(self):
        def wire_body(handler):
            handler.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n")
            handler.wfile.write(b" " * (model_api.MAX_RESPONSE_BYTES + 1))
        with fixture({"/v1/models": (200, "application/json", wire_body, {})}) as (host, port, _):
            self.assertIsNone(model_api.probe_service(host, port))

    def test_whole_request_deadline_bounds_slow_headers_and_body(self):
        def slow_headers(handler):
            for line in (b"HTTP/1.1 200 OK\r\n", b"Content-Type: application/json\r\n", b"Content-Length: 26\r\n", b"Connection: close\r\n", b"\r\n"):
                handler.wfile.write(line)
                time.sleep(.07)
            handler.wfile.write(b'{"object":"list","data":[]}')
        def slow_body(handler):
            handler.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 26\r\nConnection: close\r\n\r\n")
            for value in b'{"object":"list","data":[]}':
                handler.wfile.write(bytes((value,)))
                time.sleep(.05)
        for wire_body in (slow_headers, slow_body):
            with self.subTest(kind=wire_body.__name__), fixture({"/v1/models": (200, "application/json", wire_body, {})}) as (host, port, _):
                started = time.monotonic()
                self.assertIsNone(model_api.probe_service(host, port, timeout=.2))
                self.assertLess(time.monotonic() - started, .5)

    def test_loopback_only_and_key_header_injection(self):
        for host in ("example.com", "192.168.1.1", "0.0.0.0", "::", "::1%1", "localhost.example.com", "127.0.0.1:8080"):
            with self.subTest(host=host), self.assertRaises(ValueError):
                model_api.probe_service(host, 8080)
        for port in (True, 0, 65536, -1, "1.5", 8080.0):
            with self.subTest(port=port), self.assertRaises(ValueError):
                model_api.probe_service("127.0.0.1", port)
        with self.assertRaises(ValueError):
            model_api.probe_service("127.0.0.1", 8080, "secret\r\nInjected: value")

    def test_ipv6_listener_is_discovered(self):
        try:
            with fixture({"/v1/models": json_response(OPENAI_MODELS)}, ipv6=True) as (host, port, _):
                rows = model_api.discover_services([port])
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["host"], host)
                self.assertTrue(rows[0]["verified"])
        except OSError as exc:
            self.skipTest(f"IPv6 loopback unavailable: {exc}")

    def test_cancellation_discards_results_and_no_inference_endpoint(self):
        cancel = threading.Event()
        cancel.set()
        with fixture({"/v1/models": json_response(OPENAI_MODELS)}) as (_, port, requests):
            self.assertEqual(model_api.discover_services([port], cancel), [])
            self.assertEqual(requests, [])
        active, release = threading.Event(), threading.Event()
        def slow_route(_path, _headers):
            active.set()
            release.wait(2)
            return json_response(OPENAI_MODELS)
        cancel.clear()
        with fixture(slow_route) as (_, port, requests):
            result = []
            thread = threading.Thread(target=lambda: result.extend(model_api.discover_services([port], cancel, timeout=.25)))
            thread.start()
            self.assertTrue(active.wait(1))
            started = time.monotonic()
            cancel.set()
            thread.join(1)
            release.set()
            self.assertFalse(thread.is_alive())
            self.assertLess(time.monotonic() - started, 1)
            self.assertEqual(result, [])
            self.assertTrue(all(method == "GET" and path in ("/api/tags", "/v1/models") for method, path, _ in requests))

    def test_scan_limits_concurrency_and_port_count(self):
        lock = threading.Lock()
        counters = {"active": 0, "peak": 0, "count": 0}
        def fake_probe(_port, _cancel, _timeout):
            with lock:
                counters["active"] += 1
                counters["count"] += 1
                counters["peak"] = max(counters["peak"], counters["active"])
            time.sleep(.002)
            with lock:
                counters["active"] -= 1
            return []
        with patch.object(model_api, "_probe_port", fake_probe):
            self.assertEqual(model_api.discover_services(range(10000, 11000), workers=99), [])
        self.assertEqual(counters["count"], model_api.MAX_PORTS)
        self.assertLessEqual(counters["peak"], model_api.MAX_WORKERS)


if __name__ == "__main__":
    unittest.main()
