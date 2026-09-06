# -*- coding: utf-8 -*-
from __future__ import annotations

import atexit
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import platform
import queue
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
import zipfile
import tarfile
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

APP_NAME = "一键内网穿透GUI工具"
BG = "#F7F2FA"
SURFACE = "#FFFBFE"
PRIMARY = "#6750A4"
SECONDARY = "#EADDFF"
TEXT = "#1D1B20"
MUTED = "#625B71"
GREEN = "#146C2E"
RED = "#B3261E"
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
MAX_DOWNLOAD = 200 * 1024 * 1024


class Cancelled(Exception):
    pass


def check_cancel(event):
    if event.is_set():
        raise Cancelled()


def port_number(value, label="端口"):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}必须是 1～65535 的整数。")
    if not 1 <= number <= 65535:
        raise ValueError(f"{label}必须在 1～65535 之间。")
    return number


def error_text(exc):
    if isinstance(exc, PermissionError):
        return "权限不足：请检查下载目录权限，以及安全软件是否阻止了内核运行。"
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 403:
            return "GitHub 拒绝下载或 API 访问频率受限，请稍后重试。"
        return f"下载服务返回 HTTP {exc.code}，请稍后重试。"
    if isinstance(exc, urllib.error.URLError):
        return f"网络连接失败：{exc.reason}"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "网络连接超时，请检查网络、防火墙或代理设置。"
    if isinstance(exc, OSError) and getattr(exc, "winerror", None) == 193:
        return "内核与当前 Windows 架构不兼容。"
    return str(exc) or type(exc).__name__


def friendly_error(detail):
    return "哎呀，遇到一点小状况。别着急，我们一起看看：\n\n" + detail


class WindowsJob:
    """所有内核都先以挂起状态启动，再纳入退出即清理的 Job。"""

    def __init__(self):
        self.lock = threading.RLock()
        self.handle = None
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)

        class BASIC(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_ulonglong)
                for name in (
                    "ReadOperationCount", "WriteOperationCount",
                    "OtherOperationCount", "ReadTransferCount",
                    "WriteTransferCount", "OtherTransferCount",
                )
            ]

        class EXTENDED(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC),
                ("IoInfo", IO),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
        ]
        self.kernel.SetInformationJobObject.restype = wintypes.BOOL
        self.kernel.AssignProcessToJobObject.argtypes = [
            wintypes.HANDLE, wintypes.HANDLE
        ]
        self.kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL

        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = EXTENDED()
        info.BasicLimitInformation.LimitFlags = 0x00002000
        if not self.kernel.SetInformationJobObject(
            self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)
        ):
            code = ctypes.get_last_error()
            self.close()
            raise ctypes.WinError(code)

    def launch(self, args, cwd, env, cancel):
        with self.lock:
            check_cancel(cancel)
            if not self.handle:
                raise Cancelled()

            process = subprocess.Popen(
                args,
                cwd=str(cwd),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW | 0x00000004,
                bufsize=0,
            )
            try:
                if not self.kernel.AssignProcessToJobObject(
                    self.handle, wintypes.HANDLE(int(process._handle))
                ):
                    raise ctypes.WinError(ctypes.get_last_error())

                check_cancel(cancel)
                ntdll = ctypes.WinDLL("ntdll")
                resume = ntdll.NtResumeProcess
                resume.argtypes = [wintypes.HANDLE]
                resume.restype = ctypes.c_long
                result = resume(wintypes.HANDLE(int(process._handle)))
                if result < 0:
                    raise OSError(f"恢复内核进程失败：0x{result & 0xffffffff:08X}")
                return process
            except BaseException:
                process.kill()
                process.wait(timeout=5)
                process.stdout.close()
                raise

    def close(self):
        with self.lock:
            if self.handle:
                self.kernel.CloseHandle(self.handle)
                self.handle = None


