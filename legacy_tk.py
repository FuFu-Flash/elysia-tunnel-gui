from tunnel_core import *
import tkinter as tk
from tkinter import ttk, messagebox

class TunnelApp(TunnelCore):
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
