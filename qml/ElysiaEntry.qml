import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Templates as T

T.TextField {
    required property var ui
    id: field
    implicitHeight: 54
    Layout.fillWidth: true
    leftPadding: 16
    rightPadding: 16
    verticalAlignment: TextInput.AlignVCenter
    color: ui.ink
    selectByMouse: true
    selectionColor: ui.tonal
    selectedTextColor: ui.ink
    placeholderTextColor: ui.muted
    Text {
        x: field.leftPadding
        anchors.verticalCenter: parent.verticalCenter
        width: field.width - field.leftPadding - field.rightPadding
        text: field.placeholderText
        font: field.font
        color: field.placeholderTextColor
        elide: Text.ElideRight
        visible: !field.text.length && !field.preeditText.length
    }
    background: Rectangle {
        radius: 15
        color: "#FFFBFF"
        border.width: field.activeFocus ? 2 : 1
        border.color: field.activeFocus ? ui.accent : "#D3CCD9"
        Behavior on border.color { ColorAnimation { duration: ui.duration(180) } }
    }

}
