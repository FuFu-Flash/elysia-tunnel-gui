"""Exercise rendered ripple pixels and real pointer/keyboard input, without tunnels."""
from pathlib import Path
import sys

from PySide6.QtCore import QPoint, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest


def main():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda messages: warnings.extend(m.toString() for m in messages))
    uri = QUrl.fromLocalFile(str(Path("qml").resolve())).toString()
    engine.loadData(('''
import QtQuick
import QtQuick.Window
import QtQuick.Templates as T
import "''' + uri + '''" as App
Window {
    width: 340; height: 160; visible: true; color: "white"
    property int clicks: 0
    T.Button {
        id: button; objectName: "button"
        x: 30; y: 40; width: 280; height: 64
        onClicked: clicks++
        background: Rectangle {
            color: "#F4E5ED"; radius: 32
            App.PressRipple { control: button; tint: "#C24C86" }
        }
    }
}
''').encode())
    assert engine.rootObjects(), warnings
    window = engine.rootObjects()[0]
    button = window.findChild(QQuickItem, "button")
    ripple = window.findChild(QQuickItem, "pressRipple")
    QTest.qWait(400)
    baseline = window.grabWindow().scaled(window.width(), window.height())
    QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, QPoint(45, 72))
    QTest.qWait(80)
    early = window.grabWindow().scaled(window.width(), window.height())
    assert ripple.property("running")
    assert early.pixelColor(53, 72) != baseline.pixelColor(53, 72), "no ripple at press position"
    assert early.pixelColor(295, 72) == baseline.pixelColor(295, 72), "ripple started fully expanded"
    QTest.qWait(280)
    middle = window.grabWindow().scaled(window.width(), window.height())
    assert middle.pixelColor(240, 72) != baseline.pixelColor(240, 72), "ripple failed to spread"
    for x, y in [(30, 40), (32, 42), (308, 42), (308, 102), (32, 102)]:
        assert middle.pixelColor(x, y) == baseline.pixelColor(x, y), "ripple escaped rounded mask"
    QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, QPoint(45, 72))
    QTest.qWait(700)
    assert not ripple.property("running")
    assert window.property("clicks") == 1
    # Keyboard presses must start at the centre, even after an off-centre mouse press.
    button.forceActiveFocus()
    QTest.keyPress(window, Qt.Key_Space)
    QTest.qWait(80)
    wave_centres = [item.property("centerX") for item in ripple.childItems()[0].childItems()
                    if item.property("playing")]
    assert wave_centres and abs(wave_centres[-1] - 140) < 1, wave_centres
    QTest.keyRelease(window, Qt.Key_Space)
    assert window.property("clicks") == 2
    # Rapid presses remain bounded and each produces exactly one click.
    for _ in range(6):
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(90, 72))
        QTest.qWait(25)
    assert window.property("clicks") == 8
    ripple.setProperty("motion", False)
    QTest.qWait(50)
    assert not ripple.property("running")
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(90, 72))
    assert not ripple.property("running") and window.property("clicks") == 9
    ripple.setProperty("motion", True)
    for timing in (1., 2., 4.):
        ripple.setProperty("timing", timing)
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(90, 72))
        QTest.qWait(round(300 * timing))
        assert ripple.property("running"), f"ended too early: {timing}"
        QTest.qWait(round(250 * timing))
        assert not ripple.property("running"), f"did not end: {timing}"
    assert not warnings, warnings
    output = Path(".tools/ripple-pixels")
    output.mkdir(parents=True, exist_ok=True)
    early.save(str(output / "early.png"))
    middle.save(str(output / "middle.png"))
    window.close()
    print("PASS ripple origin, expansion, rounded clipping, keyboard centre, rapid clicks, motion toggle and 0.5x/1x/2x speed")


if __name__ == "__main__":
    main()
