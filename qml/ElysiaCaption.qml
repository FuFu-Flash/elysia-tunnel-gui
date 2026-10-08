import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Templates as T

Label {
    required property var ui
    color: ui.muted
    wrapMode: Text.WordWrap
    font.pixelSize: 12
    Layout.fillWidth: true

}
