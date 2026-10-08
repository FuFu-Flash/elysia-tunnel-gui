"""Fresh reduced-motion pages must render after actual navigation clicks."""
import json
from pathlib import Path
import tempfile

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from qt_ui import create_application


def descendants(item):
    for child in item.childItems():
        yield child
        yield from descendants(child)


def main():
    output = Path('.tools/reduced-navigation-pixels')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        prefs = Path(temporary) / 'appearance.json'
        prefs.write_text(json.dumps({'motion': False}), encoding='utf-8')
        app, engine, manager, window = create_application(prefs)
        warnings = []
        engine.warnings.connect(lambda messages: warnings.extend(m.toString() for m in messages))
        try:
            # Prevent navigation from initiating network discovery. Empty state
            # must still display the real page heading, fields and actions.
            manager.model_share.scan_complete = True
            manager.model_share.changed.emit()
            QTest.qWait(250)

            def item(name):
                found = window.findChild(QQuickItem, name)
                assert found is not None, name
                return found

            def click(target):
                target = item(target) if isinstance(target, str) else target
                position = target.mapToScene(QPointF(target.width() / 2, target.height() / 2)).toPoint()
                QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, position)

            def choose(text):
                target = next(child for child in descendants(item('mainNavigation'))
                              if child.property('text') == text and child.metaObject().indexOfSignal('clicked()') >= 0)
                click(target)

            def snapshot(name):
                image = window.grabWindow()
                assert not image.isNull()
                scale = image.width() / window.width()
                # Confirm the persistent Android settings icon renders exactly
                # at its scene position. A page covering the toolbar fails here.
                icon = next(child for child in descendants(item('settingsButton'))
                            if child.metaObject().className() == 'QQuickIconImage')
                corner = icon.mapToScene(QPointF(0, 0))
                accent = window.property('accent')
                colored = sum(
                    max(abs(image.pixelColor(x, y).red() - accent.red()),
                        abs(image.pixelColor(x, y).green() - accent.green()),
                        abs(image.pixelColor(x, y).blue() - accent.blue())) < 15
                    for x in range(round(corner.x() * scale), round((corner.x() + icon.width()) * scale))
                    for y in range(round(corner.y() * scale), round((corner.y() + icon.height()) * scale))
                )
                assert colored >= 20, name + ': navigation was covered or clipped'
                header = round(88 * scale)
                body = image.copy(0, header, image.width(), image.height() - header)
                small = body.scaled(160, 120).convertToFormat(QImage.Format_RGB32)
                pixels = bytes(small.constBits())
                dark = sum(max(pixels[index:index + 3]) < 145 for index in range(0, len(pixels), 4))
                assert dark > 35, name + ': rendered page is blank'
                assert image.save(str(output / (name + '.png')))
                return pixels

            for motion in (False, True, False):
                manager.setPreference('motion', motion)
                label = 'motion' if motion else 'instant'
                choose('模型分享')
                QTest.qWait(180)
                if not motion:
                    assert item('modelSharePage').opacity() == 1., 'Fresh reduced-motion model page stayed transparent'
                    assert item('homePage').opacity() == 0.
                snapshot(label + '-model-180')
                QTest.qWait(1000)
                assert item('modelSharePage').opacity() == 1.
                snapshot(label + '-model-1180')
                click('settingsButton')
                QTest.qWait(180)
                snapshot(label + '-settings-180')
                QTest.qWait(750)
                assert item('pageStrip').x() == -window.width()
                assert item('settingsPage').mapToScene(QPointF(0, 0)).y() == 88
                snapshot(label + '-settings-complete')
                click('backButton')
                QTest.qWait(180)
                snapshot(label + '-model-return-180')
                QTest.qWait(750)
                assert item('pageStrip').x() == 0 and window.property('modelOpen')
                snapshot(label + '-model-return-complete')
                choose('服务穿透')
                QTest.qWait(180)
                snapshot(label + '-home-return-180')
                QTest.qWait(400)
                assert item('homePage').opacity() == 1. and item('modelSharePage').opacity() == 0.
                snapshot(label + '-home-return-complete')
            assert not warnings, warnings
            print('PASS fresh reduced-motion actual model/home/settings navigation, rendered body and toolbar, '
                  '180/1180ms frames, animated round trips and disabling motion again')
        finally:
            manager.close()
            window.hide()
            app.quit()


if __name__ == '__main__':
    main()
