import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Templates as T

ApplicationWindow {
    id: win
    objectName: "mainWindow"
    visible: true
    width: Math.min(1240, Screen.desktopAvailableWidth - 64)
    height: Math.min(780, Screen.desktopAvailableHeight - 64)
    minimumWidth: 640
    minimumHeight: 560
    x: Screen.virtualX + (Screen.width - width) / 2
    y: Screen.virtualY + Math.max(0, (Screen.height - height) / 2 - 25)
    title: "一键内网穿透GUI工具"
    font.family: "Microsoft YaHei UI"
    font.pixelSize: 14
    Material.theme: Material.Light
    Material.accent: accent
    Material.primary: accent
    color: backgroundColor
    property var data: bridge.state
    property color accent: data.accent
    property color backgroundColor: Qt.tint("#FAF8FC", Qt.rgba(accent.r, accent.g, accent.b, .035))
    property color tonal: Qt.tint("#FFFFFF", Qt.rgba(accent.r, accent.g, accent.b, .13))
    property color ink: "#211D29"
    property color muted: "#71697D"
    property bool motion: data.motion && data.systemMotion
    property real timing: 2 / data.speed
    property bool settingsOpen: false
    property bool frpOpen: false
    property bool wideLayout: width >= 1000
    property bool compactLayout: height < 720
    property bool animating: slideAnimation.running
    function duration(base) { return motion ? Math.round(base * timing) : 0 }
    Behavior on accent { ColorAnimation { duration: win.duration(240); easing.type: Easing.InOutCubic } }
    onClosing: bridge.close()

    component Caption: Label {
        color: win.muted
        wrapMode: Text.WordWrap
        font.pixelSize: 12
        Layout.fillWidth: true
    }
    component Heading: Label {
        color: win.ink
        font.pixelSize: 18
        font.bold: true
        Layout.fillWidth: true
    }
    component Card: Rectangle {
        property int inset: win.compactLayout ? 14 : 20
        color: "#FFFBFF"
        radius: 28
        Layout.fillWidth: true
        implicitHeight: content.implicitHeight + inset * 2
        default property alias contents: content.data
        ColumnLayout {
            id: content
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: parent.inset }
            spacing: win.compactLayout ? 8 : 12
        }
    }
    component Action: T.Button {
        id: button
        property bool filled: false
        property bool quiet: false
        implicitHeight: 48
        implicitWidth: Math.max(90, Math.ceil(contentItem.implicitWidth) + 48)
        hoverEnabled: true
        padding: 16
        leftPadding: 18
        rightPadding: 18
        opacity: enabled ? 1 : .42
        font.pixelSize: 14
        contentItem: Text {
            text: button.text
            font: button.font
            color: button.filled ? "white" : win.accent
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        background: Rectangle {
            radius: height / 2
            color: button.filled ? win.accent : button.quiet ? "transparent" : win.tonal
            border.width: button.visualFocus ? 2 : 0
            border.color: win.accent
            Rectangle {
                anchors.fill: parent
                radius: height / 2
                color: button.filled ? "white" : win.accent
                opacity: button.down ? .18 : button.hovered ? .08 : 0
                Behavior on opacity { OpacityAnimator { duration: win.duration(180); easing.type: Easing.OutCubic } }
            }
        }
        scale: down ? .965 : 1
        Behavior on scale { ScaleAnimator { duration: win.duration(140); easing.type: Easing.OutCubic } }
    }
    component Choice: Rectangle {
        id: choice
        property var options: []
        property string selected: ""
        signal chosen(string value)
        implicitHeight: 46
        Layout.fillWidth: true
        color: win.tonal
        radius: 23
        opacity: enabled ? 1 : .45
        Rectangle {
            id: selection
            x: 4 + Math.max(0, choice.options.indexOf(choice.selected)) * (choice.width - 8) / Math.max(1, choice.options.length)
            y: 4
            width: (choice.width - 8) / Math.max(1, choice.options.length)
            height: parent.height - 8
            radius: 20
            color: win.accent
            Behavior on x { XAnimator { duration: win.duration(250); easing.type: Easing.OutCubic } }
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
                    text: modelData
                    hoverEnabled: true
                    onClicked: choice.chosen(modelData)
                    background: Rectangle {
                        radius: 20
                        color: option.visualFocus ? "#306750A4" : "transparent"
                        border.width: option.visualFocus ? 1 : 0
                        border.color: win.accent
                    }
                    contentItem: Text {
                        text: option.text
                        font: win.font
                        color: choice.selected === option.modelData ? "white" : win.accent
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
        }
    }
    component Entry: T.TextField {
        id: field
        implicitHeight: 54
        Layout.fillWidth: true
        leftPadding: 16
        rightPadding: 16
        verticalAlignment: TextInput.AlignVCenter
        color: win.ink
        selectByMouse: true
        selectionColor: win.tonal
        selectedTextColor: win.ink
        placeholderTextColor: win.muted
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
            border.color: field.activeFocus ? win.accent : "#D3CCD9"
            Behavior on border.color { ColorAnimation { duration: win.duration(180) } }
        }
    }

    Item {
        id: pages
        anchors.fill: parent
        clip: true
        Item {
            id: pageStrip
            objectName: "pageStrip"
            width: pages.width * 2
            height: pages.height
            x: win.settingsOpen ? -pages.width : 0
            // A single transform keeps both pages adjacent throughout a transition.
            // Separate XAnimators in the same Transition left a page offscreen on return.
            Behavior on x {
                XAnimator {
                    id: slideAnimation
                    duration: win.duration(340)
                    easing.type: Easing.InOutCubic
                }
            }

            ScrollView {
                id: home
                objectName: "homePage"
                width: pages.width; height: pages.height
                contentWidth: availableWidth
                enabled: !win.settingsOpen
                clip: true
                ColumnLayout {
                    width: home.availableWidth - 48
                    x: (home.availableWidth - width) / 2
                    spacing: 14
                    Item { Layout.preferredHeight: 10 }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 16
                        Rectangle {
                            width: 52; height: 52; radius: 18; color: win.tonal
                            Label { anchors.centerIn: parent; text: "↑"; font.pixelSize: 30; color: win.accent }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Heading { text: "一键内网穿透"; font.pixelSize: 26 }
                            Caption { text: "嗨，想把你的小小世界分享出去吗？交给我吧♪" }
                        }
                        Action { objectName: "settingsButton"; text: "设置 ⚙"; onClicked: win.settingsOpen = true }
                    }
                    GridLayout {
                        objectName: "homeColumns"
                        Layout.fillWidth: true
                        columns: win.wideLayout ? 2 : 1
                        columnSpacing: 20
                        rowSpacing: 16
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.minimumWidth: 0
                            Layout.alignment: Qt.AlignTop
                            spacing: 14
                            Card {
                                Heading { text: "连接设置 · 一起准备吧" }
                                RowLayout {
                                    Layout.fillWidth: true; spacing: 20
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 1
                                        Caption { text: "穿透引擎" }
                                        Choice { options: ["自动", "Cloudflare", "FRP"]; selected: win.data.mode; enabled: !win.data.active; onChosen: value => bridge.setField("mode", value) }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 1
                                        Caption { text: "本地服务类型" }
                                        Choice { options: ["HTTP", "HTTPS", "TCP"]; selected: win.data.protocol; enabled: !win.data.active; onChosen: value => bridge.setField("protocol", value) }
                                    }
                                }
                                Caption { text: "本地端口" }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Entry {
                                        objectName: "portField"
                                        text: win.data.port
                                        placeholderText: "本地端口"
                                        enabled: !win.data.active
                                        inputMethodHints: Qt.ImhDigitsOnly
                                        onTextEdited: bridge.setField("port", text)
                                    }
                                    Action {
                                        text: "⌄"; implicitWidth: 48; enabled: !win.data.active && win.data.ports.length > 0
                                        onClicked: portMenu.open()
                                        Menu {
                                            id: portMenu
                                            enter: Transition { OpacityAnimator { from: 0; to: 1; duration: win.duration(120) } }
                                            exit: Transition { OpacityAnimator { from: 1; to: 0; duration: win.duration(100) } }
                                            Repeater {
                                                model: win.data.ports
                                                MenuItem { required property string modelData; text: modelData; onTriggered: bridge.setField("port", modelData) }
                                            }
                                        }
                                    }
                                    Action { text: win.data.scanBusy ? "正在找哦…" : "帮你找端口"; enabled: !win.data.active && !win.data.scanBusy; onClicked: bridge.scan() }
                                }
                                Caption { text: "告诉我本地端口吧。不记得也没关系，让我帮你找找♪" }
                            }
                            GridLayout {
                                columns: 2
                                Layout.fillWidth: true; columnSpacing: 8; rowSpacing: 8
                            Action { objectName: "startButton"; text: "开始穿透 ♪"; filled: true; Layout.fillWidth: true; enabled: !win.data.active && !win.data.cfBusy; onClicked: bridge.start() }
                                Action { text: "停止，歇一会"; Layout.fillWidth: true; enabled: win.data.active && !win.data.stopping; onClicked: bridge.stop() }
                                Action { text: "重新出发"; Layout.fillWidth: true; enabled: win.data.active && !win.data.stopping; onClicked: bridge.restart() }
                                Action { text: "后台陪着你"; quiet: true; Layout.fillWidth: true; onClicked: win.showMinimized() }
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.minimumWidth: 0
                            Layout.alignment: Qt.AlignTop
                            spacing: 14
                            Card {
                                color: win.tonal
                                RowLayout {
                                    Layout.fillWidth: true
                                    Item {
                                        width: 32; height: 32
                                        Rectangle {
                                            anchors.centerIn: parent; width: 22; height: 22; radius: 11
                                            color: win.accent; opacity: .17
                                            SequentialAnimation on scale {
                                                running: win.data.active && win.motion && !win.settingsOpen && win.visibility !== Window.Minimized
                                                loops: Animation.Infinite
                                                ScaleAnimator { from: 1; to: 1.35; duration: win.duration(500); easing.type: Easing.InOutSine }
                                                ScaleAnimator { from: 1.35; to: 1; duration: win.duration(500); easing.type: Easing.InOutSine }
                                            }
                                        }
                                        Rectangle { anchors.centerIn: parent; width: 10; height: 10; radius: 5; color: win.data.rawStatus === "已连接" ? "#287D50" : win.accent }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Caption { text: "连接状态" }
                                        Label { text: win.data.status; color: win.ink; font.bold: true; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Entry { text: win.data.address; readOnly: true; placeholderText: "出发后，你的外网地址就会出现在这里哦♪" }
                                    Action { text: "复制地址"; quiet: true; enabled: win.data.address.length > 0; onClicked: bridge.copyAddress() }
                                    Action { text: "去看看 ↗"; quiet: true; enabled: win.data.address.length > 0; onClicked: bridge.openAddress() }
                                }
                            }
                            Choice {
                                Layout.fillWidth: false; Layout.preferredWidth: 250
                                options: ["运行日志", "FRP 配置"]
                                selected: win.frpOpen ? "FRP 配置" : "运行日志"
                                onChosen: value => win.frpOpen = value === "FRP 配置"
                            }
                            Card {
                                ColumnLayout {
                                    visible: !win.frpOpen
                                    Layout.fillWidth: true
                                    Heading { text: "我们的连接手记"; font.pixelSize: 15 }
                                    ScrollView {
                                        Layout.fillWidth: true; Layout.preferredHeight: 145
                                        contentWidth: availableWidth
                                        TextArea {
                                            id: logArea
                                            text: bridge.logText
                                            readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                                            color: win.muted; font.pixelSize: 12
                                            background: null
                                        }
                                    }
                                }
                                GridLayout {
                                    visible: win.frpOpen
                                    Layout.fillWidth: true; columns: 2; columnSpacing: 12; rowSpacing: 10
                                    Caption { text: "FRPS 服务器"; Layout.columnSpan: 2 }
                                    Entry { Layout.columnSpan: 2; text: win.data.server; placeholderText: "域名或 IP"; enabled: !win.data.active; onTextEdited: bridge.setField("server", text) }
                                    Caption { text: "服务端口" }
                                    Caption { text: "远程映射端口" }
                                    Entry { text: win.data.server_port; enabled: !win.data.active; onTextEdited: bridge.setField("server_port", text) }
                                    Entry { text: win.data.remote_port; enabled: !win.data.active; onTextEdited: bridge.setField("remote_port", text) }
                                    Caption { text: "认证 Token" }
                                    Caption { text: "公网访问主机（可选）" }
                                    Entry { text: win.data.token; echoMode: TextInput.Password; enabled: !win.data.active; onTextEdited: bridge.setField("token", text) }
                                    Entry { text: win.data.public_host; enabled: !win.data.active; onTextEdited: bridge.setField("public_host", text) }
                                    Caption { Layout.columnSpan: 2; text: "记得准备好 FRPS 服务端，并放行映射端口哦。Token 只在这次会话里使用。" }
                                }
                            }
                        }
                    }
                    Caption { text: "让我来选吧：HTTP / HTTPS 用 Cloudflare，TCP 用 FRP。临时地址用于测试哦。\n后台运行时，我会在任务栏等你；关闭窗口，穿透也会一起停下。" }
                    Item { Layout.preferredHeight: 16 }
                }
            }

            ScrollView {
                id: settings
                objectName: "settingsPage"
                x: pages.width
                width: pages.width; height: pages.height
                contentWidth: availableWidth
                enabled: win.settingsOpen
                clip: true
                ColumnLayout {
                    width: settings.availableWidth - 48
                    x: (settings.availableWidth - width) / 2
                    spacing: 18
                    Item { Layout.preferredHeight: 10 }
                    RowLayout {
                        Layout.fillWidth: true
                        Action { objectName: "backButton"; text: "← 回去吧"; quiet: true; onClicked: win.settingsOpen = false }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Heading { text: "偏爱，由你决定"; font.pixelSize: 26 }
                            Caption { text: "换一抹颜色，调一调节奏。最舒服的模样，当然要听你的呀♪" }
                        }
                    }
                    GridLayout {
                        objectName: "settingsColumns"
                        Layout.fillWidth: true
                        columns: win.wideLayout ? 2 : 1
                        columnSpacing: 20
                        rowSpacing: 16
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.minimumWidth: 0
                            Layout.alignment: Qt.AlignTop
                            spacing: 14
                            Card {
                                Heading { text: "今天，喜欢哪一种颜色？" }
                                Choice {
                                    objectName: "themeChoice"
                                    options: ["爱莉粉", "薰衣紫", "玫瑰粉", "薄荷绿", "晴空蓝"]
                                    selected: win.data.theme
                                    onChosen: value => bridge.setPreference("theme", value)
                                }
                                Caption { text: "选好就会慢慢换上哦，不用重新打开。" }
                            }
                            Card {
                                RowLayout {
                                    Layout.fillWidth: true
                                    Heading { text: "让动画跟上你的节奏" }
                                    Label { text: Number(win.data.speed).toFixed(1) + " ×"; color: win.accent; font.bold: true }
                                }
                                Slider {
                                    id: speedSlider
                                    objectName: "speedSlider"
                                    Layout.fillWidth: true
                                    from: .5; to: 2; stepSize: .1
                                    value: win.data.speed
                                    onMoved: bridge.setPreference("speed", value)
                                    background: Rectangle {
                                        x: speedSlider.leftPadding; y: speedSlider.topPadding + speedSlider.availableHeight / 2 - height / 2
                                        width: speedSlider.availableWidth; height: 6; radius: 3; color: win.tonal
                                        Rectangle { width: speedSlider.visualPosition * parent.width; height: parent.height; radius: 3; color: win.accent }
                                    }
                                    handle: Rectangle {
                                        x: speedSlider.leftPadding + speedSlider.visualPosition * (speedSlider.availableWidth - width)
                                        y: speedSlider.topPadding + speedSlider.availableHeight / 2 - height / 2
                                        width: 22; height: 22; radius: 11; color: win.accent
                                        border.width: speedSlider.activeFocus ? 3 : 0; border.color: win.tonal
                                        scale: speedSlider.pressed ? 1.16 : 1
                                        Behavior on scale { ScaleAnimator { duration: win.duration(120) } }
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Caption { text: "0.5 × · 慢慢来" }
                                    Caption { text: "2.0 × · 轻快一点"; horizontalAlignment: Text.AlignRight }
                                }
                                Caption { text: "想慢慢欣赏，还是轻快一点？调到你喜欢的节奏就好♪" }
                            }
                            Card {
                                Heading { text: "也可以，安静一点" }
                                Choice { options: ["开启动画", "减少动态"]; selected: win.data.motion ? "开启动画" : "减少动态"; onChosen: value => bridge.setPreference("motion", value === "开启动画") }
                                Caption { text: win.data.systemMotion ? "减少动态后，切换会直接完成。舒服最重要啦♪" : "Windows 已关闭界面动画，我也会陪你保持安静哦。" }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                Action { objectName: "previewButton"; text: "试试这个手感 ♪"; filled: true }
                                Item { Layout.fillWidth: true }
                                Action { text: "恢复初见的样子"; quiet: true; onClicked: bridge.resetPreferences() }
                            }
                            Caption { text: win.data.saveError || "偏好会自动记住，下次见面，还是你喜欢的模样♪"; color: win.data.saveError ? "#B3261E" : win.muted }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.minimumWidth: 0
                            Layout.alignment: Qt.AlignTop
                            spacing: 14
                            Card {
                                Heading { text: "让地址，一直在这里等你" }
                                Caption { text: "登录 Cloudflare 后，可以把你已有的域名绑定到隧道。先把域名托管到 Cloudflare，再来和我一起准备吧♪" }
                                Label { text: win.data.cfStatus; color: win.accent; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                Flow {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    Action { text: "登录 Cloudflare"; filled: true; enabled: !win.data.active && !win.data.cfBusy; onClicked: bridge.cloudflareAction("login") }
                                    Action { text: "打开控制台 ↗"; quiet: true; onClicked: bridge.cloudflareAction("dashboard") }
                                    Action { text: "取消操作"; visible: win.data.cfBusy; onClicked: bridge.cloudflareAction("cancel") }
                                    Action { text: "继续浏览器授权 ↗"; visible: win.data.cfBusy && win.data.cfLoginUrl.length > 0; onClicked: bridge.cloudflareAction("browser") }
                                }
                                Choice {
                                    options: ["临时地址", "固定域名"]
                                    selected: win.data.cfEnabled ? "固定域名" : "临时地址"
                                    enabled: !win.data.active && !win.data.cfBusy
                                    onChosen: value => bridge.setCloudflare("enabled", value === "固定域名")
                                }
                                Caption { text: "你的固定域名" }
                                Entry {
                                    id: cfHostnameField
                                    objectName: "cloudflareHostname"
                                    text: win.data.cfHostname
                                    placeholderText: "例如 hello.example.com"
                                    enabled: !win.data.active && !win.data.cfBusy
                                    onEditingFinished: bridge.setCloudflare("hostname", text)
                                }
                                Action {
                                    text: win.data.cfReady ? "重新绑定域名" : "创建隧道并绑定域名"
                                    enabled: !win.data.active && !win.data.cfBusy
                                    onClicked: {
                                        bridge.setCloudflare("hostname", cfHostnameField.text)
                                        bridge.cloudflareAction("prepare")
                                    }
                                }
                                Caption { text: win.data.cfReady ? "准备好啦♪ 回主页选择自动或 Cloudflare，填好本地端口，再点开始穿透。" : "这个按钮会在你的账户中创建隧道和 DNS 记录；已有的同名记录不会被覆盖。固定域名用于 HTTP / HTTPS 网站。" }
                                Caption { text: "授权在 Cloudflare 官方网页完成，应用不接收你的密码。授权证书和隧道凭据保存在本机。" }
                            }
                        }
                    }
                    Item { Layout.preferredHeight: 18 }
                }
            }
        }
    }
    Dialog {
        id: message
        objectName: "messageDialog"
        anchors.centerIn: parent
        width: Math.min(win.width - 60, 520)
        title: "一起看看这个小状况"
        modal: true
        standardButtons: Dialog.Ok
        enter: Transition { OpacityAnimator { from: 0; to: 1; duration: win.duration(150) } }
        exit: Transition { OpacityAnimator { from: 1; to: 0; duration: win.duration(100) } }
        property string detail: ""
        contentItem: Label { text: message.detail; wrapMode: Text.WordWrap; color: win.ink }
    }
    Connections {
        target: bridge
        function onErrorRaised(detail) { message.detail = detail; message.open() }
    }
    Shortcut { sequence: "Escape"; enabled: win.settingsOpen && !message.visible; onActivated: win.settingsOpen = false }
}
