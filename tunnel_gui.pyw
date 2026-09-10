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
        import json
        import os
        from pathlib import Path
        report = Path(tempfile.gettempdir()) / "elysia-tunnel-startup-error.txt"
        report.write_text(traceback.format_exc(), encoding="utf-8")
        language = "zh_CN"
        try:
            prefs = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "OneClickTunnelGUI" / "appearance.json"
            saved = json.loads(prefs.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                language = saved.get("language", "zh_CN")
        except (OSError, ValueError):
            pass
        title = "Elysia Tunnel GUI" if language == "en" else "一键内网穿透GUI工具"
        detail = (f"Something went wrong while starting: {exc}\n\nDetails: {report}" if language == "en"
                  else f"哎呀，启动遇到一点小状况：{exc}\n\n详细记录：{report}")
        ctypes.windll.user32.MessageBoxW(None, detail, title, 0x10)
