import QtQuick
import QtQuick.Controls
import "vendor/qwindowkit" as QWK

// Theme/accessibility adapter around the unchanged QWindowKit QML example.
QWK.QWKButton {
    id: button
    required property var ui
    required property string glyph
    property bool destructive: false
    height: 32
    implicitWidth: 48
    implicitHeight: 32
    hoverEnabled: true
    source: Qt.resolvedUrl("../assets/window-controls/" + glyph + (destructive && hovered ? "-white.png" : "-ink.png"))
    Accessible.name: text
    background: Rectangle {
        radius: 4
        color: button.destructive ? "#C92C48" : ui.accent
        opacity: button.pressed ? (button.destructive ? .9 : .12) : button.hovered ? (button.destructive ? 1 : .07) : 0
        Behavior on opacity { enabled: ui.motion; OpacityAnimator { duration: ui.duration(100); easing.type: Easing.OutCubic } }
    }
    Rectangle {
        anchors.fill: parent
        radius: 4
        color: "transparent"
        border.width: button.visualFocus ? 2 : 0
        border.color: ui.accent
    }
    PressRipple {
        control: button
        tint: button.destructive && button.hovered ? "white" : ui.accent
        cornerRadius: 4
        motion: ui.motion
        timing: ui.timing
    }
    ToolTip.visible: hovered
    ToolTip.delay: 750
    ToolTip.text: text
}
