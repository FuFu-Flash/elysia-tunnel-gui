"""GUI-thread model API discovery and explicit, per-tunnel sharing actions.

Discovery only lists local models. Keys used for an explicit probe never become
QObject properties, log entries, saved settings, or generated client examples.
"""
from __future__ import annotations

import json
import queue
import threading
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication

from model_api import discover_services, probe_service
from tunnel_core import listening_ports


MODEL_EN = {
    "兼容 OpenAI 的 API": "OpenAI-compatible API",
    "待验证的模型 API": "Unverified model API",
    "没有找到模型 API。先启动本地模型服务，再让我找找吧♪": "No model API found. Start your local model server and let me look again ♪",
    "扫描没有完成，保留了上次的结果。请稍后重试。": "The scan could not finish. Previous results were kept. Please try again.",
    "请输入 1～65535 的本地端口。": "Enter a local port from 1 to 65535.",
    "API Key 格式不正确，请检查后重试。": "Check the API key format and try again.",
    "这个端口还没有返回可验证的模型列表，请检查服务和 API Key。": "This port has not returned a valid model list. Check the server and API key.",
    "这个服务需要 API Key，验证模型列表后才能分享。": "This service needs an API key. Verify its model list before sharing.",
    "验证没有完成，请检查本地服务后重试。": "Verification could not finish. Check your local server and try again.",
    "先选择一个已验证的模型 API 吧♪": "Choose a verified model API first ♪",
    "请先停止当前隧道，再更改分享配置。": "Stop the selected tunnel before changing its sharing configuration.",
    "请先在服务端管理中填写 FRPS 配置。": "Enter your FRPS configuration in FRPS servers.",
    "请先在设置中准备好固定域名，再来分享模型。": "Prepare your fixed domain in Settings before sharing a model.",
    "当前隧道正在进行 Cloudflare 操作，请等待完成。": "Wait for this tunnel's Cloudflare operation to finish.",
    "临时地址仅用于非流式调用；Cloudflare Quick Tunnel 不支持 SSE。": "Temporary addresses support non-streaming requests here. Cloudflare Quick Tunnel does not support SSE.",
    "FRP 当前使用 HTTP，公网访问不加密。需要 HTTPS 时请选择固定域名。": "FRP uses unencrypted HTTP. Choose a fixed domain for HTTPS.",
    "API 地址复制好啦，记得把模型名称也带上♪": "API address copied. Remember to include the model name ♪",
    "调用示例复制好啦♪ API Key 请在客户端单独填写。": "Client example copied ♪ Set the API key separately in your client.",
    "模型名称复制好啦♪": "Model name copied ♪",
    "本地隧道列表已满，请先删除不用的条目。": "The tunnel list is full. Remove an unused entry first.",
    "还没有可用的远程端口，请调整 FRPS 配置。": "No unused remote port is available. Adjust your FRPS configuration.",
}


def _service(value):
    """Return only bounded, non-secret model API metadata."""
    if not isinstance(value, dict) or value.get("host") not in ("127.0.0.1", "::1"):
        return None
    port = value.get("port")
    if isinstance(port, bool):
        return None
    try:
        port = int(port)
    except (TypeError, ValueError):
        return None
    if not 1 <= port <= 65535:
        return None
    kind = value.get("kind")
    if kind not in ("ollama", "openai", "candidate"):
        return None
    models = value.get("models", [])
    if not isinstance(models, list):
        return None
    models = list(dict.fromkeys(model for model in models[:256]
                                if isinstance(model, str) and 0 < len(model) <= 512
                                and not any(ord(c) < 32 for c in model)))
    names = {"ollama": "Ollama", "openai": "兼容 OpenAI 的 API", "candidate": "待验证的模型 API"}
    host = value["host"]
    return {"id": f"{host}:{port}", "host": host, "port": port,
            "name": names[kind], "kind": kind, "models": models, "basePath": "/v1",
            "verified": value.get("verified") is True and kind != "candidate",
            "authRequired": value.get("authRequired") is True}


def model_binding_matches(metadata, session):
    """A model label applies only to the exact local target and transport saved.

    The manager also uses this predicate to restore the explicit loopback host
    before an existing model profile is started from the ordinary tunnel list.
    """
    service = _service(metadata)
    if service is None or not service["verified"]:
        return False
    if metadata.get("id") != service["id"]:
        return False
    binding = metadata.get("binding")
    if not isinstance(binding, dict):
        return False
    fields = session.fields
    if fields.get("protocol") != "HTTP" or fields.get("port") != str(service["port"]):
        return False
    transport = metadata.get("transport")
    expected_mode = "FRP" if transport == "FRP" else "Cloudflare" if transport in ("quick", "fixed") else None
    if expected_mode is None or fields.get("mode") != expected_mode:
        return False
    fixed = session.cloudflare.data
    if bool(fixed.get("enabled")) != (transport == "fixed"):
        return False
    if binding.get("port") != str(service["port"]) or binding.get("mode") != expected_mode or binding.get("protocol") != "HTTP":
        return False
    if transport == "fixed" and (fixed.get("hostname") != binding.get("hostname") or fixed.get("id") != binding.get("tunnelId")):
        return False
    return True


