import ctypes
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.request

BASE = Path(__file__).resolve().parent
loader = importlib.machinery.SourceFileLoader('tunnel_gui', str(BASE / 'legacy_tk.py'))
spec = importlib.util.spec_from_loader(loader.name, loader)
app = importlib.util.module_from_spec(spec)
loader.exec_module(app)


def smoke():
    root = tk.Tk()
    root.withdraw()
    gui = app.TunnelApp(root)
    root.update()
    print('PASS Tkinter GUI creation; Tcl/Tk', root.tk.call('info', 'patchlevel'), flush=True)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        port = listener.getsockname()[1]
        assert port in app.listening_ports()
        assert app.local_endpoint(port, threading.Event()) == '127.0.0.1'
    try:
        app.local_endpoint(port, threading.Event())
    except ValueError:
        print('PASS local listener discovery, connection, closed-port error', flush=True)
    else:
        raise AssertionError('Closed port was accepted')
    job = app.WindowsJob()
    child = job.launch([sys.executable, '-c', 'import time; print("READY",flush=True); time.sleep(60)'], BASE, os.environ.copy(), threading.Event())
    assert child.stdout.readline().strip() == b'READY'
    job.close()
    child.wait(timeout=5)
    child.stdout.close()
    print('PASS suspended process launch, Job assignment, process cleanup', flush=True)
    gui.close()


