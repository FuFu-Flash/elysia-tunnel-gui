"""Explicit, cancellable Cloudflare account operations; never run on startup."""
import json
import os
from pathlib import Path
import queue
import re
import tempfile
import threading
import time
import uuid

from tunnel_core import ANSI, Cancelled, EngineStore, WindowsJob, check_cancel


def hostname(value):
    value = value.strip().rstrip(".").encode("idna").decode("ascii").lower()
    if len(value) > 253 or "." not in value or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
        for part in value.split(".")
    ):
        raise ValueError("请填写 Cloudflare 中的完整域名，例如 hello.example.com，不要带协议或路径。")
    return value


class CloudflareAccount:
    def __init__(self, folder, cache):
        self.folder = Path(folder)
        self.cache = cache
        self.path = self.folder / "cloudflare.json"
        self.credentials = self.folder / "tunnel-credentials.json"
        self.cert = Path.home() / ".cloudflared" / "cert.pem"
        self.data = {"enabled": False, "hostname": "", "name": "elysia-" + uuid.uuid4().hex[:10],
                     "id": "", "routed_hostname": ""}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for key in self.data:
                    if type(raw.get(key)) is type(self.data[key]):
                        self.data[key] = raw[key]
        except (OSError, ValueError):
            pass
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.lock = threading.RLock()
        self.job = None
        self.busy = False
        self.worker = None
        self.status = "检测到本地授权凭据" if self.cert.is_file() else "还未登录 Cloudflare"
        self.login_url = ""

    def save(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        fd, path = tempfile.mkstemp(prefix="cloudflare-", suffix=".tmp", dir=self.folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self.data, stream, ensure_ascii=False)
            os.replace(path, self.path)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def state(self):
        return {"cfBusy": self.busy, "cfStatus": self.status, "cfLoginUrl": self.login_url,
                "cfEnabled": self.data["enabled"], "cfHostname": self.data["hostname"],
                "cfTunnelId": self.data["id"],
                "cfReady": bool(self.data["id"] and self.credentials.is_file()
                                and self.data["hostname"] == self.data["routed_hostname"])}

    def begin(self, operation):
        if self.busy:
            return
        self.busy = True
        self.cancel = threading.Event()
        self.status = "请在浏览器中完成授权哦…" if operation == "login" else "正在准备固定域名…"
        self.login_url = ""

        def work():
            try:
                self.folder.mkdir(parents=True, exist_ok=True)
                binary = EngineStore(self.cache, lambda kind, text: self.events.put((kind, text)), self.cancel).ensure("cloudflared")
                if operation == "login":
                    if not self.cert.is_file():
                        self.command(binary, ["tunnel", "login"], 300)
                    if not self.cert.is_file():
                        raise RuntimeError("还没有收到授权证书，请完成浏览器授权后再试一次。")
                    self.events.put(("status", "本地授权凭据已就绪，可以绑定域名啦♪"))
                else:
                    self.prepare(binary)
                    self.events.put(("status", "固定域名准备好啦，回主页开始穿透吧♪"))
            except Cancelled:
                self.events.put(("status", "已取消操作。已创建的隧道会保留，下次可以继续。"))
            except Exception as exc:
                self.events.put(("error", str(exc)))
            finally:
                self.events.put(("finished", None))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def command(self, binary, arguments, timeout=60):
        check_cancel(self.cancel)
        output = queue.Queue(maxsize=300)
        stop_reader = threading.Event()
        job = WindowsJob()
        process = reader = None
        with self.lock:
            if self.cancel.is_set():
                job.close()
                raise Cancelled()
            self.job = job
        try:
            process = job.launch([str(binary), *arguments], self.folder, os.environ.copy(), self.cancel)

            def read():
                while not stop_reader.is_set():
                    raw = process.stdout.readline(16384)
                    if not raw:
                        break
                    line = ANSI.sub("", raw.decode("utf-8", errors="replace")).strip()
                    try:
                        output.put_nowait(line)
                    except queue.Full:
                        pass
            reader = threading.Thread(target=read, daemon=True)
            reader.start()
            deadline = time.monotonic() + timeout
            tail = []
            while process.poll() is None or not output.empty() or reader.is_alive():
                check_cancel(self.cancel)
                if time.monotonic() > deadline:
                    raise TimeoutError("操作等待超时，请检查网络后重试。")
                try:
                    line = output.get(timeout=.1)
                except queue.Empty:
                    continue
                tail = (tail + [line])[-8:]
                url = re.search(r"https://dash\.cloudflare\.com/argotunnel[^\s\"<>]*", line)
                if url:
                    self.events.put(("login_url", url.group()))
                else:
                    self.events.put(("log", line))
            if process.returncode:
                raise RuntimeError("Cloudflare 操作失败：\n" + "\n".join(tail))
        finally:
            stop_reader.set()
            job.close()
            if process:
                process.wait(timeout=5)
                if reader:
                    reader.join(timeout=2)
                process.stdout.close()
            with self.lock:
                if self.job is job:
                    self.job = None

    def prepare(self, binary):
        domain = hostname(self.data["hostname"])
        if not self.cert.is_file():
            raise ValueError("先点「登录 Cloudflare」，完成域名授权吧。")
        prefix = ["tunnel", "--origincert", str(self.cert)]
        # Persist identity before DNS work, so retries do not create another tunnel.
        if not self.credentials.is_file():
            if self.data["id"]:
                raise ValueError("本地隧道凭据缺失，请恢复 tunnel-credentials.json 后重试。")
            self.command(binary, prefix + ["create", "--credentials-file", str(self.credentials), self.data["name"]])
        info = json.loads(self.credentials.read_text(encoding="utf-8"))
        self.data["id"] = str(uuid.UUID(info["TunnelID"]))
        self.data["hostname"] = domain
        self.save()
        self.command(binary, prefix + ["route", "dns", self.data["id"], domain])
        self.data["routed_hostname"] = domain
        self.data["enabled"] = True
        self.save()

    def snapshot(self):
        if not self.data["enabled"]:
            return None
        domain = hostname(self.data["hostname"])
        if domain != self.data["routed_hostname"] or not self.data["id"] or not self.credentials.is_file():
            raise ValueError("请先在设置中点击「创建隧道并绑定域名」，再开始固定域名穿透。")
        return {"hostname": domain, "id": str(uuid.UUID(self.data["id"])),
                "credentials": str(self.credentials)}

    def stop(self):
        self.cancel.set()
        with self.lock:
            if self.job:
                self.job.close()
