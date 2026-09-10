import QtQuick
import QtQuick.Effects

// Visual only: the owning control keeps pointer, keyboard and accessibility handling.
Item {
    id: root
    objectName: "pressRipple"
    required property Item control
    property color tint: "white"
    property real cornerRadius: height / 2
    property bool motion: true
    property real timing: 2
    property int nextWave: 0
    readonly property bool running: waves.count === 3 &&
        (waves.itemAt(0).playing || waves.itemAt(1).playing || waves.itemAt(2).playing)
    anchors.fill: parent

    function clear() {
        for (let i = 0; i < waves.count; ++i)
            waves.itemAt(i).clear()
    }
    function press() {
        if (!motion || !control.enabled || !visible) return
        // AbstractButton supplies the centre for keyboard activation too.
        const px = typeof control.pressX === "number" ? control.pressX : control.width / 2
        const py = typeof control.pressY === "number" ? control.pressY : control.height / 2
        const point = control.mapToItem(root, px, py)
        waves.itemAt(nextWave).start(Math.max(0, Math.min(width, point.x)),
                                     Math.max(0, Math.min(height, point.y)))
        nextWave = (nextWave + 1) % 3
    }
    onMotionChanged: if (!motion) clear()
    onVisibleChanged: if (!visible) clear()
    Connections {
        target: root.control
        ignoreUnknownSignals: true
        function onPressed() { root.press() }
        function onPressedChanged() {
            if (typeof root.control.pressX !== "number" && root.control.pressed) root.press()
        }
        function onEnabledChanged() { if (!root.control.enabled) root.clear() }
    }
    Item {
        id: source
        anchors.fill: parent
        visible: root.running
        layer.enabled: root.running
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: mask
            maskThresholdMin: .5
            maskSpreadAtMin: 1
            autoPaddingEnabled: false
        }
        Repeater {
            id: waves
            model: 3
            Rectangle {
                id: wave
                property bool playing: animation.running
                property real centerX: 0
                property real centerY: 0
                property real diameter: 0
                width: diameter; height: diameter
                x: centerX - width / 2; y: centerY - height / 2
                radius: width / 2
                color: root.tint
                opacity: 0
                scale: 0
                function clear() { animation.stop(); opacity = 0; scale = 0 }
                function start(px, py) {
                    clear()
                    centerX = px; centerY = py
                    diameter = 2 * Math.hypot(Math.max(px, root.width - px),
                                               Math.max(py, root.height - py))
                    animation.start()
                }
                ParallelAnimation {
                    id: animation
                    ScaleAnimator {
                        target: wave; from: 0; to: 1
                        duration: Math.round(420 * root.timing)
                        easing.type: Easing.OutCubic
                    }
                    SequentialAnimation {
                        OpacityAnimator { target: wave; from: 0; to: .16; duration: Math.round(50 * root.timing) }
                        PauseAnimation { duration: Math.round(120 * root.timing) }
                        OpacityAnimator {
                            target: wave; from: .16; to: 0
                            duration: Math.round(300 * root.timing)
                            easing.type: Easing.OutCubic
                        }
                    }
                }
            }
        }
    }
    Rectangle {
        id: mask
        anchors.fill: parent
        radius: root.cornerRadius
        color: "white"
        visible: false
        layer.enabled: root.running
        layer.smooth: true
    }
}
