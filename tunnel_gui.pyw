# -*- coding: utf-8 -*-
"""Windows GUI entry point; launch with pythonw to avoid a console window."""
if __name__ == "__main__":
    try:
        from qt_ui import main
        main()
    except Exception as exc:
        import ctypes
        import traceback
        import tempfile
        from pathlib import Path
        report = Path(tempfile.gettempdir()) / "elysia-tunnel-startup-error.txt"
        report.write_text(traceback.format_exc(), encoding="utf-8")
        ctypes.windll.user32.MessageBoxW(None, f"哎呀，启动遇到一点小状况：{exc}\n\n详细记录：{report}", "一键内网穿透GUI工具", 0x10)
