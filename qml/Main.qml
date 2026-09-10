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
    title: win.tr("一键内网穿透GUI工具")
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
    function tr(text) { return bridge.translate(text, win.data.language) }
    function duration(base) { return motion ? Math.round(base * timing) : 0 }
    Behavior on accent { ColorAnimation { duration: win.duration(240); easing.type: Easing.InOutCubic } }
    onClosing: close => { close.accepted = bridge.handleClose() }

    component Caption: Label {
        color: win.muted
        wrapMode: Text.WordWrap
        font.pixelSize: 12
        Layout.fillWidth: true
    }
    component ProfileSelect: ComboBox {
        id: profileSelect
        implicitHeight: 46
        background: Rectangle {
            radius: 16; color: win.tonal
            border.width: parent.visualFocus ? 2 : 0; border.color: win.accent
            PressRipple { control: profileSelect; tint: win.accent; cornerRadius: 16; motion: win.motion; timing: win.timing }
        }
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
                opacity: button.down ? .08 : button.hovered ? .05 : 0
                Behavior on opacity { OpacityAnimator { duration: win.duration(180); easing.type: Easing.OutCubic } }
            }
            PressRipple {
                control: button; tint: button.filled ? "white" : win.accent
                motion: win.motion; timing: win.timing
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
                    text: win.tr(modelData)
                    hoverEnabled: true
                    onClicked: choice.chosen(modelData)
                    background: Rectangle {
                        radius: 20
                        color: option.visualFocus ? "#306750A4" : "transparent"
                        border.width: option.visualFocus ? 1 : 0
                        border.color: win.accent
                        PressRipple {
                            control: option; tint: choice.selected === option.modelData ? "white" : win.accent
                            cornerRadius: 20; motion: win.motion; timing: win.timing
                        }
                    }
                    contentItem: Text {
                        text: option.text
                        font.family: win.font.family
                        font.pixelSize: win.data.language === "en" ? 12 : 14
                        elide: Text.ElideRight
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
                            Heading { text: win.tr("一键内网穿透"); font.pixelSize: 26 }
                            Caption { text: win.tr("嗨，想把你的小小世界分享出去吗？交给我吧♪") }
                        }
                        Action { objectName: "settingsButton"; text: win.tr("设置 ⚙"); onClicked: win.settingsOpen = true }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        ProfileSelect {
                            objectName: "tunnelSelector"
                            Layout.fillWidth: true
                            model: win.data.tunnels
                            textRole: "name"; valueRole: "id"
                            currentIndex: win.data.tunnels.findIndex(row => row.id === win.data.selectedTunnel)
                            onActivated: bridge.selectTunnel(currentValue)
                        }
                        Label { text: win.data.runningCount + " · " + win.tr("运行中"); color: win.accent }
                        Action { text: win.tr("隧道管理"); onClicked: tunnelDrawer.open() }
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
                                Heading { text: win.tr("连接设置 · 一起准备吧") }
                                RowLayout {
                                    Layout.fillWidth: true; spacing: 20
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 1
                                        Caption { text: win.tr("穿透引擎") }
                                        Choice { options: ["自动", "Cloudflare", "FRP"]; selected: win.data.mode; enabled: !win.data.active; onChosen: value => bridge.setField("mode", value) }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 1
                                        Caption { text: win.tr("本地服务类型") }
                                        Choice { options: ["HTTP", "HTTPS", "TCP"]; selected: win.data.protocol; enabled: !win.data.active; onChosen: value => bridge.setField("protocol", value) }
                                    }
                                }
                                Caption { text: win.tr("本地端口") }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Entry {
                                        objectName: "portField"
                                        text: win.data.port
                                        placeholderText: win.tr("本地端口")
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
                                    Action { text: win.data.scanBusy ? win.tr("正在找哦…") : win.tr("帮你找端口"); enabled: !win.data.active && !win.data.scanBusy; onClicked: bridge.scan() }
                                }
                                Caption { text: win.tr("告诉我本地端口吧。不记得也没关系，让我帮你找找♪") }
                            }
                            GridLayout {
                                columns: 2
                                Layout.fillWidth: true; columnSpacing: 8; rowSpacing: 8
                            Action { objectName: "startButton"; text: win.tr("开始穿透 ♪"); filled: true; Layout.fillWidth: true; enabled: !win.data.active && !win.data.cfBusy; onClicked: bridge.start() }
                                Action { text: win.tr("停止，歇一会"); Layout.fillWidth: true; enabled: win.data.active && !win.data.stopping; onClicked: bridge.stop() }
                                Action { text: win.tr("重新出发"); Layout.fillWidth: true; enabled: win.data.active && !win.data.stopping; onClicked: bridge.restart() }
                                Action { text: win.tr("后台陪着你"); quiet: true; Layout.fillWidth: true; onClicked: bridge.background() }
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
                                        Caption { text: win.tr("连接状态") }
                                        Label { text: win.data.status; color: win.ink; font.bold: true; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Entry { text: win.data.address; readOnly: true; placeholderText: win.tr("出发后，你的外网地址就会出现在这里哦♪") }
                                    Action { text: win.tr("复制地址"); quiet: true; enabled: win.data.address.length > 0; onClicked: bridge.copyAddress() }
                                    Action { text: win.tr("去看看 ↗"); quiet: true; enabled: win.data.address.length > 0; onClicked: bridge.openAddress() }
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
                                    Heading { text: win.tr("我们的连接手记"); font.pixelSize: 15 }
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
                                ColumnLayout {
                                    visible: win.frpOpen
                                    Layout.fillWidth: true; spacing: 10
                                    RowLayout {
                                        Layout.fillWidth: true
                                        ProfileSelect {
                                            objectName: "serverSelector"
                                            Layout.fillWidth: true
                                            model: win.data.servers; textRole: "name"; valueRole: "id"
                                            currentIndex: win.data.servers.findIndex(row => row.id === win.data.serverId)
                                            enabled: !win.data.active
                                            onActivated: bridge.selectServer(currentValue)
                                        }
                                        Action { text: win.tr("服务端管理"); quiet: true; onClicked: serverDrawer.open() }
                                    }
                                    Caption { text: win.data.server ? win.data.server + ":" + win.data.server_port : win.tr("请在服务端管理中填写 FRPS 配置。") }
                                    Caption { text: win.tr("远程映射端口") }
                                    Entry { text: win.data.remote_port; enabled: !win.data.active; onTextEdited: bridge.setField("remote_port", text) }
                                    Caption { text: win.tr("每条隧道独立选择服务端与远程端口。Token 使用 Windows 当前用户加密保存。") }
                                }
                            }
                        }
                    }
                    Caption { text: win.tr("HTTP / HTTPS 可用 Cloudflare，TCP 用 FRP。关闭窗口后留在托盘继续运行；选择「退出」会停止全部隧道。") }
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
                        Action { objectName: "backButton"; text: win.tr("← 回去吧"); quiet: true; onClicked: win.settingsOpen = false }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Heading { text: win.tr("偏爱，由你决定"); font.pixelSize: 26 }
                            Caption { text: win.tr("换一抹颜色，调一调节奏。最舒服的模样，当然要听你的呀♪") }
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
                                Heading { text: win.tr("今天，喜欢哪一种颜色？") }
                                Choice {
                                    objectName: "themeChoice"
                                    options: ["爱莉粉", "薰衣紫", "玫瑰粉", "薄荷绿", "晴空蓝"]
                                    selected: win.data.theme
                                    onChosen: value => bridge.setPreference("theme", value)
                                }
                                Caption { text: win.tr("选好就会慢慢换上哦，不用重新打开。") }
                            }
                            Card {
                                RowLayout {
                                    Layout.fillWidth: true
                                    Heading { text: win.tr("让动画跟上你的节奏") }
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
                                    Caption { text: win.tr("0.5 × · 慢慢来") }
                                    Caption { text: win.tr("2.0 × · 轻快一点"); horizontalAlignment: Text.AlignRight }
                                }
                                Caption { text: win.tr("想慢慢欣赏，还是轻快一点？调到你喜欢的节奏就好♪") }
                            }
                            Card {
                                Heading { text: win.tr("也可以，安静一点") }
                                Choice { options: ["开启动画", "关闭动画"]; selected: win.data.motion ? "开启动画" : "关闭动画"; onChosen: value => bridge.setPreference("motion", value === "开启动画") }
                                Caption { text: win.data.systemMotion ? win.tr("关闭动画后，切换会直接完成。舒服最重要啦♪") : win.tr("Windows 已关闭界面动画，我也会陪你保持安静哦。") }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                Action { objectName: "previewButton"; text: win.tr("试试这个手感 ♪"); filled: true }
                                Item { Layout.fillWidth: true }
                                Action { text: win.tr("恢复初见的样子"); quiet: true; onClicked: bridge.resetPreferences() }
                            }
                            Caption { text: win.data.saveError || win.tr("偏好会自动记住，下次见面，还是你喜欢的模样♪"); color: win.data.saveError ? "#B3261E" : win.muted }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.minimumWidth: 0
                            Layout.alignment: Qt.AlignTop
                            spacing: 14
                            Card {
                                RowLayout {
                                    Layout.fillWidth: true
                                    Heading { text: win.tr("语言") }
                                    ComboBox {
                                        id: languageCombo
                                        objectName: "languageCombo"
                                        Layout.preferredWidth: 210
                                        implicitHeight: 48
                                        model: ["简体中文", "English"]
                                        currentIndex: win.data.language === "en" ? 1 : 0
                                        onActivated: index => bridge.setPreference("language", index === 1 ? "en" : "zh_CN")
                                        Accessible.name: win.tr("语言")
                                        leftPadding: 16; rightPadding: 38
                                        contentItem: Text {
                                            text: languageCombo.displayText
                                            font: win.font; color: win.ink
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                        indicator: Label {
                                            x: languageCombo.width - width - 16
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: "⌄"; color: win.accent
                                        }
                                        background: Rectangle {
                                            radius: 16; color: win.tonal
                                            border.width: languageCombo.visualFocus ? 2 : 0
                                            border.color: win.accent
                                            PressRipple {
                                                control: languageCombo; tint: win.accent; cornerRadius: 16
                                                motion: win.motion; timing: win.timing
                                            }
                                        }
                                        delegate: ItemDelegate {
                                            required property int index
                                            required property string modelData
                                            width: languageCombo.width - 8
                                            text: modelData
                                            highlighted: languageCombo.highlightedIndex === index
                                            Material.accent: win.accent
                                        }
                                        popup: Popup {
                                            objectName: "languagePopup"
                                            y: languageCombo.height + 6
                                            width: languageCombo.width
                                            padding: 4
                                            implicitHeight: contentItem.implicitHeight + 8
                                            contentItem: ListView {
                                                clip: true
                                                implicitHeight: contentHeight
                                                model: languageCombo.popup.visible ? languageCombo.delegateModel : null
                                                currentIndex: languageCombo.highlightedIndex
                                            }
                                            background: Rectangle {
                                                radius: 16; color: "#FFFBFF"
                                                border.width: 1; border.color: win.tonal
                                            }
                                            enter: Transition { OpacityAnimator { from: 0; to: 1; duration: win.duration(120) } }
                                            exit: Transition { OpacityAnimator { from: 1; to: 0; duration: win.duration(100) } }
                                        }
                                    }
                                }
                            }
                            Card {
                                Heading { text: win.tr("外网地址，由你选择") }
                                Choice {
                                    objectName: "addressModeChoice"
                                    options: ["临时地址", "固定域名"]
                                    selected: win.data.cfEnabled ? "固定域名" : "临时地址"
                                    enabled: !win.data.active && !win.data.cfBusy
                                    onChosen: value => bridge.setCloudflare("enabled", value === "固定域名")
                                }
                                ColumnLayout {
                                    objectName: "quickAddressHelp"
                                    visible: !win.data.cfEnabled && !win.data.cfBusy
                                    Layout.fillWidth: true
                                    spacing: 12
                                    Heading { text: win.tr("没有域名，也能出发♪"); font.pixelSize: 16 }
                                    Caption { text: win.tr("临时地址无需登录，也不用准备域名。适合把本地网站分享出去，重新连接后地址可能变化。") }
                                    Action { objectName: "quickStartButton"; text: win.tr("使用临时地址，回主页 ♪"); filled: true; enabled: !win.data.active; onClicked: bridge.cloudflareAction("temporary") }
                                    Caption { text: win.tr("想保留同一个地址？选择上方「固定域名」，需要你已有的域名。") }
                                }
                                ColumnLayout {
                                    objectName: "fixedDomainSetup"
                                    visible: win.data.cfEnabled || win.data.cfBusy
                                    Layout.fillWidth: true
                                    spacing: win.compactLayout ? 8 : 10
                                    Caption { text: win.tr("① 添加自有域名 → ② 选择域名并授权 → ③ 绑定地址") }
                                    Rectangle {
                                        Layout.fillWidth: true
                                        implicitHeight: authHelp.implicitHeight + 20
                                        radius: 14; color: win.tonal
                                        Caption {
                                            id: authHelp
                                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10 }
                                            text: win.tr("登录账户后，还要在授权页选择域名。列表为空时，请先添加域名或检查账户权限；仅登录不会完成授权。")
                                        }
                                    }
                                    Label { objectName: "authorizationStatus"; text: win.data.cfStatus; color: win.accent; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    Caption {
                                        visible: win.data.cfBusy && win.data.cfOperation === "login"
                                        text: win.tr("正在等待授权证书。请完成网页上的域名授权；成功后会尝试切回这里。网页报错时，请取消后重试。")
                                    }
                                    Flow {
                                        Layout.fillWidth: true; spacing: 8
                                        Action { objectName: "authorizeButton"; text: win.data.cfCertPresent ? win.tr("已收到本地证书") : win.tr("选择域名并授权 ↗"); filled: true; enabled: !win.data.cfCertPresent && !win.data.active && !win.data.accountBusy; onClicked: bridge.cloudflareAction("login") }
                                        Action { text: win.tr("添加／管理域名 ↗"); quiet: true; onClicked: bridge.cloudflareAction("dashboard") }
                                        Action { text: win.tr("取消操作"); visible: win.data.cfBusy; onClicked: bridge.cloudflareAction("cancel") }
                                        Action { text: win.tr("继续浏览器授权 ↗"); visible: win.data.cfBusy && win.data.cfLoginUrl.length > 0; onClicked: bridge.cloudflareAction("browser") }
                                    }
                                    Entry {
                                        id: cfHostnameField
                                        objectName: "cloudflareHostname"
                                        text: win.data.cfHostname
                                        placeholderText: win.tr("你的固定域名，例如 hello.example.com")
                                        Accessible.name: win.tr("你的固定域名")
                                        enabled: !win.data.active && !win.data.cfBusy
                                        onEditingFinished: bridge.setCloudflare("hostname", text)
                                    }
                                    Action {
                                        objectName: "bindDomainButton"
                                        text: win.data.cfReady ? win.tr("重新绑定域名") : win.tr("创建隧道并绑定域名")
                                        enabled: win.data.cfCertPresent && cfHostnameField.text.trim().length > 0 && !win.data.active && !win.data.accountBusy
                                        onClicked: {
                                            bridge.setCloudflare("hostname", cfHostnameField.text)
                                            bridge.cloudflareAction("prepare")
                                        }
                                    }
                                    Caption { text: win.data.cfReady ? win.tr("准备好啦♪ 回主页选择自动或 Cloudflare，填好本地端口，再点开始穿透。") : win.tr("收到本地授权证书后才能绑定。此操作会创建隧道和 DNS 记录，不覆盖已有同名记录。") }
                                    Action { text: win.tr("没有域名？使用临时地址 ♪"); quiet: true; enabled: !win.data.active && win.data.cfOperation !== "prepare"; onClicked: bridge.cloudflareAction("temporary") }
                                }
                            }
                        }
                    }
                    Item { Layout.preferredHeight: 18 }
                }
            }
        }
    }
    Drawer {
        id: tunnelDrawer
        objectName: "tunnelDrawer"
        width: Math.min(440, win.width - 32); height: win.height
        edge: Qt.LeftEdge
        enter: Transition { NumberAnimation { property: "position"; from: 0; to: 1; duration: win.duration(180); easing.type: Easing.OutCubic } }
        exit: Transition { NumberAnimation { property: "position"; from: 1; to: 0; duration: win.duration(180); easing.type: Easing.InCubic } }
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 18; spacing: 10
            Heading { text: win.tr("隧道管理") }
            Entry { objectName: "tunnelName"; text: win.data.tunnelName; placeholderText: win.tr("隧道名称"); onEditingFinished: bridge.renameTunnel(text) }
            RowLayout {
                Action { text: win.tr("新增隧道"); filled: true; onClicked: bridge.addTunnel() }
                Action { text: win.tr("删除当前"); enabled: win.data.tunnels.length > 1 && !win.data.active && !win.data.cfBusy; onClicked: bridge.deleteTunnel() }
            }
            ListView {
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 8
                model: win.data.tunnels
                ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    required property var modelData
                    width: ListView.view.width; height: 136; radius: 18
                    color: modelData.id === win.data.selectedTunnel ? win.tonal : "#FFFBFF"
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 12; spacing: 4
                        Label { text: modelData.name + " · " + modelData.port; font.bold: true; color: win.ink; elide: Text.ElideRight; Layout.fillWidth: true }
                        Caption { text: modelData.status; maximumLineCount: 1; elide: Text.ElideRight }
                        Caption { text: modelData.address; maximumLineCount: 1; elide: Text.ElideRight }
                        RowLayout {
                            Action { text: win.tr("查看"); implicitHeight: 36; onClicked: { bridge.selectTunnel(modelData.id); tunnelDrawer.close() } }
                            Action { text: modelData.active ? win.tr("停止") : win.tr("启动"); implicitHeight: 36; onClicked: modelData.active ? bridge.stopTunnel(modelData.id) : bridge.startTunnel(modelData.id) }
                        }
                    }
                }
            }
            RowLayout {
                Action { text: win.tr("全部启动"); onClicked: bridge.startAll() }
                Action { text: win.tr("全部停止"); onClicked: bridge.stopAll() }
            }
            Caption { text: win.tr("删除仅移除本地列表；云端隧道和 DNS 记录会保留。") }
            Action { text: win.tr("退出"); quiet: true; onClicked: bridge.exitApplication() }
        }
    }
    Drawer {
        id: serverDrawer
        objectName: "serverDrawer"
        width: Math.min(460, win.width - 32); height: win.height; edge: Qt.RightEdge
        enter: Transition { NumberAnimation { property: "position"; from: 0; to: 1; duration: win.duration(180); easing.type: Easing.OutCubic } }
        exit: Transition { NumberAnimation { property: "position"; from: 1; to: 0; duration: win.duration(180); easing.type: Easing.InCubic } }
        ScrollView {
            anchors.fill: parent; anchors.margins: 18; contentWidth: availableWidth
            ColumnLayout {
                width: parent.width; spacing: 10
                Heading { text: win.tr("服务端管理") }
                ProfileSelect {
                    Layout.fillWidth: true
                    model: win.data.servers; textRole: "name"; valueRole: "id"
                    currentIndex: win.data.servers.findIndex(row => row.id === win.data.serverId)
                    enabled: !win.data.active
                    onActivated: bridge.selectServer(currentValue)
                }
                Entry { id: serverNameEntry; text: win.data.serverName; placeholderText: win.tr("服务端名称"); enabled: !win.data.active }
                Entry { text: win.data.server; placeholderText: win.tr("域名或 IP"); enabled: !win.data.active; onTextEdited: bridge.setField("server", text) }
                Entry { text: win.data.server_port; placeholderText: win.tr("服务端口"); enabled: !win.data.active; onTextEdited: bridge.setField("server_port", text) }
                Entry { text: win.data.token; placeholderText: win.tr("认证 Token"); echoMode: TextInput.Password; enabled: !win.data.active; onTextEdited: bridge.setField("token", text) }
                Entry { text: win.data.public_host; placeholderText: win.tr("公网访问主机（可选）"); enabled: !win.data.active; onTextEdited: bridge.setField("public_host", text) }
                Flow {
                    Layout.fillWidth: true; spacing: 8
                    Action { text: win.tr("保存服务端"); filled: true; enabled: !win.data.active && serverNameEntry.text.trim().length > 0; onClicked: bridge.saveServer(serverNameEntry.text, false) }
                    Action { text: win.tr("另存为新服务端"); enabled: !win.data.active && serverNameEntry.text.trim().length > 0; onClicked: bridge.saveServer(serverNameEntry.text, true) }
                    Action { text: win.tr("删除服务端"); enabled: !win.data.active && win.data.serverId.length > 0; onClicked: bridge.deleteServer() }
                }
                Caption { text: win.tr("运行中的配置请先停止再修改。修改后点击保存服务端，才会更新其他引用此档案的隧道。") }
                Caption { text: win.tr("Token 只可由此 Windows 用户解密。重新打开软件不会自动启动隧道。") }
                Action { text: win.tr("完成"); onClicked: serverDrawer.close() }
            }
        }
    }
    Dialog {
        id: message
        objectName: "messageDialog"
        anchors.centerIn: parent
        width: Math.min(win.width - 60, 520)
        title: win.tr("一起看看这个小状况")
        modal: true
        standardButtons: Dialog.NoButton
        footer: DialogButtonBox {
            Action { objectName: "messageOk"; text: win.tr("确定"); focus: true; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
            onAccepted: message.accept()
        }
        enter: Transition { OpacityAnimator { from: 0; to: 1; duration: win.duration(150) } }
        exit: Transition { OpacityAnimator { from: 1; to: 0; duration: win.duration(100) } }
        property string detail: ""
        contentItem: Label { text: win.tr(message.detail); wrapMode: Text.WordWrap; color: win.ink }
    }
    Connections {
        target: bridge
        function onAuthorizationCompleted() {
            win.settingsOpen = true
            if (win.visibility === Window.Minimized || win.visibility === Window.Hidden) win.showNormal()
            win.raise()
            win.requestActivate()
        }
        function onTemporarySelected() { win.settingsOpen = false }
        function onErrorRaised(detail) { message.detail = detail; message.open() }
    }
    Shortcut { sequence: "Escape"; enabled: win.settingsOpen && !message.visible; onActivated: win.settingsOpen = false }
}
