import QtQuick
import QtQuick.Window

// Use the platform resize loop for DPI changes, Snap and minimum size handling.
Item {
    id: root
    required property var ui
    anchors.fill: parent
    z: 100
    visible: ui.visibility !== Window.Maximized && ui.visibility !== Window.FullScreen
    Repeater {
        model: [Qt.TopEdge, Qt.BottomEdge, Qt.LeftEdge, Qt.RightEdge,
                Qt.TopEdge | Qt.LeftEdge, Qt.TopEdge | Qt.RightEdge,
                Qt.BottomEdge | Qt.LeftEdge, Qt.BottomEdge | Qt.RightEdge]
        MouseArea {
            required property int modelData
            readonly property bool leftEdge: (modelData & Qt.LeftEdge) !== 0
            readonly property bool rightEdge: (modelData & Qt.RightEdge) !== 0
            readonly property bool topEdge: (modelData & Qt.TopEdge) !== 0
            readonly property bool bottomEdge: (modelData & Qt.BottomEdge) !== 0
            readonly property bool corner: (leftEdge || rightEdge) && (topEdge || bottomEdge)
            objectName: "resizeEdge" + modelData
            width: corner ? 8 : leftEdge || rightEdge ? 6 : root.width - 16
            height: corner ? 8 : topEdge || bottomEdge ? 6 : root.height - 16
            x: leftEdge ? 0 : rightEdge ? root.width - width : 8
            y: topEdge ? 0 : bottomEdge ? root.height - height : 8
            cursorShape: corner ? (leftEdge === topEdge ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor) :
                                 topEdge || bottomEdge ? Qt.SizeVerCursor : Qt.SizeHorCursor
            acceptedButtons: Qt.LeftButton
            onPressed: mouse => { ui.startSystemResize(modelData); mouse.accepted = true }
        }
    }
}
