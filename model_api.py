"""Read-only discovery of model APIs listening on this computer.

Only numeric loopback addresses are contacted. Probes bypass system proxies,
never follow redirects, and only request model lists; no model is loaded and no
inference is performed. A service is verified only by a model-list JSON shape.
Authentication failures may produce clearly unverified candidates.

``discover_services(listening_ports(), cancel)`` accepts TCP port numbers and
checks both loopback families because the Windows listener table merges them.
``probe_service(row['host'], row['port'], api_key)`` rechecks a selected service.
API keys are used only after an unauthenticated request is denied and are never
included in returned rows or error text. Cancelling returns an empty list.
"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
import http.client
import ipaddress
import json
import math
import socket
import threading
import time
from typing import Iterable

MAX_RESPONSE_BYTES = 512 * 1024
MAX_PORTS = 256
MAX_WORKERS = 6
MAX_MODELS = 512
KNOWN_MODEL_PORTS = (11434, 1234, 8080, 8000, 5000, 5001, 7860, 8081, 8001)
LOOPBACK_HOSTS = ("127.0.0.1", "::1")


@dataclass(frozen=True)
class _Reply:
    status: int
    value: object
    bearer: bool = False


def _port_number(port: int | str) -> int:
    if isinstance(port, bool) or not isinstance(port, (int, str)):
        raise ValueError("Invalid local port.")
    if isinstance(port, str):
        port = port.strip()
        if not port.isascii() or not port.isdigit():
            raise ValueError("Invalid local port.")
        port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError("Invalid local port.")
    return port


def _loopback_host(host: str) -> str:
    if not isinstance(host, str):
        raise ValueError("Only local loopback addresses can be probed.")
    host = host.strip()
    if host.lower() == "localhost":
        return "127.0.0.1"
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    # Zone identifiers and names are unnecessary on loopback and are rejected.
    if "%" in host:
        raise ValueError("Only local loopback addresses can be probed.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise ValueError("Only local loopback addresses can be probed.") from None
    if not address.is_loopback:
        raise ValueError("Only local loopback addresses can be probed.")
    return str(address)


def _timeout(value: float) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError("Invalid request timeout.") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Invalid request timeout.")
    return min(value, 1.0)


def _cancelled(cancel: threading.Event | None) -> bool:
    return cancel is not None and cancel.is_set()


def _request_json(
    host: str,
    port: int,
    path: str,
    cancel: threading.Event | None,
    timeout: float,
    api_key: str = "",
) -> _Reply | None:
    """Connect directly; HTTPConnection has neither proxies nor redirects."""
    if _cancelled(cancel):
        return None
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "identity",
        "Connection": "close",
        "User-Agent": "ElysiaTunnel-LocalModelDiscovery/1.0",
    }
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    connection = http.client.HTTPConnection(host, port, timeout=timeout)
    read_socket = None
    response = None
    def abort_request():
        # A socket timeout alone is renewed by each arriving byte. Enforce the
        # whole request deadline even if headers/body arrive one byte at a time.
        current_socket = connection.sock or read_socket
        if current_socket is not None:
            try:
                current_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
    watchdog = threading.Timer(timeout, abort_request)
    watchdog.daemon = True
    deadline = time.monotonic() + timeout
    watchdog.start()
    try:
        connection.request("GET", path, headers=headers)
        if _cancelled(cancel):
            return None
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        if connection.sock is not None:
            connection.sock.settimeout(remaining)
        read_socket = connection.sock
        response = connection.getresponse()
        # Redirect destinations are deliberately never requested, even locally.
        if response.status not in (200, 401, 403):
            return None
        content_type = response.getheader("Content-Type", "").lower()
        if "application/json" not in content_type and "+json" not in content_type:
            return None
        if response.getheader("Content-Encoding", "identity").lower() != "identity":
            return None
        length = response.getheader("Content-Length")
        if length is not None:
            try:
                if int(length) < 0 or int(length) > MAX_RESPONSE_BYTES:
                    return None
            except ValueError:
                return None
        body = bytearray()
        while not response.isclosed():
            if _cancelled(cancel):
                return None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            # Keep the direct socket reference: a closing HTTP response can
            # release HTTPConnection.sock while its response reader owns it.
            if read_socket is not None:
                read_socket.settimeout(remaining)
            chunk = response.read1(min(16384, MAX_RESPONSE_BYTES + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
            if len(body) > MAX_RESPONSE_BYTES:
                return None
        if response.length not in (None, 0):
            return None
        if not body:
            return None
        value = json.loads(body.decode("utf-8-sig"))
        bearer = response.getheader("WWW-Authenticate", "").lower().startswith("bearer")
        return _Reply(response.status, value, bearer)
    except (OSError, http.client.HTTPException, UnicodeError, ValueError, RecursionError):
        return None
    finally:
        watchdog.cancel()
        if response is not None:
            response.close()
        connection.close()


def _model_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= 1024
        and value.strip() == value
        and not any(ord(character) < 32 for character in value)
    )


def _models(value: object, kind: str) -> list[str] | None:
    if not isinstance(value, dict):
        return None
    if kind == "ollama":
        items = value.get("models")
        if not isinstance(items, list) or len(items) > MAX_MODELS:
            return None
        names = []
        for item in items:
            if not isinstance(item, dict) or not _model_id(item.get("name")):
                return None
            # These fields distinguish tags from an unrelated list of names.
            if not any(key in item for key in ("model", "digest", "modified_at", "details")):
                return None
            names.append(item["name"])
    else:
        if value.get("object") != "list":
            return None
        items = value.get("data")
        if not isinstance(items, list) or len(items) > MAX_MODELS:
            return None
        names = []
        for item in items:
            if not isinstance(item, dict) or not _model_id(item.get("id")):
                return None
            if item.get("object", "model") != "model":
                return None
            names.append(item["id"])
    return list(dict.fromkeys(names))


def _auth_candidate(reply: _Reply, port: int) -> bool:
    if reply.status not in (401, 403) or not isinstance(reply.value, dict):
        return False
    error = reply.value.get("error")
    if isinstance(error, dict):
        markers = (error.get("code"), error.get("type"))
        if any(marker in ("invalid_api_key", "authentication_error", "missing_api_key") for marker in markers):
            return True
    # Known ports plus a structured error/challenge are hints, not verification.
    return port in KNOWN_MODEL_PORTS and (
        isinstance(reply.value.get("detail"), str)
        or isinstance(error, (str, dict))
        or reply.bearer
    )


def _row(host: str, port: int, kind: str, models: list[str], auth: bool, verified: bool) -> dict:
    names = {
        "ollama": "Ollama",
        "openai": "OpenAI compatible",
        "candidate": "Model API candidate",
    }
    return {
        "id": f"{host}:{port}",
        "host": host,
        "port": port,
        "name": names[kind],
        "kind": kind,
        "models": models,
        "basePath": "/v1",
        "authRequired": auth,
        "verified": verified,
    }


def probe_service(
    host: str,
    port: int | str,
    api_key: str = "",
    *,
    cancel: threading.Event | None = None,
    timeout: float = 1.0,
) -> dict | None:
    """Verify a selected local API. Invalid host/port/key inputs raise ValueError.

    API keys remain local variables and are only sent to a denied loopback model
    listing endpoint. No service/provider is inferred from its port alone.
    """
    host = _loopback_host(host)
    port = _port_number(port)
    timeout = _timeout(timeout)
    if not isinstance(api_key, str) or len(api_key) > 8192 or any(ord(c) < 32 or ord(c) > 126 for c in api_key):
        raise ValueError("Invalid API key.")
    denied = []
    candidate = False
    for path, kind in (("/api/tags", "ollama"), ("/v1/models", "openai")):
        if _cancelled(cancel):
            return None
        reply = _request_json(host, port, path, cancel, timeout)
        if reply is None:
            continue
        if reply.status == 200:
            models = _models(reply.value, kind)
            if models is not None:
                return _row(host, port, kind, models, False, True)
        elif reply.status in (401, 403):
            denied.append((path, kind))
            candidate = candidate or _auth_candidate(reply, port)
    # Prefer the standard OpenAI endpoint if both endpoints denied the request.
    if api_key:
        for path, kind in reversed(denied):
            if _cancelled(cancel):
                return None
            reply = _request_json(host, port, path, cancel, timeout, api_key)
            if reply is not None and reply.status == 200:
                models = _models(reply.value, kind)
                if models is not None:
                    return _row(host, port, kind, models, True, True)
    if candidate and not _cancelled(cancel):
        return _row(host, port, "candidate", [], True, False)
    return None


def _probe_port(port: int, cancel: threading.Event | None, timeout: float) -> list[dict]:
    rows = []
    for host in LOOPBACK_HOSTS:
        if _cancelled(cancel):
            break
        row = probe_service(host, port, cancel=cancel, timeout=timeout)
        if row is not None:
            rows.append(row)
    # An API commonly binds both families. Prefer its IPv4 entry without
    # duplicating it, but retain distinct IPv6 APIs using the same port.
    if len(rows) == 2:
        keys = ("kind", "models", "authRequired", "verified")
        if all(rows[0][key] == rows[1][key] for key in keys):
            return rows[:1]
    return rows


def discover_services(
    ports: Iterable[int | str],
    cancel: threading.Event | None = None,
    *,
    workers: int = MAX_WORKERS,
    timeout: float = 1.0,
) -> list[dict]:
    """Scan at most 256 listener ports with up to six concurrent workers.

    Workers use only localhost HTTP requests and carry no API keys. Invalid port
    entries are ignored. Cancellation discards results and waits at most the
    remaining request deadline for active requests to stop.
    """
    timeout = _timeout(timeout)
    if _cancelled(cancel):
        return []
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise ValueError("Invalid scan worker count.")
    workers = min(workers, MAX_WORKERS)
    unique = set()
    for index, value in enumerate(ports):
        if _cancelled(cancel):
            return []
        if index >= MAX_PORTS * 4:
            break
        try:
            unique.add(_port_number(value))
        except ValueError:
            continue
        if len(unique) >= MAX_PORTS:
            break
    preferred = {port: index for index, port in enumerate(KNOWN_MODEL_PORTS)}
    ordered = sorted(unique, key=lambda port: (preferred.get(port, len(preferred)), port))
    rows = []
    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="model-api")
    pending = set()
    try:
        pending = {executor.submit(_probe_port, port, cancel, timeout) for port in ordered}
        while pending and not _cancelled(cancel):
            completed, pending = wait(pending, timeout=0.05, return_when=FIRST_COMPLETED)
            for future in completed:
                rows.extend(future.result())
    finally:
        for future in pending:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
    if _cancelled(cancel):
        return []
    return sorted(rows, key=lambda row: (not row["verified"], row["port"], row["host"]))
