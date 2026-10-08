"""Loopback HTTP relay for sharing model APIs through a tunnel.

The upstream address is fixed to a numeric loopback IP. The relay replaces Host
with that address, preserves the caller's Authorization, and never stores or
adds API keys. HTTP bodies and SSE are forwarded; WebSocket upgrades and CONNECT
are intentionally unsupported. All listening/accepted/upstream sockets are
closed on cancellation or exit.
"""
from __future__ import annotations

import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import math
import socket
import socketserver
import threading
import time

MAX_HEADER_BYTES = 64 * 1024
HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade", "proxy-connection",
}


class _RequestError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message


class _HeaderReader:
    def __init__(self, source):
        self.source = source
        self.remaining = MAX_HEADER_BYTES

    def readline(self, limit=-1):
        limit = min(limit if limit >= 0 else self.remaining + 1, self.remaining + 1)
        line = self.source.readline(limit)
        self.remaining -= len(line)
        if self.remaining < 0:
            raise http.client.LineTooLong("request headers")
        return line


def _hop_headers(headers) -> set[str]:
    excluded = set(HOP_HEADERS)
    for name, value in headers:
        if name.lower() == "connection":
            excluded.update(part.strip().lower() for part in value.split(","))
    return excluded


class _Upstream(http.client.HTTPConnection):
    def __init__(self, proxy):
        super().__init__(proxy.host, proxy.target_port, timeout=proxy.timeout)
        self.proxy = proxy
        self.tracked_socket = None

    def connect(self):
        # Numeric addresses are connected directly without getaddrinfo/DNS.
        family = socket.AF_INET6 if ":" in self.host else socket.AF_INET
        self.sock = socket.socket(family, socket.SOCK_STREAM)
        self.tracked_socket = self.sock
        self.proxy._track(self.sock)
        self.sock.settimeout(min(self.timeout, 5.0))
        self.sock.connect((self.host, self.port))
        self.sock.settimeout(self.timeout)

    def close(self):
        # HTTPConnection releases its socket after Connection: close headers,
        # while HTTPResponse still reads it. The request handler untracks only
        # after the response has finished, so cancellation can interrupt SSE.
        super().close()


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        # HTTPServer normally performs a reverse hostname lookup here.
        socketserver.TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]

    def process_request(self, request, client_address):
        if not self.proxy._slots.acquire(blocking=False):
            try:
                request.settimeout(.5)
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            self.proxy._track(request)
            super().process_request(request, client_address)
        except BaseException:
            self.proxy._slots.release()
            self.shutdown_request(request)
            if not self.proxy._stop.is_set():
                raise

    def process_request_thread(self, request, client_address):
        current = threading.current_thread()
        with self.proxy._lock:
            self.proxy._threads.add(current)
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.proxy._untrack(request)
            self.proxy._slots.release()
            with self.proxy._lock:
                self.proxy._threads.discard(current)

    def handle_error(self, _request, _client_address):
        # Never log request headers, API keys, paths, or shutdown tracebacks.
        pass


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ElysiaModelRelay"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(min(self.server.proxy.timeout, 30.0))

    def log_message(self, *_args):
        pass

    def parse_request(self):
        original = self.rfile
        self.rfile = _HeaderReader(original)
        try:
            return super().parse_request()
        finally:
            self.rfile = original

    def send_error(self, code, message=None, explain=None):
        self.close_connection = True
        payload = json.dumps({"error": {"message": message or "HTTP relay error.", "type": "proxy_error", "code": str(code)}}).encode()
        try:
            self.send_response_only(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)
                self.wfile.flush()
        except OSError:
            pass

    def __getattr__(self, name):
        if name.startswith("do_"):
            return self._forward
        raise AttributeError(name)

    def _exact(self, length: int) -> bytes:
        value = self.rfile.read(length)
        if len(value) != length:
            raise _RequestError(400, "Incomplete request body.")
        return value

    def _body(self) -> bytes:
        transfer = self.headers.get_all("Transfer-Encoding", [])
        lengths = self.headers.get_all("Content-Length", [])
        if transfer and lengths:
            raise _RequestError(400, "Ambiguous request body framing.")
        if transfer:
            if ",".join(transfer).strip().lower() != "chunked":
                raise _RequestError(501, "Unsupported request transfer encoding.")
            chunks = []
            total = 0
            while True:
                line = self.rfile.readline(1025)
                if not line.endswith(b"\r\n") or len(line) > 1024:
                    raise _RequestError(400, "Invalid chunk framing.")
                number = line[:-2].split(b";", 1)[0].strip()
                if not number or any(value not in b"0123456789abcdefABCDEF" for value in number):
                    raise _RequestError(400, "Invalid chunk size.")
                size = int(number, 16)
                if total + size > self.server.proxy.max_body:
                    raise _RequestError(413, "Request body is too large.")
                if not size:
                    trailer_bytes = 0
                    while True:
                        trailer = self.rfile.readline(MAX_HEADER_BYTES + 1)
                        trailer_bytes += len(trailer)
                        if trailer_bytes > MAX_HEADER_BYTES or not trailer.endswith(b"\r\n"):
                            raise _RequestError(400, "Invalid chunk trailers.")
                        if trailer == b"\r\n":
                            return b"".join(chunks)
                chunks.append(self._exact(size))
                if self._exact(2) != b"\r\n":
                    raise _RequestError(400, "Invalid chunk framing.")
                total += size
        if lengths:
            normalized = [value.strip() for value in lengths]
            if any(not value.isascii() or not value.isdigit() for value in normalized) or len(set(normalized)) != 1:
                raise _RequestError(400, "Invalid request content length.")
            size = int(normalized[0])
            if size > self.server.proxy.max_body:
                raise _RequestError(413, "Request body is too large.")
            return self._exact(size)
        return b""

    def _forward(self):
        proxy = self.server.proxy
        if self.command == "CONNECT" or self.headers.get("Upgrade"):
            self.send_error(501, "This relay supports HTTP model APIs only.")
            return
        if not self.path.startswith("/") and not (self.command == "OPTIONS" and self.path == "*"):
            self.send_error(400, "Only origin-form HTTP requests are accepted.")
            return
        connection = None
        response = None
        response_started = False
        upstream_socket = None
        try:
            body = self._body()
            if proxy._stop.is_set():
                return
            connection = _Upstream(proxy)
            connection.connect()
            upstream_socket = connection.sock
            connection.putrequest(self.command, self.path, skip_host=True, skip_accept_encoding=True)
            host_header = f"[{proxy.host}]:{proxy.target_port}" if ":" in proxy.host else f"{proxy.host}:{proxy.target_port}"
            connection.putheader("Host", host_header)
            excluded = _hop_headers(self.headers.items()) | {"host", "content-length", "expect"}
            for name, value in self.headers.items():
                if name.lower() not in excluded:
                    connection.putheader(name, value)
            connection.putheader("Content-Length", str(len(body)))
            connection.putheader("Connection", "close")
            connection.endheaders(body)
            response = connection.getresponse()
            if response.status == 101:
                raise _RequestError(501, "This relay supports HTTP model APIs only.")
            no_body = self.command == "HEAD" or response.status in (204, 304) or 100 <= response.status < 200
            is_sse = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower() == "text/event-stream"
            chunked = not no_body and (is_sse or response.length is None) and self.request_version >= "HTTP/1.1"
            headers = response.getheaders()
            excluded = _hop_headers(headers) | {"content-length"}
            self.send_response_only(response.status)
            for name, value in headers:
                if name.lower() not in excluded:
                    self.send_header(name, value)
            if no_body:
                original_length = response.getheader("Content-Length")
                if self.command == "HEAD" and original_length and original_length.isdigit():
                    self.send_header("Content-Length", original_length)
            elif chunked:
                self.send_header("Transfer-Encoding", "chunked")
            elif response.length is not None:
                self.send_header("Content-Length", str(response.length))
            else:
                self.close_connection = True
                self.send_header("Connection", "close")
            self.end_headers()
            response_started = True
            if no_body:
                self.wfile.flush()
                return
            while not response.isclosed() and not proxy._stop.is_set():
                chunk = response.read1(16384)
                if not chunk:
                    break
                if chunked:
                    self.wfile.write(f"{len(chunk):X}\r\n".encode() + chunk + b"\r\n")
                else:
                    self.wfile.write(chunk)
                self.wfile.flush()
            if proxy._stop.is_set() or response.length not in (None, 0):
                self.close_connection = True
                return
            if chunked:
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
        except _RequestError as exc:
            if not response_started and not proxy._stop.is_set():
                self.send_error(exc.status, exc.message)
            self.close_connection = True
        except (TimeoutError, socket.timeout):
            if not response_started and not proxy._stop.is_set():
                self.send_error(504, "The local model service timed out.")
            self.close_connection = True
        except (OSError, http.client.HTTPException, ValueError):
            if not response_started and not proxy._stop.is_set():
                self.send_error(502, "The local model service is unavailable.")
            self.close_connection = True
        finally:
            if response is not None:
                response.close()
            if upstream_socket is not None:
                proxy._untrack(upstream_socket)
            if connection is not None:
                if connection.tracked_socket is not None:
                    proxy._untrack(connection.tracked_socket)
                connection.close()


