import QtQuick
import QtQuick.Controls
import QtQuick.Controls.impl as Impl
import QtQuick.Layouts
import QtQuick.Templates as T

T.Button {
    required property var ui
    id: button
    property bool filled: false
    property bool quiet: false
    implicitHeight: 48
    implicitWidth: Math.max(90, Math.ceil(contentItem.implicitWidth) + 48)
    hoverEnabled: true
    padding: 16
    verticalPadding: 12
    leftPadding: 18
    rightPadding: 18
    opacity: enabled ? 1 : .42
    font.pixelSize: 14
    spacing: 8
    icon.width: 24
    icon.height: 24
    icon.color: button.filled ? "white" : ui.accent
    contentItem: Impl.IconLabel {
        text: button.text
        font: button.font
        icon: button.icon
        display: button.display
        spacing: button.spacing
        mirrored: button.mirrored
        color: button.filled ? "white" : ui.accent
        alignment: Qt.AlignCenter
    }
    background: Rectangle {
        radius: height / 2
        color: button.filled ? ui.accent : button.quiet ? "transparent" : ui.tonal
        border.width: button.visualFocus ? 2 : 0
        border.color: ui.accent
        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: button.filled ? "white" : ui.accent
            opacity: button.down ? .08 : button.hovered ? .05 : 0
            Behavior on opacity { OpacityAnimator { duration: ui.duration(180); easing.type: Easing.OutCubic } }
        }
        PressRipple {
            control: button; tint: button.filled ? "white" : ui.accent
            motion: ui.motion; timing: ui.timing
        }
    }
    scale: down ? .965 : 1
    Behavior on scale { ScaleAnimator { duration: ui.duration(140); easing.type: Easing.OutCubic } }

}
