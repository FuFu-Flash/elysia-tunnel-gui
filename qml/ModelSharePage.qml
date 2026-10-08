import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Templates as T

ScrollView {
    id: page
    required property var ui
    required property var share
    property var info: share.state
    property var service: info.selectedService
    property bool showKey: false
    contentWidth: availableWidth
    clip: true

    component Caption: ElysiaCaption { ui: page.ui }
    component Heading: ElysiaHeading { ui: page.ui }
    component Card: ElysiaCard { ui: page.ui }
    component Action: ElysiaAction { ui: page.ui; implicitHeight: 44 }
    component Entry: ElysiaEntry { ui: page.ui; implicitHeight: 46 }
    component Select: ElysiaProfileSelect { ui: page.ui; implicitHeight: 42 }

    ColumnLayout {
        width: page.availableWidth - 48
        x: 24
        spacing: 14
        Item { Layout.preferredHeight: 10 }
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true; spacing: 4
                Heading { text: page.ui.tr("本地大模型分享"); font.pixelSize: 24 }
                Caption { text: page.ui.tr("让你的模型，也能与远方相遇♪") }
            }
            Action {
                objectName: "scanModelsButton"
                text: page.info.scanBusy ? page.ui.tr("正在识别…") : page.ui.tr("重新检测")
                enabled: !page.info.scanBusy
                onClicked: page.share.scan()
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Select {
                objectName: "modelTunnelSelector"
                Layout.fillWidth: true
                model: page.ui.data.tunnels; textRole: "name"; valueRole: "id"
                currentIndex: page.ui.data.tunnels.findIndex(row => row.id === page.ui.data.selectedTunnel)
                Accessible.name: page.ui.tr("分享所用的隧道")
                onActivated: bridge.selectTunnel(currentValue)
            }
            Action { text: page.ui.tr("新增模型隧道"); quiet: true; onClicked: page.share.createTunnel() }
        }
        GridLayout {
            objectName: "modelShareColumns"
            Layout.fillWidth: true
            columns: page.ui.wideLayout ? 2 : 1
            columnSpacing: 20; rowSpacing: 16
            Card {
                Layout.preferredWidth: 1
                Layout.minimumWidth: 0
                Layout.alignment: Qt.AlignTop
                RowLayout {
                    Layout.fillWidth: true
                    Heading { text: page.ui.tr("你的模型服务") }
                    Label { text: page.info.services.length; color: page.ui.accent; font.bold: true }
                }
                ListView {
                    objectName: "modelServiceList"
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(164, Math.max(88, contentHeight))
                    visible: page.info.services.length > 0
                    model: page.info.services
                    clip: true; spacing: 6
                    ScrollBar.vertical: ScrollBar {}
                    delegate: T.AbstractButton {
                        id: serviceButton
                        required property var modelData
                        width: ListView.view.width; height: 76
                        hoverEnabled: true
                        Accessible.name: modelData.name + " " + modelData.port
                        enabled: !page.ui.data.active && !page.info.scanBusy
                        onClicked: page.share.selectService(modelData.id)
                        background: Rectangle {
                            radius: 16
                            color: page.info.selectedId === serviceButton.modelData.id ? page.ui.tonal : serviceButton.hovered ? page.ui.backgroundColor : "#FFFFFF"
                            border.width: page.info.selectedId === serviceButton.modelData.id || serviceButton.visualFocus ? 2 : 1
                            border.color: page.info.selectedId === serviceButton.modelData.id || serviceButton.visualFocus ? page.ui.accent : page.ui.tonal
                            PressRipple { control: serviceButton; tint: page.ui.accent; cornerRadius: 16; motion: page.ui.motion; timing: page.ui.timing }
                        }
                        contentItem: ColumnLayout {
                            anchors { fill: parent; margins: 12 } spacing: 4
                            RowLayout {
                                Layout.fillWidth: true
                                Label { text: serviceButton.modelData.name; color: page.ui.ink; font.bold: true; elide: Text.ElideRight; Layout.fillWidth: true }
                                Label { text: serviceButton.modelData.verified ? page.ui.tr("已识别") : page.ui.tr("需要验证"); color: page.ui.accent; font.pixelSize: 12 }
                            }
                            Label { text: (serviceButton.modelData.host === "::1" ? "[::1]" : serviceButton.modelData.host) + ":" + serviceButton.modelData.port + " · " + serviceButton.modelData.models.length + " " + page.ui.tr("个模型"); color: page.ui.muted; font.pixelSize: 12 }
                        }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 124
                    visible: page.info.services.length === 0
                    radius: 16; color: page.ui.backgroundColor
                    ColumnLayout {
                        anchors { fill: parent; margins: 16 } spacing: 8
                        Heading { text: page.info.scanBusy ? page.ui.tr("让我找找，模型在哪里♪") : page.ui.tr("先把模型服务打开吧♪"); font.pixelSize: 16 }
                        Caption { text: page.info.scanBusy ? page.ui.tr("正在读取本机服务的模型列表，不会加载模型。") : page.ui.tr("支持 Ollama 与 OpenAI 兼容服务。启动后重新检测，或在下方指定端口。") }
                    }
                }
                ProgressBar {
                    Layout.fillWidth: true; visible: page.info.scanBusy
                    indeterminate: true
                    Material.accent: page.ui.accent
                }
                Caption { visible: page.info.scanError.length > 0; text: page.info.scanError; color: "#B3261E" }
                RowLayout {
                    Layout.fillWidth: true
                    Caption { text: page.ui.tr("指定本地端口"); font.bold: true }
                    Action { text: page.ui.tr("检测用 API Key"); quiet: true; implicitHeight: 28; onClicked: page.showKey = !page.showKey }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Entry {
                        id: manualPort
                        objectName: "modelPortField"
                        text: page.service.port ? String(page.service.port) : "8080"
                        placeholderText: "8080"
                        Accessible.name: page.ui.tr("指定本地端口")
                        inputMethodHints: Qt.ImhDigitsOnly
                        enabled: !page.info.scanBusy && !page.ui.data.active
                    }
                    Action {
                        objectName: "probeModelButton"
                        text: page.ui.tr("识别端口")
                        enabled: !page.info.scanBusy && !page.ui.data.active
                        onClicked: { page.share.probePort(manualPort.text, probeKey.text); probeKey.clear() }
                    }
                }
                Caption { text: page.ui.tr("模型服务已有的 API Key"); visible: page.showKey || !!page.service.authRequired }
                Entry {
                    id: probeKey
                    objectName: "modelApiKeyField"
                    visible: page.showKey || !!page.service.authRequired
                    placeholderText: page.ui.tr("服务已有 API Key（可选，仅用于检测）")
                    Accessible.name: page.ui.tr("模型服务已有的 API Key")
                    echoMode: TextInput.Password
                    enabled: !page.info.scanBusy && !page.ui.data.active
                }
                Caption { text: page.ui.tr("Key 仅用于本次本机检测，不会保存，也不会替服务添加鉴权。"); visible: page.showKey || !!page.service.authRequired }
                Caption { text: page.ui.tr("模型"); font.bold: true }
                Select {
                    objectName: "shareModelSelector"
                    Layout.fillWidth: true
                    model: page.service.models || []
                    currentIndex: model.indexOf(page.info.selectedModel)
                    enabled: !page.ui.data.active && model.length > 0
                    Accessible.name: page.ui.tr("模型")
                    onActivated: page.share.selectModel(currentText)
                }
                Caption {
                    visible: !!page.service.verified && page.service.models.length === 0
                    text: page.ui.tr("服务已识别，但模型列表为空。请先在服务中准备模型。")
                }
            }
            ColumnLayout {
                Layout.fillWidth: true; Layout.preferredWidth: 1
                Layout.minimumWidth: 0; Layout.alignment: Qt.AlignTop; spacing: 14
                Card {
                    Heading { text: page.ui.tr("分享到远方") }
                    ElysiaChoice {
                        ui: page.ui
                        objectName: "modelTransportChoice"
                        options: ["FRP", "固定域名", "临时地址"]
                        selected: page.info.transport === "fixed" ? "固定域名" : page.info.transport === "quick" ? "临时地址" : "FRP"
                        enabled: !page.ui.data.active
                        onChosen: value => page.share.setTransport(value === "FRP" ? "FRP" : value === "固定域名" ? "fixed" : "quick")
                    }
                    Caption { visible: page.info.transport === "fixed"; text: page.ui.tr("支持流式输出，需要已授权并绑定的 Cloudflare 域名。") }
                    ColumnLayout {
                        visible: page.info.transport === "FRP"
                        Layout.fillWidth: true; spacing: 8
                        RowLayout {
                            Layout.fillWidth: true
                            Select {
                                objectName: "modelServerSelector"
                                Layout.fillWidth: true
                                model: page.ui.data.servers; textRole: "name"; valueRole: "id"
                                currentIndex: page.ui.data.servers.findIndex(row => row.id === page.ui.data.serverId)
                                enabled: !page.ui.data.active
                                Accessible.name: page.ui.tr("FRPS 服务端")
                                onActivated: bridge.selectServer(currentValue)
                            }
                            Action { text: page.ui.tr("管理"); quiet: true; onClicked: page.ui.manageServers() }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Caption { text: page.ui.tr("远程映射端口") }
                            Entry { objectName: "modelRemotePort"; Layout.preferredWidth: 170; Layout.fillWidth: false; text: page.ui.data.remote_port; enabled: !page.ui.data.active; inputMethodHints: Qt.ImhDigitsOnly; onTextEdited: bridge.setField("remote_port", text) }
                        }
                    }
                    RowLayout {
                        visible: page.info.transport === "fixed"
                        Layout.fillWidth: true
                        Caption { text: page.ui.data.cfReady ? page.ui.data.cfHostname : page.ui.tr("先在设置中绑定固定域名。") }
                        Action { text: page.ui.tr("配置域名"); quiet: true; onClicked: page.ui.settingsOpen = true }
                    }
                    Caption { text: page.info.notice; color: page.ui.accent; visible: page.info.notice.length > 0 }
                    RowLayout {
                        Layout.fillWidth: true
                        Action {
                            objectName: "startModelShareButton"
                            text: page.ui.tr("开始分享 ♪"); filled: true
                            Layout.fillWidth: true
                            enabled: !!page.service.verified && !page.ui.data.active && !page.ui.data.cfBusy && !page.info.scanBusy
                            onClicked: page.share.startShare()
                        }
                        Action { objectName: "stopModelShareButton"; text: page.ui.tr("停止分享"); enabled: page.info.shareActive && !page.ui.data.stopping; onClicked: page.share.stopShare() }
                    }
                    Caption {
                        text: page.service.kind === "ollama"
                            ? page.ui.tr("Ollama 本地 API 不校验 Key。穿透会公开整个服务端口，请先配置访问控制。")
                            : page.ui.tr("穿透会公开此端口的所有 HTTP 路径。请先在模型服务中配置访问控制。")
                    }
                }
                Card {
                    color: page.ui.tonal
                    RowLayout {
                        Layout.fillWidth: true
                        Heading { text: page.ui.tr("客户端连接") }
                        Label { text: page.info.shareActive ? page.ui.tr("运行中") : page.ui.tr("待连接"); color: page.ui.muted; font.pixelSize: 12 }
                    }
                    Entry {
                        objectName: "modelBaseUrl"
                        text: page.info.shareBaseUrl
                        readOnly: true; font.family: "Consolas"; font.pixelSize: 13
                        placeholderText: "OpenAI Base URL · …/v1"
                        Accessible.name: "OpenAI Base URL"
                    }
                    Flow {
                        Layout.fillWidth: true; spacing: 6
                        Action { objectName: "copyModelBaseUrl"; text: page.ui.tr("复制 Base URL"); quiet: true; enabled: page.info.shareBaseUrl.length > 0; onClicked: page.share.copyBaseUrl() }
                        Action { text: page.ui.tr("复制模型 ID"); quiet: true; enabled: page.info.shareModels.length > 0; onClicked: page.share.copyModel() }
                        Action { objectName: "copyModelSnippet"; text: page.ui.tr("复制调用示例"); quiet: true; enabled: page.info.snippet.length > 0; onClicked: page.share.copySnippet() }
                    }
                }
            }
        }
        Item { Layout.preferredHeight: 18 }
    }
}
