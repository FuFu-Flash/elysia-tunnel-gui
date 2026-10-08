import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Templates as T

Label {
    required property var ui
    color: ui.ink
    font.pixelSize: 18
    font.bold: true
    Layout.fillWidth: true

}
