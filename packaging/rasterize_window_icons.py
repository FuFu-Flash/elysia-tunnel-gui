"""Rasterize the vendored QWindowKit caption SVGs for the lean runtime.

Run with the full PySide6 build environment. The application itself does not
need QtSvg. SVG sources remain unchanged, while PNG variants preserve their
geometry/alpha and provide readable foreground colors on the light frame.
"""
from pathlib import Path
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer


def main():
    directory = Path(__file__).resolve().parents[1] / 'assets' / 'window-controls'
    for symbol in ('minimize', 'maximize', 'restore', 'close'):
        renderer = QSvgRenderer(QByteArray((directory / (symbol + '.svg')).read_bytes()))
        if not renderer.isValid():
            raise RuntimeError(f'Invalid upstream icon: {symbol}')
        image = QImage(96, 96, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        for name, color in (('ink', '#211D29'), ('white', '#FFFFFF')):
            variant = image.copy()
            painter = QPainter(variant)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(variant.rect(), QColor(color))
            painter.end()
            if not variant.save(str(directory / f'{symbol}-{name}.png')):
                raise RuntimeError(f'Could not save caption icon: {symbol}')


if __name__ == '__main__':
    main()
