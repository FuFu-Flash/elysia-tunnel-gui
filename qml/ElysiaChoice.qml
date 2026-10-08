import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Templates as T

Rectangle {
    required property var ui
    id: choice
    property var options: []
    property string selected: ""
    signal chosen(string value)
    implicitHeight: 46
    Layout.fillWidth: true
    color: ui.tonal
    radius: 23
    opacity: enabled ? 1 : .45
    Rectangle {
        id: selection
        x: 4 + Math.max(0, choice.options.indexOf(choice.selected)) * (choice.width - 8) / Math.max(1, choice.options.length)
        y: 4
        width: (choice.width - 8) / Math.max(1, choice.options.length)
        height: parent.height - 8
        radius: 20
        color: ui.accent
        Behavior on x { XAnimator { duration: ui.duration(250); easing.type: Easing.OutCubic } }
    }
    Row {
        anchors { fill: parent; margins: 4 }
        Repeater {
            model: choice.options
            delegate: T.AbstractButton {
                id: option
                required property string modelData
                width: (choice.width - 8) / Math.max(1, choice.options.length)
                height: choice.height - 8
                text: ui.tr(modelData)
                hoverEnabled: true
                onClicked: choice.chosen(modelData)
                background: Rectangle {
                    radius: 20
                    color: option.visualFocus ? "#306750A4" : "transparent"
                    border.width: option.visualFocus ? 1 : 0
                    border.color: ui.accent
                    PressRipple {
                        control: option; tint: choice.selected === option.modelData ? "white" : ui.accent
                        cornerRadius: 20; motion: ui.motion; timing: ui.timing
                    }
                }
                contentItem: Text {
                    text: option.text
                    font.family: ui.font.family
                    font.pixelSize: ui.data.language === "en" ? 12 : 14
                    elide: Text.ElideRight
                    color: choice.selected === option.modelData ? "white" : ui.accent
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }

}