class ModelShare(QObject):
    changed = Signal()

    def __init__(self, manager):
        super().__init__(manager)
        self.manager = manager
        self.services = []
        self.selected_id = ""
        self.selected_models = {}
        self.scan_busy = False
        self.scan_complete = False
        self.scan_error = ""
        self.notice = ""
        self.closing = False
        self.worker = None
        self.cancel = threading.Event()
        self.events = queue.Queue()
        self.operation_id = 0
        self.last_tunnel = manager.selected
        self.transport = self._preferred_transport()
        self.transport_chosen = False
        self.timer = QTimer(self)
        self.timer.setInterval(80)  # Discovery results only, never animation.
        self.timer.timeout.connect(self._pump)
        self.timer.start()
        manager.changed.connect(self._manager_changed)

    def _preferred_transport(self):
        session = self.manager.current
        if session.fields.get("server", "").strip():
            return "FRP"
        if session.cloudflare.state()["cfReady"]:
            return "fixed"
        return "quick"

    def _metadata(self):
        metadata = self.manager.profiles[self.manager.selected].get("modelService")
        return metadata if model_binding_matches(metadata, self.manager.current) else None

    def _selected_service(self):
        metadata = self._metadata()
        if self.manager.current.active and metadata is not None:
            return _service(metadata)
        return next((row for row in self.services if row["id"] == self.selected_id), None)

    def _model(self, service):
        if not service:
            return ""
        models = service["models"]
        selected = self.selected_models.get(service["id"], "")
        metadata = self._metadata()
        if not selected and metadata and metadata.get("id") == service["id"]:
            selected = metadata.get("selectedModel", "")
        return selected if selected in models else models[0] if models else ""

    def _public_base(self):
        session = self.manager.current
        metadata = self._metadata()
        if not session.active or metadata is None or getattr(session, "api_target", None) != metadata["host"]:
            return ""
        address = session.address
        try:
            parsed = urlsplit(address)
            if (parsed.scheme not in ("http", "https") or not parsed.hostname
                    or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or parsed.path not in ("", "/") or any(ord(c) < 33 for c in address)):
                return ""
            parsed.port  # Validate the port before making this a client URL.
        except (ValueError, TypeError):
            return ""
        return address.rstrip("/") + "/v1"

    def _snippet(self, base, model):
        if not base:
            return ""
        # A non-streaming example works on every offered transport. Real keys
        # are intentionally not remembered or interpolated into this example.
        return ("import json\nimport os\nimport urllib.request\n\n"
                "class NoRedirect(urllib.request.HTTPRedirectHandler):\n"
                "    def redirect_request(self, request, fp, code, message, headers, new_url):\n"
                "        return None\n\n"
                "opener = urllib.request.build_opener(NoRedirect())\n\n"
                f"base_url = {json.dumps(base, ensure_ascii=False)}\n"
                f"model = {json.dumps(model or 'your-model-id', ensure_ascii=False)}\n"
                "headers = {\"Content-Type\": \"application/json\"}\n"
                "api_key = os.environ.get(\"MODEL_API_KEY\", \"\")\n"
                "if api_key:\n    headers[\"Authorization\"] = \"Bearer \" + api_key\n"
                "body = {\"model\": model, \"messages\": [\n"
                "    {\"role\": \"user\", \"content\": \"Hello!\"}\n"
                "], \"stream\": False}\n"
                "request = urllib.request.Request(\n"
                "    base_url + \"/chat/completions\",\n"
                "    data=json.dumps(body).encode(\"utf-8\"), headers=headers, method=\"POST\"\n"
                ")\nwith opener.open(request, timeout=120) as response:\n"
                "    result = json.load(response)\n"
                "print(result[\"choices\"][0][\"message\"][\"content\"])\n")

    @Property("QVariantMap", notify=changed)
    def state(self):
        service = self._selected_service()
        metadata = self._metadata()
        share_active = bool(self.manager.current.active and metadata is not None
                            and getattr(self.manager.current, "api_target", None) == metadata["host"])
        transport = metadata["transport"] if share_active else self.transport
        base = self._public_base()
        model = self._model(service)
        notice = self.notice
        if not notice:
            if transport == "quick":
                notice = "临时地址仅用于非流式调用；Cloudflare Quick Tunnel 不支持 SSE。"
            elif transport == "FRP":
                notice = "FRP 当前使用 HTTP，公网访问不加密。需要 HTTPS 时请选择固定域名。"
        def display(row):
            result = dict(row)
            result["name"] = self.manager.tr_text(row["name"])
            return result
        return {"services": [display(row) for row in self.services], "scanBusy": self.scan_busy,
                "scanError": self.manager.tr_text(self.scan_error), "scanComplete": self.scan_complete,
                "selectedId": service["id"] if service else self.selected_id,
                "selectedService": display(service) if service else {}, "transport": transport,
                "shareBaseUrl": base, "shareModels": service["models"][:] if service else [],
                "selectedModel": model, "snippet": self._snippet(base, model), "shareActive": share_active,
                "targetTunnel": self.manager.profiles[self.manager.selected]["name"],
                "notice": self.manager.tr_text(notice)}

    @Slot()
    def _manager_changed(self):
        if self.closing:
            return
        if self.manager.selected != self.last_tunnel:
            self.last_tunnel = self.manager.selected
            self.notice = ""
            metadata = self._metadata()
            if metadata and any(row["id"] == metadata["id"] for row in self.services):
                self.selected_id = metadata["id"]
        self.changed.emit()

    def _begin(self, operation, action):
        if self.closing or self.manager.closing or self.scan_busy:
            return
        self.operation_id += 1
        operation_id = self.operation_id
        self.cancel = threading.Event()
        cancel = self.cancel
        self.scan_busy = True
        self.scan_error = ""
        self.notice = ""
        def work():
            try:
                result = action(cancel)
                if not cancel.is_set():
                    self.events.put((operation_id, operation, result))
            except Exception:
                if not cancel.is_set():
                    self.events.put((operation_id, "error", operation))
            finally:
                self.events.put((operation_id, "done", None))
        self.worker = threading.Thread(target=work, name="model-share-" + operation, daemon=True)
        self.worker.start()
        self.changed.emit()

    @Slot()
    def scan(self):
        if not self.scan_complete and not self.transport_chosen and not self.scan_busy:
            self.transport = self._preferred_transport()
        self._begin("scan", lambda cancel: discover_services(listening_ports(), cancel=cancel))

    @Slot(str, str)
    def probePort(self, port, api_key):
        if self.closing or self.scan_busy:
            return
        text = port.strip()
        if not 1 <= len(text) <= 5 or not text.isascii() or not text.isdecimal() or not 1 <= int(text) <= 65535:
            self.notice = "请输入 1～65535 的本地端口。"
            self.changed.emit()
            return
        if len(api_key) > 8192 or any(ord(c) < 32 or ord(c) > 126 for c in api_key):
            self.notice = "API Key 格式不正确，请检查后重试。"
            self.changed.emit()
            return
        number = int(text)
        def probe(cancel):
            candidate = None
            for host in ("127.0.0.1", "::1"):
                if cancel.is_set():
                    break
                row = probe_service(host, number, api_key, cancel=cancel)
                if row and row["verified"]:
                    return row
                if row:
                    candidate = row
            return candidate
        self._begin("probe", probe)

    @Slot()
    def _pump(self):
        if self.closing:
            return
        changed = False
        for _ in range(32):
            try:
                operation_id, kind, result = self.events.get_nowait()
            except queue.Empty:
                break
            if operation_id != self.operation_id:
                continue
            changed = True
            if kind == "scan":
                self.services = [row for value in result if (row := _service(value)) is not None]
                self.scan_complete = True
                if not any(row["id"] == self.selected_id for row in self.services):
                    self.selected_id = self.services[0]["id"] if self.services else ""
                if not self.services:
                    self.notice = "没有找到模型 API。先启动本地模型服务，再让我找找吧♪"
            elif kind == "probe":
                row = _service(result)
                if row is None:
                    self.notice = "这个端口还没有返回可验证的模型列表，请检查服务和 API Key。"
                else:
                    self.services = [item for item in self.services if item["id"] != row["id"]] + [row]
                    self.scan_complete = True
                    if not self.manager.current.active:
                        self.selected_id = row["id"]
                    if not row["verified"]:
                        self.notice = "这个服务需要 API Key，验证模型列表后才能分享。"
            elif kind == "error":
                self.scan_error = ("扫描没有完成，保留了上次的结果。请稍后重试。" if result == "scan"
                                   else "验证没有完成，请检查本地服务后重试。")
                self.scan_complete = True
            elif kind == "done":
                self.scan_busy = False
        if changed:
            self.changed.emit()

    @Slot(str)
    def selectService(self, key):
        if self.closing:
            return
        if self.manager.current.active:
            self.notice = "请先停止当前隧道，再更改分享配置。"
        elif any(row["id"] == key for row in self.services):
            self.selected_id = key
            self.notice = ""
        self.changed.emit()

    @Slot(str)
    def selectModel(self, model):
        service = self._selected_service()
        if not self.closing and service and model in service["models"]:
            self.selected_models[service["id"]] = model
            self.changed.emit()

    @Slot(str)
    def setTransport(self, transport):
        if self.closing or transport not in ("FRP", "fixed", "quick"):
            return
        if self.manager.current.active:
            self.notice = "请先停止当前隧道，再更改分享配置。"
        else:
            self.transport = transport
            self.transport_chosen = True
            self.notice = ""
        self.changed.emit()

    @Slot()
    def createTunnel(self):
        if self.closing or self.manager.closing:
            return
        manager = self.manager
        if len(manager.sessions) >= 256:
            self.notice = "本地隧道列表已满，请先删除不用的条目。"
            self.changed.emit()
            return
        fields = manager.current.fields.copy()
        server_id = manager.profiles[manager.selected].get("serverId", "")
        if fields["server"].strip():
            used = {session.fields.get("remote_port") for session in manager.sessions.values()
                    if all(session.fields.get(key, "").strip().lower() == fields[key].strip().lower()
                           for key in ("server", "server_port"))}
            try:
                remote_port = int(fields["remote_port"])
                if not 1 <= remote_port <= 65535:
                    remote_port = 18080
            except ValueError:
                remote_port = 18080
            for _ in range(65535):
                if str(remote_port) not in used:
                    break
                remote_port = remote_port % 65535 + 1
            else:
                self.notice = "还没有可用的远程端口，请调整 FRPS 配置。"
                self.changed.emit()
                return
            fields["remote_port"] = str(remote_port)
        manager.addTunnel()
        manager.renameTunnel("Model API")
        if fields["server"].strip():
            if server_id:
                manager.selectServer(server_id)
            for name in ("server", "server_port", "token", "public_host", "remote_port"):
                manager.setField(name, fields[name])
            self.transport = "FRP"
            self.transport_chosen = True
        elif self.transport == "fixed":
            self.transport = "quick"  # A new session needs its own fixed-domain binding.
            self.transport_chosen = True
        self.notice = ""
        self.changed.emit()

    @Slot()
    def startShare(self):
        if self.closing or self.manager.closing:
            return
        manager = self.manager
        session = manager.current
        service = self._selected_service()
        if session.active:
            self.notice = "请先停止当前隧道，再更改分享配置。"
        elif session.cloudflare.busy:
            self.notice = "当前隧道正在进行 Cloudflare 操作，请等待完成。"
        elif not service or not service["verified"]:
            self.notice = "先选择一个已验证的模型 API 吧♪"
        elif self.transport == "FRP" and not session.fields["server"].strip():
            self.notice = "请先在服务端管理中填写 FRPS 配置。"
        elif self.transport == "fixed" and not session.cloudflare.state()["cfReady"]:
            self.notice = "请先在设置中准备好固定域名，再来分享模型。"
        else:
            self.notice = ""
            manager.setField("protocol", "HTTP")
            manager.setField("port", str(service["port"]))
            manager.setField("mode", "FRP" if self.transport == "FRP" else "Cloudflare")
            manager.setCloudflare("enabled", self.transport == "fixed")
            session.api_target = service["host"]
            fixed = session.cloudflare.data
            metadata = {**service, "transport": self.transport,
                        "selectedModel": self._model(service),
                        "binding": {"port": str(service["port"]), "protocol": "HTTP",
                                    "mode": session.fields["mode"],
                                    "hostname": fixed["hostname"] if self.transport == "fixed" else "",
                                    "tunnelId": fixed["id"] if self.transport == "fixed" else ""}}
            manager.profiles[manager.selected]["modelService"] = metadata
            manager.save_timer.start()
            manager.start()
        self.changed.emit()

    @Slot()
    def stopShare(self):
        if not self.closing and self.state["shareActive"]:
            self.manager.stop()

    @Slot()
    def copyBaseUrl(self):
        base = self._public_base()
        if base and not self.closing:
            QGuiApplication.clipboard().setText(base)
            self.notice = "API 地址复制好啦，记得把模型名称也带上♪"
            self.changed.emit()

    @Slot()
    def copySnippet(self):
        state = self.state
        if state["snippet"] and not self.closing:
            QGuiApplication.clipboard().setText(state["snippet"])
            self.notice = "调用示例复制好啦♪ API Key 请在客户端单独填写。"
            self.changed.emit()

    @Slot()
    def copyModel(self):
        model = self.state["selectedModel"]
        if model and not self.closing:
            QGuiApplication.clipboard().setText(model)
            self.notice = "模型名称复制好啦♪"
            self.changed.emit()

    @Slot()
    def close(self):
        if self.closing:
            return
        self.closing = True
        self.operation_id += 1
        self.cancel.set()
        self.timer.stop()
