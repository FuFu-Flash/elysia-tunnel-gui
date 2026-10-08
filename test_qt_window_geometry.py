"""Window resizing must not rerun startup centering or move its top-left."""
from pathlib import Path
import tempfile
from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from qt_ui import create_application


def main():
    with tempfile.TemporaryDirectory() as directory:
        app, engine, manager, window = create_application(Path(directory) / 'appearance.json')
        try:
            manager.setPreference('motion', False)
            QTest.qWait(160)
            original = window.geometry()
            window.resize(original.width() + 180, original.height() + 80)
            QTest.qWait(80)
            assert window.position() == original.topLeft(), (
                'Resize repeated startup centering and moved the window', original, window.geometry())
            assert window.size() == QSize(original.width() + 180, original.height() + 80)
            enlarged = window.geometry()
            button = window.findChild(QQuickItem, 'maximizeButton')
            point = button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint()
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
            QTest.qWait(100)
            assert window.geometry() == window.screen().availableGeometry()
            point = button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint()
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
            QTest.qWait(100)
            assert window.geometry() == enlarged, ('Maximize/restore moved the normal window', enlarged, window.geometry())
            window.resize(original.size())
            QTest.qWait(80)
            assert window.geometry() == original
            print('PASS resize keeps original top-left; maximize uses work area; restore preserves position and size')
        finally:
            manager.close()
            window.hide()
            app.quit()


if __name__ == '__main__':
    main()