def listening_ports():
    """从 Windows TCP 表读取监听端口，不启动命令行。"""
    api = ctypes.WinDLL("iphlpapi", use_last_error=True)
    get_table = api.GetExtendedTcpTable
    get_table.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD),
        wintypes.BOOL, wintypes.ULONG, ctypes.c_int, wintypes.ULONG,
    ]
    get_table.restype = wintypes.DWORD

    class ROW4(ctypes.Structure):
        _fields_ = [
            ("state", wintypes.DWORD),
            ("localAddr", wintypes.DWORD),
            ("localPort", wintypes.DWORD),
            ("remoteAddr", wintypes.DWORD),
            ("remotePort", wintypes.DWORD),
            ("pid", wintypes.DWORD),
        ]

    class ROW6(ctypes.Structure):
        _fields_ = [
            ("localAddr", ctypes.c_ubyte * 16),
            ("localScope", wintypes.DWORD),
            ("localPort", wintypes.DWORD),
            ("remoteAddr", ctypes.c_ubyte * 16),
            ("remoteScope", wintypes.DWORD),
            ("remotePort", wintypes.DWORD),
            ("state", wintypes.DWORD),
            ("pid", wintypes.DWORD),
        ]

    ports = set()
    errors = []
    for family, row_type in ((socket.AF_INET, ROW4), (socket.AF_INET6, ROW6)):
        try:
            size = wintypes.DWORD(0)
            result = get_table(None, ctypes.byref(size), False, family, 3, 0)
            if result not in (0, 122):
                raise OSError(result, "读取 TCP 监听表失败")
            if size.value < 4:
                continue
            for _ in range(4):
                buffer = ctypes.create_string_buffer(size.value)
                result = get_table(
                    buffer, ctypes.byref(size), False, family, 3, 0
                )
                if result != 122:
                    break
            if result:
                raise OSError(result, "读取 TCP 监听表失败")
            count = wintypes.DWORD.from_buffer_copy(buffer.raw[:4]).value
            row_size = ctypes.sizeof(row_type)
            count = min(count, (len(buffer) - 4) // row_size)
            for index in range(count):
                row = row_type.from_buffer_copy(buffer, 4 + index * row_size)
                if row.state == 2:
                    ports.add(socket.ntohs(row.localPort & 0xFFFF))
        except OSError as exc:
            errors.append(exc)
    if len(errors) == 2:
        raise errors[0]
    return sorted(ports)


def local_endpoint(port, cancel):
    for host in ("127.0.0.1", "::1"):
        check_cancel(cancel)
        try:
            with socket.create_connection((host, port), timeout=1):
                return host
        except OSError:
            pass
    raise ValueError(
        f"本地端口 {port} 没有可连接的服务。\n"
        "请先启动网站或应用，并确认它监听 127.0.0.1、::1 或所有网卡。\n"
        "穿透工具连接已有服务，不会占用或替代该服务端口。"
    )


class EngineStore:
    def __init__(self, root, emit, cancel):
        self.root = root
        self.emit = emit
        self.cancel = cancel

    def request(self, url):
        if not url.startswith("https://"):
            raise ValueError("仅允许通过 HTTPS 下载内核。")
        return urllib.request.urlopen(
            urllib.request.Request(
                url,
                headers={
                    "User-Agent": "OneClickTunnelGUI/1.0",
                    "Accept": "application/vnd.github+json"
                    if "api.github.com/" in url else "*/*",
                },
            ),
            timeout=15,
        )

    def read_json(self, url):
        check_cancel(self.cancel)
        with self.request(url) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
        check_cancel(self.cancel)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError("发布信息过大。")
        return json.loads(raw.decode("utf-8"))

    def sha256(self, path):
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while True:
                check_cancel(self.cancel)
                block = stream.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
        return digest.hexdigest()

    def download(self, asset, destination):
        check_cancel(self.cancel)
        digest = hashlib.sha256()
        received = 0
        previous = 0.0
        expected_size = int(asset.get("size") or 0)
        if expected_size > MAX_DOWNLOAD:
            raise ValueError("内核文件超出下载大小限制。")

        with self.request(asset["browser_download_url"]) as response:
            with destination.open("wb") as stream:
                while True:
                    check_cancel(self.cancel)
                    block = response.read(64 * 1024)
                    if not block:
                        break
                    received += len(block)
                    if received > MAX_DOWNLOAD:
                        raise ValueError("内核文件超出下载大小限制。")
                    digest.update(block)
                    stream.write(block)
                    now = time.monotonic()
                    if now - previous > 0.3:
                        previous = now
                        label = f"下载内核 {received / 1048576:.1f} MB"
                        if expected_size:
                            label += f" / {expected_size / 1048576:.1f} MB"
                        self.emit("status", label)

        if expected_size and received != expected_size:
            raise ValueError("下载不完整，请重试。")
        expected = asset.get("digest", "")
        if not expected or not expected.startswith("sha256:"):
            raise ValueError("官方发布未提供 SHA-256 摘要，已停止安装。")
        if digest.hexdigest().lower() != expected.split(":", 1)[1].lower():
            raise ValueError("内核 SHA-256 校验失败，请重试。")

    def ensure(self, engine):
        self.root.mkdir(parents=True, exist_ok=True)
        machine = os.environ.get(
            "PROCESSOR_ARCHITEW6432", platform.machine()
        ).lower()
        if machine in ("arm64", "aarch64"):
            arch = "arm64"
        elif machine in ("amd64", "x86_64"):
            arch = "amd64"
        elif machine in ("x86", "i386", "i686"):
            arch = "386"
        else:
            raise ValueError(f"不支持的处理器架构：{machine}")

        name = f"{engine}-{arch}"
        target = self.root / f"{name}.exe"
        manifest = self.root / f"{name}.json"

        if target.exists() and manifest.exists():
            try:
                info = json.loads(manifest.read_text(encoding="utf-8"))
                if self.sha256(target) == info["sha256"]:
                    self.emit("log", f"使用已校验的 {engine} {info['version']}")
                    return target
            except Cancelled:
                raise
            except (OSError, ValueError, KeyError):
                pass

        self.emit("status", "正在获取官方内核…")
        repo = "cloudflare/cloudflared" if engine == "cloudflared" else "fatedier/frp"
        release = self.read_json(f"https://api.github.com/repos/{repo}/releases/latest")
        assets = release.get("assets", [])

        if engine == "cloudflared":
            candidates = [f"cloudflared-windows-{arch}.exe"]
        else:
            version = release["tag_name"].lstrip("v")
            candidates = [
                f"frp_{version}_windows_{arch}.zip",
                f"frp_{version}_windows_{arch}.tar.gz",
            ]
        asset = next(
            (item for item in assets if item["name"] in candidates), None
        )
        if asset is None:
            raise ValueError(f"官方暂未提供 {engine} 的 Windows {arch} 内核。")

        self.emit("log", f"从 GitHub 官方仓库下载 {asset['name']}")
        with tempfile.TemporaryDirectory(prefix="download-", dir=self.root) as tmp:
            tmp = Path(tmp)
            archive = tmp / asset["name"]
            self.download(asset, archive)
            check_cancel(self.cancel)
            binary = tmp / "verified.exe"

            if engine == "cloudflared":
                shutil.copyfile(archive, binary)
            elif asset["name"].endswith(".zip"):
                with zipfile.ZipFile(archive) as package:
                    entries = [
                        item for item in package.infolist()
                        if Path(item.filename).name.lower() == "frpc.exe"
                        and not item.is_dir()
                    ]
                    if len(entries) != 1 or entries[0].file_size > MAX_DOWNLOAD:
                        raise ValueError("FRP 压缩包内容异常。")
                    with package.open(entries[0]) as source, binary.open("wb") as out:
                        shutil.copyfileobj(source, out)
            else:
                with tarfile.open(archive, "r:gz") as package:
                    entries = [
                        item for item in package.getmembers()
                        if Path(item.name).name.lower() == "frpc.exe"
                        and item.isfile()
                    ]
                    if len(entries) != 1 or entries[0].size > MAX_DOWNLOAD:
                        raise ValueError("FRP 压缩包内容异常。")
                    with package.extractfile(entries[0]) as source:
                        with binary.open("wb") as out:
                            shutil.copyfileobj(source, out)

            with binary.open("rb") as stream:
                if stream.read(2) != b"MZ":
                    raise ValueError("下载内容不是有效的 Windows 可执行文件。")
            fingerprint = self.sha256(binary)
            record = tmp / "manifest.json"
            record.write_text(
                json.dumps({
                    "version": release["tag_name"],
                    "sha256": fingerprint,
                }),
                encoding="utf-8",
            )
            check_cancel(self.cancel)
            os.replace(binary, target)
            os.replace(record, manifest)

        self.emit("log", "内核下载完成，SHA-256 校验通过。")
        return target


class TunnelApp:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.logs = queue.Queue(maxsize=2500)
        self.cancel = threading.Event()
        self.worker = None
        self.job = None
        self.job_lock = threading.Lock()
        self.closing = False
        self.restart_pending = False
        self.active = False
        self.scan_busy = False
        self.run_id = 0
        self.address_value = ""

        base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
        self.cache = Path(base) / "OneClickTunnelGUI" / "engines"

        self.mode = tk.StringVar(value="自动")
        self.protocol = tk.StringVar(value="HTTP")
        self.port = tk.StringVar(value="8080")
        self.status = tk.StringVar(value="准备就绪")
        self.address = tk.StringVar(value="出发后，你的外网地址就会出现在这里哦♪")
        self.server = tk.StringVar()
        self.server_port = tk.StringVar(value="7000")
        self.remote_port = tk.StringVar(value="18080")
        self.token = tk.StringVar()
        self.public_host = tk.StringVar()
        self.editables = []

        self.build_ui()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.report_callback_exception = self.callback_error
        root.after(100, self.pump)
        atexit.register(self.kill_job)

    def build_ui(self):
        from m3_ui import build_material_ui
        build_material_ui(self)

    def emit(self, run_id, kind, value):
        if kind == "log":
            try:
                self.logs.put_nowait((run_id, str(value)))
            except queue.Full:
                pass
        else:
            self.events.put((run_id, kind, value))

    def log(self, text):
        self.emit(self.run_id, "log", text)

    def callback_error(self, exc_type, exc, tb):
        if not self.closing:
            self.log(error_text(exc))
            messagebox.showerror(APP_NAME, friendly_error(error_text(exc)), parent=self.root)

    def scan(self):
        if self.scan_busy or self.active:
            return
        self.scan_busy = True
        self.scan_button.configure(state="disabled")
        self.log("让我找找正在监听的 TCP 端口，稍等一下哦…")
        run_id = self.run_id

        def work():
            try:
                ports = listening_ports()
                self.emit(run_id, "ports", ports)
            except Exception as exc:
                self.emit(run_id, "scan_error", error_text(exc))
            finally:
                self.emit(run_id, "scan_done", None)

        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def clean_host(value, label):
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = value[1:-1]
        if (
            not value or any(ch.isspace() for ch in value)
            or any(ch in value for ch in "/\\?#@\"")
        ):
            raise ValueError(f"{label}请填写域名或 IP，不要包含协议、路径或端口。")
        if ":" in value:
            try:
                socket.inet_pton(socket.AF_INET6, value)
            except OSError:
                raise ValueError(f"{label}格式不正确，请将端口填入单独的端口栏。")
        return value

    def snapshot(self):
        config = {
            "port": port_number(self.port.get(), "本地端口"),
            "mode": self.mode.get(),
            "protocol": self.protocol.get().lower(),
            "server": self.server.get().strip(),
            "token": self.token.get(),
        }
        needs_frp = config["mode"] == "FRP" or config["protocol"] == "tcp"
        if config["mode"] == "Cloudflare" and config["protocol"] == "tcp":
            raise ValueError("Cloudflare 临时隧道仅支持 HTTP/HTTPS，请为 TCP 选择 FRP。")
        has_optional_frp = config["mode"] == "自动" and bool(config["server"])
        if needs_frp or has_optional_frp:
            config["server"] = self.clean_host(config["server"], "FRPS 服务器")
            config["server_port"] = port_number(
                self.server_port.get(), "FRPS 服务端口"
            )
            config["remote_port"] = port_number(
                self.remote_port.get(), "远程映射端口"
            )
            config["public_host"] = self.clean_host(
                self.public_host.get().strip() or config["server"], "公网访问主机"
            )
        if "\x00" in config["token"]:
            raise ValueError("Token 包含非法字符。")
        return config

    def set_active(self, active):
        self.active = active
        for widget, normal in self.editables:
            widget.configure(state="disabled" if active else normal)
        self.start_button.configure(state="disabled" if active else "normal")
        self.stop_button.configure(state="normal" if active else "disabled")
        self.restart_button.configure(state="normal" if active else "disabled")
        self.scan_button.configure(
            state="disabled" if active or self.scan_busy else "normal"
        )

    def start(self):
        if self.active or self.closing:
            return
        try:
            config = self.snapshot()
        except Exception as exc:
            messagebox.showerror(APP_NAME, friendly_error(error_text(exc)), parent=self.root)
            return
        self.run_id += 1
        self.cancel = threading.Event()
        self.restart_pending = False
        self.address_value = ""
        self.address.set("正在准备你的外网地址，稍等一下哦…")
        self.status.set("检测本地服务…")
        self.status_label.configure(foreground=PRIMARY)
        self.set_active(True)
        self.worker = threading.Thread(
            target=self.run, args=(self.run_id, config, self.cancel), daemon=True
        )
        self.worker.start()

    def stop(self):
        if not self.active:
            return
        self.restart_pending = False
        self.cancel.set()
        self.status.set("正在停止…")
        self.address_value = ""
        self.address.set("正在收好这次连接，稍等我一下…")
        self.stop_button.configure(state="disabled")
        self.restart_button.configure(state="disabled")
        self.kill_job()

    def restart(self):
        if not self.active:
            self.start()
            return
        self.stop()
        self.restart_pending = True

    def kill_job(self):
        with self.job_lock:
            if self.job:
                self.job.close()

    def run(self, run_id, config, cancel):
        emit = lambda kind, value: self.emit(run_id, kind, value)
        try:
            host = local_endpoint(config["port"], cancel)
            config["local_host"] = host
            emit("log", f"找到你啦♪ 本地服务可连接：{host}:{config['port']}")

            if config["mode"] == "FRP" or config["protocol"] == "tcp":
                engines = ["frpc"]
            elif config["mode"] == "Cloudflare":
                engines = ["cloudflared"]
            else:
                engines = ["cloudflared"]
                if config["server"]:
                    engines.append("frpc")

            store = EngineStore(self.cache, emit, cancel)
            for index, engine in enumerate(engines):
                check_cancel(cancel)
                emit("engine", engine)
                try:
                    binary = store.ensure(engine)
                    self.supervise(engine, binary, config, cancel, emit)
                    break
                except Cancelled:
                    raise
                except Exception as exc:
                    check_cancel(cancel)
                    if index + 1 >= len(engines):
                        raise
                    emit("log", f"{engine} 连接失败：{error_text(exc)}")
                    emit("log", "换条路也没关系哦，正在切换到已配置的 FRP 服务端…")
                    emit("address", "")
        except Cancelled:
            emit("log", "穿透已经停止啦。下次想出发时，再来找我吧♪")
        except Exception as exc:
            emit("error", error_text(exc))
        finally:
            emit("done", None)

    def supervise(self, engine, binary, config, cancel, emit):
        for attempt in range(4):
            check_cancel(cancel)
            if attempt:
                delay = min(2 ** attempt, 10)
                emit("status", f"连接中断，{delay} 秒后重连（{attempt}/3）…")
                emit("address", "")
                if cancel.wait(delay):
                    raise Cancelled()
            try:
                self.run_process(engine, binary, config, cancel, emit)
                return
            except Cancelled:
                raise
            except Exception as exc:
                check_cancel(cancel)
                emit("log", error_text(exc))
                if attempt == 3:
                    raise

    def run_process(self, engine, binary, config, cancel, emit):
        process = None
        job = None
        reader = None
        output = queue.Queue(maxsize=1000)
        reader_stop = threading.Event()
        ready = False
        address = ""
        started = time.monotonic()

        with tempfile.TemporaryDirectory(prefix="oneclick-tunnel-") as temp:
            temp = Path(temp)
            env = os.environ.copy()
            host = config["local_host"]
            url_host = f"[{host}]" if ":" in host else host

            if engine == "cloudflared":
                cfg_path = temp / "cloudflared.yml"
                cfg_path.write_text("{}\n", encoding="utf-8")
                args = [
                    str(binary), "--config", str(cfg_path),
                    "tunnel", "--no-autoupdate",
                    "--protocol", "http2",
                    "--url", f"{config['protocol']}://{url_host}:{config['port']}",
                ]
            else:
                env["ONECLICK_FRP_TOKEN"] = config["token"]
                cfg_path = temp / "frpc.json"
                content = {
                    "serverAddr": config["server"],
                    "serverPort": config["server_port"],
                    "loginFailExit": True,
                    "auth": {
                        "method": "token",
                        "token": "{{ .Envs.ONECLICK_FRP_TOKEN }}",
                    },
                    "log": {"to": "console", "level": "info", "disablePrintColor": True},
                    "transport": {"tls": {"enable": True}},
                    "proxies": [{
                        "name": "oneclick_" + uuid.uuid4().hex[:16],
                        "type": "tcp",
                        "localIP": host,
                        "localPort": config["port"],
                        "remotePort": config["remote_port"],
                    }],
                }
                # JSON 转义在模板替换前完成，避免 Token 中引号破坏配置。
                content["auth"]["token"] = config["token"]
                serialized = json.dumps(content, ensure_ascii=False)
                encoded_token = json.dumps(config["token"], ensure_ascii=False)[1:-1]
                env["ONECLICK_FRP_TOKEN"] = encoded_token
                content["auth"]["token"] = "{{ .Envs.ONECLICK_FRP_TOKEN }}"
                serialized = json.dumps(content, ensure_ascii=False)
                cfg_path.write_text(serialized, encoding="utf-8")
                args = [str(binary), "-c", str(cfg_path)]
                public = config["public_host"]
                if ":" in public:
                    public = f"[{public}]"
                address = f"{config['protocol']}://{public}:{config['remote_port']}"

            def read_output():
                try:
                    while not reader_stop.is_set():
                        raw = process.stdout.readline(16384)
                        if not raw:
                            break
                        line = ANSI.sub("", raw.decode("utf-8", errors="replace")).strip()
                        if not line:
                            continue
                        secret = config["token"]
                        if secret:
                            line = line.replace(secret, "***")
                            line = line.replace(
                                json.dumps(secret, ensure_ascii=False)[1:-1], "***"
                            )
                        while not reader_stop.is_set():
                            try:
                                output.put(line, timeout=0.2)
                                break
                            except queue.Full:
                                continue
                except (OSError, ValueError):
                    pass

            try:
                check_cancel(cancel)
                job = WindowsJob()
                with self.job_lock:
                    check_cancel(cancel)
                    self.job = job
                emit("status", f"正在连接 {'Cloudflare' if engine == 'cloudflared' else 'FRP'}…")
                process = job.launch(args, temp, env, cancel)
                started = time.monotonic()
                reader = threading.Thread(target=read_output, daemon=True)
                reader.start()
                last_health = started
                local_available = True

                while True:
                    check_cancel(cancel)
                    try:
                        line = output.get(timeout=0.2)
                    except queue.Empty:
                        line = None

                    if line:
                        emit("log", line)
                        lower = line.lower()

                        if engine == "cloudflared":
                            match = URL_PATTERN.search(lower)
                            if match:
                                address = match.group(0)
                            if "registered tunnel connection" in lower:
                                ready = True
                            if "all connections" in lower and (
                                "closed" in lower or "failed" in lower
                            ):
                                raise RuntimeError("Cloudflare 连接已断开。")
                        else:
                            if "start proxy success" in lower:
                                ready = True
                            if "start error" in lower or "login to server failed" in lower:
                                if "port" in lower and (
                                    "used" in lower or "unavailable" in lower
                                    or "not allowed" in lower
                                ):
                                    raise RuntimeError(
                                        "FRP 远程端口被占用或不在服务端允许范围内，"
                                        "请修改远程映射端口。"
                                    )
                                raise RuntimeError(f"FRP 连接失败：{line}")

                        if ready and address:
                            emit("address", address)
                            emit(
                                "connected",
                                "已连接" if local_available else "隧道已连接 · 本地服务不可用"
                            )

                    if process.poll() is not None and output.empty():
                        if reader.is_alive():
                            continue
                        raise RuntimeError(
                            f"{engine} 已退出（退出码 {process.returncode}），请查看运行日志。"
                        )

                    now = time.monotonic()
                    if (not ready or not address) and now - started > 90:
                        raise TimeoutError("90 秒内未建立穿透连接，请检查网络及服务端配置。")

                    if ready and now - last_health >= 10:
                        last_health = now
                        try:
                            with socket.create_connection(
                                (host, config["port"]), timeout=1
                            ):
                                available = True
                        except OSError:
                            available = False
                        if available != local_available:
                            local_available = available
                            emit(
                                "connected",
                                "已连接" if available else "隧道已连接 · 本地服务不可用"
                            )
                            emit(
                                "log",
                                "本地服务已恢复。" if available
                                else "本地服务已停止或无法连接，请检查原应用。"
                            )
            finally:
                reader_stop.set()
                if job:
                    job.close()
                with self.job_lock:
                    if self.job is job:
                        self.job = None
                if process:
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    if reader:
                        reader.join(timeout=2)
                    if process.stdout:
                        process.stdout.close()

    def pump(self):
        if self.closing:
            return
        for _ in range(300):
            try:
                run_id, kind, value = self.events.get_nowait()
            except queue.Empty:
                break

            if kind == "scan_done":
                self.scan_busy = False
                if not self.active:
                    self.scan_button.configure(state="normal")
                continue
            if run_id != self.run_id:
                continue

            if kind == "status":
                self.status.set(value)
                self.status_label.configure(foreground=PRIMARY)
            elif kind == "engine":
                self.status.set(f"准备 {value}…")
            elif kind == "address":
                self.address_value = value
                self.address.set(value or "正在重新连接，陪我等一小会儿吧…")
            elif kind == "connected":
                self.status.set(value)
                self.status_label.configure(
                    foreground=GREEN if value == "已连接" else RED
                )
            elif kind == "ports":
                self.port_box.configure(values=[str(port) for port in value])
                if value:
                    self.log("找到这些监听端口啦：" + "、".join(map(str, value)))
                    if self.port.get() not in {str(port) for port in value}:
                        preferred = next(
                            (p for p in (8080, 3000, 8000, 5000, 80, 5173, 8888, 443)
                             if p in value),
                            value[0]
                        )
                        self.port.set(str(preferred))
                    self.log("从端口下拉框里选一个吧。出发前，我会再帮你检查一次哦。")
                else:
                    self.log("还没找到 TCP 监听端口呢。先启动本地服务，再让我找找吧。")
            elif kind == "scan_error":
                self.log(value)
                messagebox.showerror(APP_NAME, friendly_error(value), parent=self.root)
            elif kind == "error":
                self.status.set("连接失败")
                self.status_label.configure(foreground=RED)
                self.address_value = ""
                self.address.set("这次没连上，我们去日志里看看原因吧。")
                self.log(value)
                if not self.cancel.is_set():
                    messagebox.showerror(APP_NAME, friendly_error(value), parent=self.root)
            elif kind == "done":
                self.set_active(False)
                if self.cancel.is_set():
                    self.status.set("已停止")
                    self.status_label.configure(foreground=MUTED)
                    self.address_value = ""
                    self.address.set("下次出发时，新的外网地址会在这里等你哦♪")
                if self.restart_pending:
                    self.restart_pending = False
                    self.root.after(100, self.start)

        lines = []
        for _ in range(200):
            try:
                run_id, line = self.logs.get_nowait()
            except queue.Empty:
                break
            if run_id == self.run_id:
                lines.append(f"{time.strftime('%H:%M:%S')}  {line}\n")

        if lines:
            at_end = self.log_widget.yview()[1] >= 0.98
            self.log_widget.configure(state="normal")
            self.log_widget.insert("end", "".join(lines))
            count = int(self.log_widget.index("end-1c").split(".")[0])
            if count > 1800:
                self.log_widget.delete("1.0", f"{count - 1500}.0")
            if at_end:
                self.log_widget.see("end")
            self.log_widget.configure(state="disabled")

        self.root.after(100, self.pump)

    def copy_address(self):
        if self.address_value:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.address_value)
            self.log("外网地址帮你复制好啦，记得分享给想见的人哦♪")

    def open_address(self):
        value = self.address_value
        if value.startswith(("https://", "http://")):
            webbrowser.open(value)
        elif value:
            messagebox.showinfo(
                APP_NAME, "这是 TCP 地址哦，要在对应客户端里使用。点一下「复制地址」，我帮你收好♪",
                parent=self.root
            )

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.restart_pending = False
        self.cancel.set()
        self.kill_job()
        self.root.destroy()


def main():
    if os.name != "nt":
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(APP_NAME, "这次旅程需要 Windows 10 / 11 哦，请在支持的系统上来找我吧。")
        root.destroy()
        return

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass

    root = tk.Tk()
    app = None
    try:
        app = TunnelApp(root)
        root.mainloop()
    except Exception as exc:
        try:
            messagebox.showerror(APP_NAME, friendly_error(error_text(exc)), parent=root)
        except tk.TclError:
            ctypes.windll.user32.MessageBoxW(
                None, error_text(exc), APP_NAME, 0x10
            )
    finally:
        if app:
            app.cancel.set()
            app.kill_job()


if __name__ == "__main__":
    main()
