import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Templates as T

ComboBox {
    required property var ui
    id: profileSelect
    implicitHeight: 46
    background: Rectangle {
        radius: 16; color: ui.tonal
        border.width: parent.visualFocus ? 2 : 0; border.color: ui.accent
        PressRipple { control: profileSelect; tint: ui.accent; cornerRadius: 16; motion: ui.motion; timing: ui.timing }
    }

}