class ModelProxy:
    """A fixed-target relay bound to 127.0.0.1 on an ephemeral TCP port.

    Use ``with ModelProxy(host, port, cancel) as relay:`` and point the tunnel at
    ``127.0.0.1:relay.port``. ``start()`` and ``close()`` are idempotent. A closed
    instance cannot be restarted. Upstream first-byte/read timeout defaults to
    300 seconds to accommodate model prefill; shutdown interrupts pending IO.
    """
    def __init__(self, host, port, cancel=None, *, timeout=300.0, max_body=32 * 1024 * 1024):
        try:
            address = ipaddress.ip_address(host)
        except (ValueError, TypeError):
            raise ValueError("The model service must use a numeric loopback address.") from None
        if not address.is_loopback or "%" in str(host):
            raise ValueError("The model service must use a numeric loopback address.")
        if isinstance(port, bool) or not isinstance(port, (int, str)):
            raise ValueError("Invalid model service port.")
        if isinstance(port, str) and (not port.isascii() or not port.isdigit()):
            raise ValueError("Invalid model service port.")
        port = int(port)
        if not 1 <= port <= 65535:
            raise ValueError("Invalid model service port.")
        try:
            timeout = float(timeout)
        except (TypeError, ValueError):
            raise ValueError("Invalid model service timeout.") from None
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Invalid model service timeout.")
        if isinstance(max_body, bool) or not isinstance(max_body, int) or not 1 <= max_body <= 32 * 1024 * 1024:
            raise ValueError("Invalid model request size limit.")
        self.host, self.target_port = str(address), port
        self.timeout, self.max_body, self.cancel = timeout, max_body, cancel
        self.port = 0
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._closed = threading.Event()
        self._sockets = set()
        self._threads = set()
        self._slots = threading.BoundedSemaphore(32)
        self._server = None
        self._server_thread = None
        self._watcher = None
        self._closing_owner = None

    def _track(self, sock):
        with self._lock:
            if self._stop.is_set():
                sock.close()
                raise OSError("Relay closed.")
            self._sockets.add(sock)

    def _untrack(self, sock):
        with self._lock:
            self._sockets.discard(sock)

    def start(self):
        with self._lock:
            if self._stop.is_set() or (self.cancel is not None and self.cancel.is_set()):
                raise RuntimeError("Relay closed or cancelled.")
            if self._server is not None:
                return self
            server = _Server(("127.0.0.1", 0), _Handler)
            server.proxy = self
            self._server = server
            self.port = server.server_port
            self._server_thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .05}, name="model-relay-listener", daemon=True)
            self._server_thread.start()
            if self.cancel is not None:
                self._watcher = threading.Thread(target=self._watch_cancel, name="model-relay-cancel", daemon=True)
                self._watcher.start()
        return self

    def _watch_cancel(self):
        while not self._stop.wait(.05):
            if self.cancel.is_set():
                self.close()
                return

    def close(self):
        current = threading.current_thread()
        with self._lock:
            if self._stop.is_set():
                owner = self._closing_owner
                first = False
            else:
                self._stop.set()
                self._closing_owner = current
                owner, first = current, True
                sockets = list(self._sockets)
                server = self._server
        if not first:
            if owner is not current:
                self._closed.wait(3)
            return
        try:
            for sock in sockets:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                # Socket.makefile() retains the descriptor after socket.close.
                # On Windows a timed reader may remain inside select until its
                # long model timeout. Detach then close the OS handle so those
                # readers wake immediately; the object cannot double-close a
                # subsequently reused descriptor.
                try:
                    descriptor = sock.detach()
                    if descriptor >= 0:
                        socket.close(descriptor)
                except OSError:
                    sock.close()
            if server is not None:
                server.shutdown()
                server.server_close()
            if self._server_thread is not None and self._server_thread is not current:
                self._server_thread.join(1)
            deadline = time.monotonic() + 2
            with self._lock:
                handlers = list(self._threads)
            for thread in handlers:
                if thread is not current:
                    thread.join(max(0, deadline - time.monotonic()))
            if self._watcher is not None and self._watcher is not current:
                self._watcher.join(.1)
        finally:
            self._closed.set()

    def __enter__(self):
        return self.start()

    def __exit__(self, *_args):
        self.close()
