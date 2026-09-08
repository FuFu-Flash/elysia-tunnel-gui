"""Pixel regression for real settings/back clicks; no network or tunnel."""
import json
from pathlib import Path
import sys
import tempfile

from PySide6.QtCore import QPointF, QTimer, Qt
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from qt_ui import create_application


def main():
    with tempfile.TemporaryDirectory() as temp:
        app, engine, controller, window = create_application(Path(temp) / "appearance.json")
        results, failures = [], []
        references = {}
        cases = [(1., True), (1., False), (2., True), (2., False),
                 (.5, True), (.5, False), (1., True), (1., False)]
        output = Path(".tools/navigation-pixels")
        output.mkdir(parents=True, exist_ok=True)

        def snapshot(name):
            image = window.grabWindow()
            image.save(str(output / (name + ".png")))
            small = image.scaled(160, 150).convertToFormat(QImage.Format.Format_RGB32)
            pixels = bytes(small.constBits())
            dark = sum(max(pixels[i:i + 3]) < 140 for i in range(0, len(pixels), 4))
            if dark < 25:
                failures.append(f"{name}: blank or missing page content ({dark} dark pixels)")
            return pixels

        def difference(first, second):
            return sum(abs(a - b) for a, b in zip(first, second)) / len(first)

        def click(name):
            item = window.findChild(QQuickItem, name)
            position = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
            QTest.mouseClick(window, Qt.MouseButton.LeftButton,
                             Qt.KeyboardModifier.NoModifier, position)

        def next_case():
            if not cases:
                controller.setPreference("speed", 1.)
                click("settingsButton")
                QTimer.singleShot(120, lambda: QTest.keyClick(window, Qt.Key.Key_Escape))
                QTimer.singleShot(220, lambda: window.setProperty("settingsOpen", True))
                QTimer.singleShot(320, lambda: QTest.keyClick(window, Qt.Key.Key_Escape))
                for delay in (160, 260, 450, 700):
                    QTimer.singleShot(delay, lambda d=delay: snapshot(f"rapid-reverse-{d}"))
                QTimer.singleShot(1150, reduced_begin)
                return
            speed, opening = cases.pop(0)
            controller.setPreference("speed", speed)
            duration = round(680 / speed)
            name = f"{len(results)}-{'enter' if opening else 'back'}-{speed}"
            middle = []
            click("settingsButton" if opening else "backButton")
            if bool(window.property("settingsOpen")) != opening:
                failures.append(name + ": real click failed to navigate")
            for fraction in (.2, .5, .8):
                QTimer.singleShot(round(duration * fraction),
                                  lambda f=fraction: middle.append(snapshot(name + f"-{f}")))

            def complete():
                end = snapshot(name + "-end")
                motion_changes = [round(difference(a, b), 3) for a, b in zip(middle, middle[1:])]
                if len(middle) != 3 or any(change < .5 for change in motion_changes):
                    failures.append(name + f": frozen transition pixels {motion_changes}")
                reference = references.get(opening)
                if reference is not None and difference(reference, end) > 3:
                    failures.append(name + ": destination does not match its reference page")
                references[opening] = end
                results.append({"case": name, "pixel_changes": motion_changes})
                QTimer.singleShot(80, next_case)

            QTimer.singleShot(duration + 180, complete)

        def reduced_begin():
            end = snapshot("rapid-reverse-home")
            if difference(references[False], end) > 3:
                failures.append("Rapid reversal did not restore home pixels")
            # Reduced-motion must also return the actual home pixels.
            controller.setPreference("motion", False)
            click("settingsButton")
            QTimer.singleShot(150, reduced_return)

        def reduced_return():
            snapshot("reduced-settings")
            click("backButton")
            QTimer.singleShot(150, finish)

        def finish():
            end = snapshot("reduced-home")
            if difference(references[False], end) > 3:
                failures.append("Reduced-motion return did not restore home pixels")
            app.quit()

        def begin():
            references[False] = snapshot("initial-home")
            next_case()

        QTimer.singleShot(700, begin)
        try:
            app.exec()
        finally:
            controller.close()
        (output / "result.json").write_text(json.dumps({"results": results, "failures": failures}, indent=2), encoding="utf-8")
        if failures:
            print("FAIL\n" + "\n".join(failures))
            return 1
        print("PASS real settings/back clicks: changing intermediate pixels, no blank frames, "
              "destination restored across 0.5x/1x/2x, rapid reversal and reduced motion")
        return 0


if __name__ == "__main__":
    sys.exit(main())