def download():
    def emit(kind, message):
        print(kind, message, flush=True)
    store = app.EngineStore(BASE / '.test-engines', emit, threading.Event())
    result = {}
    for engine in ('cloudflared', 'frpc'):
        try:
            binary = store.ensure(engine)
            completed = subprocess.run([str(binary), '--version' if engine == 'cloudflared' else '-v'], capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
            print('VERSION', completed.returncode, completed.stdout.decode('utf-8', errors='replace').strip(), flush=True)
            assert completed.returncode == 0
            result[engine] = str(binary)
        except Exception as exc:
            result[engine] = {'error': repr(exc)}
            print('FAIL', engine, repr(exc), flush=True)
    (BASE / 'test-download-results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')


def e2e():
    marker = b'oneclick-tunnel-environment-test-only'
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(marker)
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    root = tk.Tk()
    gui = app.TunnelApp(root)
    gui.cache = BASE / '.test-engines'
    gui.port.set(str(server.server_port))
    gui.mode.set('Cloudflare')
    failures = []
    app.messagebox.showerror = lambda *a, **kw: failures.append(str(a))
    real_emit = gui.emit
    def emit(run_id, kind, value):
        if kind in ('status', 'connected', 'error', 'log'):
            print(kind, value, flush=True)
        real_emit(run_id, kind, value)
    gui.emit = emit
    def wait_for(predicate, timeout=120):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            root.update()
            if predicate():
                return
            if failures:
                raise AssertionError(failures)
            time.sleep(.03)
        raise TimeoutError('GUI state: ' + gui.status.get())
    try:
        gui.start()
        wait_for(lambda: bool(gui.address_value))
        url = gui.address_value
        print('PASS public URL obtained', url, flush=True)
        result = []
        def request_public():
            for _ in range(6):
                try:
                    with urllib.request.urlopen(url, timeout=12) as response:
                        result.append(response.read())
                        return
                except Exception as exc:
                    print('Public request retry:', type(exc).__name__, str(exc), flush=True)
                    time.sleep(3)
            result.append(None)
        threading.Thread(target=request_public, daemon=True).start()
        wait_for(lambda: bool(result), 100)
        assert result[0] == marker, 'Public response did not match local test service'
        print('PASS public HTTPS -> tunnel -> synthetic localhost HTTP', flush=True)
        gui.stop()
        wait_for(lambda: not gui.active, 15)
        assert not gui.address_value
        print('PASS stop button', flush=True)
        gui.start()
        wait_for(lambda: bool(gui.address_value))
        old_run = gui.run_id
        gui.restart()
        wait_for(lambda: gui.run_id > old_run and bool(gui.address_value))
        print('PASS restart button', flush=True)
        gui.close()
        gui.worker.join(10)
        assert not gui.worker.is_alive()
        print('PASS close active GUI, worker and tunnel cleaned up', flush=True)
    finally:
        if not gui.closing:
            gui.close()
        if gui.worker:
            gui.worker.join(10)
        server.shutdown()
        server.server_close()


def ui():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    from PIL import Image
    import m3_ui
    import tempfile
    from unittest.mock import patch
    preferences_dir = tempfile.TemporaryDirectory(prefix='tunnel-settings-test-')
    preferences_path = Path(preferences_dir.name)/'appearance.json'
    root = tk.Tk()
    with patch.object(m3_ui,'settings_path',return_value=preferences_path):
        gui = app.TunnelApp(root)
    failures = []
    root.report_callback_exception = lambda kind,exc,tb: failures.append(repr(exc))
    def tick(seconds=.65):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            root.update()
            time.sleep(.01)
        assert not failures, failures
    def screenshot(name):
        root.update()
        # Render only this window, regardless of desktop overlays or foreground apps.
        from ctypes import wintypes as wt
        user = ctypes.WinDLL('user32',use_last_error=True)
        gdi = ctypes.WinDLL('gdi32',use_last_error=True)
        user.GetParent.argtypes = [wt.HWND]
        user.GetParent.restype = wt.HWND
        user.GetDC.argtypes = [wt.HWND]
        user.GetDC.restype = wt.HDC
        user.ReleaseDC.argtypes = [wt.HWND,wt.HDC]
        user.PrintWindow.argtypes = [wt.HWND,wt.HDC,wt.UINT]
        gdi.CreateCompatibleDC.argtypes = [wt.HDC]
        gdi.CreateCompatibleDC.restype = wt.HDC
        gdi.CreateCompatibleBitmap.argtypes = [wt.HDC,ctypes.c_int,ctypes.c_int]
        gdi.CreateCompatibleBitmap.restype = wt.HBITMAP
        gdi.SelectObject.argtypes = [wt.HDC,wt.HANDLE]
        gdi.SelectObject.restype = wt.HANDLE
        gdi.DeleteObject.argtypes = [wt.HANDLE]
        gdi.DeleteDC.argtypes = [wt.HDC]
        gdi.GetDIBits.argtypes = [wt.HDC,wt.HBITMAP,wt.UINT,wt.UINT,ctypes.c_void_p,ctypes.c_void_p,wt.UINT]
        class Header(ctypes.Structure):
            _fields_ = [('size',wt.DWORD),('width',wt.LONG),('height',wt.LONG),
                        ('planes',wt.WORD),('bits',wt.WORD),('compression',wt.DWORD),
                        ('image_size',wt.DWORD),('x',wt.LONG),('y',wt.LONG),
                        ('colors',wt.DWORD),('important',wt.DWORD)]
        hwnd = user.GetParent(root.winfo_id())
        width,height = root.winfo_width(),root.winfo_height()
        dc = user.GetDC(hwnd)
        memory = gdi.CreateCompatibleDC(dc)
        bitmap = gdi.CreateCompatibleBitmap(dc,width,height)
        old = gdi.SelectObject(memory,bitmap)
        try:
            assert user.PrintWindow(hwnd,memory,3)
            gdi.SelectObject(memory,old)
            header = Header(ctypes.sizeof(Header),width,-height,1,32,0,0,0,0,0,0)
            pixels = ctypes.create_string_buffer(width*height*4)
            assert gdi.GetDIBits(memory,bitmap,0,height,pixels,ctypes.byref(header),0)==height
            Image.frombuffer('RGB',(width,height),pixels.raw,'raw','BGRX',0,1).save(BASE/name)
        finally:
            gdi.SelectObject(memory,old)
            gdi.DeleteObject(bitmap)
            gdi.DeleteDC(memory)
            user.ReleaseDC(hwnd,dc)
    try:
        root.lift()
        tick()
        assert gui.port_box.entry.winfo_width() > 100
        screenshot('界面预览.png')
        control = gui.mode_control
        control.event_generate('<Button-1>',x=control.winfo_width()-30,y=23)
        assert gui.mode.get() == 'FRP'
        tick(.06)
        if m3_ui.MOTION:
            assert 0 < control.position < 2, control.position
        tick()
        assert abs(control.position-2) < .001
        control.focus_force()
        tick(.05)
        control.event_generate('<KeyPress-Left>')
        assert gui.mode.get() == 'Cloudflare'
        gui.mode.set('自动')
        calls = []
        button = gui.scan_button
        original = button.command
        button.command = lambda:calls.append(1)
        button.event_generate('<Enter>')
        tick()
        assert button.hover > .99
        button.event_generate('<ButtonPress-1>',x=30,y=23)
        tick(.06)
        assert button.ripple is not None
        button.event_generate('<ButtonRelease-1>',x=30,y=23)
        assert calls == [1]
        tick(.5)
        if m3_ui.MOTION:
            assert button.ripple is not None, 'Ripple finished before doubled duration'
        tick(.5)
        assert button.ripple is None
        button.configure(state='disabled')
        button.invoke()
        assert calls == [1]
        button.configure(state='normal')
        button.focus_force()
        tick(.05)
        button.event_generate('<KeyPress-space>')
        assert calls == [1,1]
        button.command = original
        gui.port_box.configure(values=['8080','3000'])
        # Verify menu commands without entering Windows' native modal menu loop.
        from unittest.mock import patch
        with patch.object(tk.Menu,'tk_popup',lambda *args:None):
            gui.port_box.popup()
        assert gui.port_box.menu.index('end') == 1
        gui.port_box.menu.invoke(1)
        gui.port_box.menu.unpost()
        assert gui.port.get() == '3000'
        gui.port.set('8080')
        gui.status.set('已连接')
        assert gui.status.get() == '已连接'
        assert '连接成功' in gui.status_display.get()
        gui.status.set('准备就绪')
        print('PASS rounded control events, hover, ripple, animated segment, disabled state',flush=True)
        print('PASS keyboard selection, keyboard activation, detected-port dropdown',flush=True)
        gui.ui_tab.set('FRP 配置')
        tick()
        assert gui.ui_pages['FRP 配置'].winfo_ismapped()
        screenshot('FRP配置预览.png')
        gui.set_active(True)
        tick()
        assert all(widget.control_state=='disabled' for widget,_ in gui.editables)
        gui.set_active(False)
        gui.ui_tab.set('运行日志')
        root.geometry('700x620')
        tick()
        gui.ui_viewport.yview_moveto(1)
        tick()
        assert gui.footer.winfo_rooty()+gui.footer.winfo_height() <= root.winfo_rooty()+root.winfo_height()
        screenshot('小窗口预览.png')
        print('PASS settings tab, running-state locking, small-window scroll access',flush=True)
        root.geometry('940x940')
        port_widget = gui.port_box
        gui.set_active(True)
        gui.settings_button.invoke()
        tick(.12)
        if m3_ui.MOTION:
            assert 0 < gui.page_host.progress < 1
        gui.page_host.show(False)
        tick(.12)
        gui.page_host.show(True)
        tick(.9)
        assert gui.page_host.progress == 1
        assert gui.port_box is port_widget and gui.active
        assert gui.port_box.control_state == 'disabled'
        screenshot('设置页面预览.png')
        root.geometry('700x620')
        tick()
        gui.appearance.view.yview_moveto(1)
        tick()
        assert gui.appearance.view.yview()[1] >= .999
        screenshot('设置小窗口预览.png')
        root.geometry('940x940')
        gui.appearance.view.yview_moveto(0)
        tick()
        gui.appearance.theme.set('薄荷绿')
        tick()
        assert m3_ui.CURRENT_THEME == '薄荷绿'
        assert gui.root.cget('background') != m3_ui.BG
        slider = gui.appearance.slider
        slider.event_generate('<Button-1>',x=slider.winfo_width()-16,y=20)
        assert gui.appearance.speed.get() == 2.
        slider.focus_force()
        tick(.05)
        slider.event_generate('<KeyPress-Left>')
        assert gui.appearance.speed.get() == 1.9
        gui.appearance.slider.set(.5)
        tick()
        assert m3_ui.MOTION_DURATION_SCALE == 4.
        gui.appearance.slider.set(2.)
        tick()
        assert m3_ui.MOTION_DURATION_SCALE == 1.
        gui.appearance.motion.set('关闭')
        tick()
        assert not m3_ui.MOTION
        gui.page_host.show(False)
        assert gui.page_host.progress == 0
        gui.page_host.show(True)
        assert gui.page_host.progress == 1
        screenshot('薄荷主题设置预览.png')
        loaded = m3_ui.read_preferences(preferences_path)
        assert loaded == {'theme':'薄荷绿','speed':2.,'motion':False},loaded
        gui.set_active(False)
        gui.appearance.reset()
        tick()
        assert m3_ui.read_preferences(preferences_path) == {'theme':'薰衣紫','speed':1.,'motion':True}
        gui.page_host.show(False)
        tick(.9)
        assert gui.port_box.entry.winfo_exists()
        print('PASS page animation/reversal, active-state preservation, live themes, speed, motion, atomic persistence, defaults',flush=True)
        preferences_path.write_text('{broken',encoding='utf-8')
        assert m3_ui.read_preferences(preferences_path)['speed'] == 1.
    finally:
        gui.close()
        preferences_dir.cleanup()


if __name__ == '__main__':
    {'smoke': smoke, 'download': download, 'e2e': e2e, 'ui': ui}[sys.argv[1]]()
