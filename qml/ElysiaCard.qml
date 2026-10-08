import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Templates as T

Rectangle {
    required property var ui
    property int inset: ui.compactLayout ? 14 : 20
    color: "#FFFFFF"
    border.width: 1
    border.color: Qt.tint(ui.backgroundColor, Qt.rgba(ui.accent.r, ui.accent.g, ui.accent.b, .08))
    radius: 28
    Layout.fillWidth: true
    implicitHeight: content.implicitHeight + inset * 2
    default property alias contents: content.data
    ColumnLayout {
        id: content
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: parent.inset }
        spacing: ui.compactLayout ? 8 : 12
    }

}
