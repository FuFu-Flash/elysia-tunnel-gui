"""Local bilingual UI regression. No account or tunnel operations are invoked."""
import json
import re
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtTest import QTest
from qt_ui import create_application, read_preferences
from i18n import RawLog, translate


def main():
    with tempfile.TemporaryDirectory() as temporary:
        prefs = Path(temporary) / "prefs.json"
        # Older preferences migrate without losing appearance choices.
        prefs.write_text(json.dumps({"theme": "薄荷绿", "motion": False}), encoding="utf-8")
        assert read_preferences(prefs)["language"] == "zh_CN"
        app, engine, controller, window = create_application(prefs)
        warnings = []
        engine.warnings.connect(lambda values: warnings.extend(str(v) for v in values))
        try:
            window.resize(1240, 780)
            window.setProperty("settingsOpen", True)
            QTest.qWait(250)
            combo = window.findChild(QObject, "languageCombo")
            assert combo is not None and combo.property("currentIndex") == 0
            point = combo.mapToScene(combo.boundingRect().center())
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point.toPoint())
            QTest.qWait(100)
            popup = window.findChild(QObject, "languagePopup")
            assert popup.property("visible"), "Language list did not open"
            QTest.keyClick(window, Qt.Key_Down)
            QTest.keyClick(window, Qt.Key_Return)
            QTest.qWait(150)
            assert controller.preferences["language"] == "en"
            assert window.title() == "Elysia Tunnel GUI"
            assert window.findChild(QObject, "backButton").property("text") == "← Back"
            assert "certificate" in controller.state["cfStatus"]
            controller.core.log("外网地址帮你复制好啦，记得分享给想见的人哦♪")
            raw = "原始日志 unchanged 例子"
            controller.core.log(RawLog(raw))
            controller.pump()
            assert raw in controller.logText and "Address copied!" in controller.logText
            assert "本地端口" not in translate("本地端口必须是 1～65535 的整数。", "en")
            controller.setField("port", "invalid")
            controller.start()
            QTest.qWait(50)
            assert window.findChild(QObject, "messageDialog").property("visible")
            ok = window.findChild(QObject, "messageOk")
            point = ok.mapToScene(ok.boundingRect().center()).toPoint()
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
            QTest.qWait(50)
            assert not window.findChild(QObject, "messageDialog").property("visible")
            # Changing the language never changes protocol or theme identifiers.
            assert controller.fields["mode"] == "自动"
            assert controller.preferences["theme"] == "薄荷绿"
            controller.save()
            assert read_preferences(prefs)["language"] == "en"
            # Render both layouts and save local inspection images.
            folder = Path(".tools")
            folder.mkdir(exist_ok=True)
            for settings in (False, True):
                window.setProperty("settingsOpen", settings)
                QTest.qWait(150)
                window.grabWindow().save(str(folder / ("language-en-settings.png" if settings else "language-en-home.png")))
            # Switch back through the actual dropdown keyboard interface.
            combo.forceActiveFocus()
            QTest.keyClick(window, Qt.Key_Space)
            QTest.keyClick(window, Qt.Key_Up)
            QTest.keyClick(window, Qt.Key_Return)
            QTest.qWait(100)
            assert controller.preferences["language"] == "zh_CN"
            def visual_items(item):
                yield item
                for child in item.childItems():
                    yield from visual_items(child)
            texts = [item.property("text") for item in visual_items(window.contentItem())]
            assert "关闭动画" in texts and "减少动态" not in texts
            assert raw in controller.logText
            controller.setPreference("language", "invalid")
            assert controller.preferences["language"] == "zh_CN"
            controller.resetPreferences()
            controller.save()
            assert read_preferences(prefs)["language"] == "zh_CN"
            assert not warnings, warnings
            print("PASS dropdown, live translation, preferences, stable IDs, raw logs, dialog and Chinese motion label")
        finally:
            controller.close()
            window.close()
            app.processEvents()


if __name__ == "__main__":
    main()
