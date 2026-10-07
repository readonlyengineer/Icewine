pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Networking
import "StatusModel.js" as StatusModel
import ".." as Bar
import qs.icewine.theme as Theme

Item {
    id: root

    required property var metrics
    implicitHeight: Math.max(content.implicitHeight + 24,
        passwordNetwork ? passwordContent.implicitHeight + 36 : 0)

    readonly property Item initialFocus: wifiToggle
    readonly property var wifiDevice: Networking.devices.values.find(device =>
        device.type === DeviceType.Wifi) ?? null
    readonly property var wifiNetworks: wifiDevice
        ? StatusModel.wifiNetworks(wifiDevice.networks.values)
        : []
    readonly property var wiredDevices: Networking.devices.values.filter(device =>
        device.type === DeviceType.Wired)
    property var connectingNetwork: null
    property var passwordNetwork: null
    property string errorMessage: ""

    function setScanning(enabled) {
        if (wifiDevice)
            wifiDevice.scannerEnabled = enabled && Networking.wifiEnabled
    }

    function connectNetwork(network) {
        if (!network || network.stateChanging)
            return
        errorMessage = ""
        if (network.connected) {
            network.disconnect()
        } else {
            connectingNetwork = network
            network.connect()
        }
    }

    function submitPassword() {
        if (!passwordNetwork || password.text.length === 0) {
            errorMessage = "Enter a network password"
            return
        }
        connectingNetwork = passwordNetwork
        passwordNetwork.connectWithPsk(password.text)
    }

    function closePassword() {
        password.text = ""
        passwordNetwork = null
        connectingNetwork = null
        errorMessage = ""
    }

    onVisibleChanged: setScanning(visible)
    onWifiDeviceChanged: setScanning(visible)
    Component.onCompleted: setScanning(true)
    Component.onDestruction: setScanning(false)

    Connections {
        target: Networking

        function onWifiEnabledChanged() {
            if (!Networking.wifiEnabled) {
                root.closePassword()
            }
            root.setScanning(root.visible)
        }
    }

    Connections {
        target: root.connectingNetwork
        ignoreUnknownSignals: true

        function onConnectionFailed(reason) {
            if (reason === ConnectionFailReason.NoSecrets) {
                if (root.passwordNetwork === root.connectingNetwork
                        && password.text.length > 0) {
                    root.errorMessage = "Authentication failed"
                } else {
                    root.passwordNetwork = root.connectingNetwork
                    root.errorMessage = ""
                    Qt.callLater(() => password.forceActiveFocus())
                }
            } else {
                root.errorMessage = `Connection failed: ${ConnectionFailReason.toString(reason)}`
            }
        }

        function onConnectedChanged() {
            if (root.connectingNetwork?.connected) {
                root.closePassword()
            }
        }
    }

    Timer {
        id: scanRestart

        interval: 120
        onTriggered: root.setScanning(true)
    }

    Flickable {
        anchors.fill: parent
        contentHeight: content.implicitHeight + 24
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: content

            x: 12
            y: 12
            width: root.width - 24
            spacing: 7

            Text {
                text: "Network"
                color: Theme.Palette.success
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 15
                font.bold: true
            }

            Bar.HistoryGraph {
                width: parent.width
                title: "Wi-Fi / Ethernet"
                labels: ["↓", "↑"]
                unit: "B/s"
                history: root.metrics.network.history
                now: root.metrics.now
            }

            Toggle {
                id: wifiToggle

                width: parent.width
                text: "Wi-Fi"
                enabled: Networking.wifiHardwareEnabled
                checked: Networking.wifiEnabled
                onToggled: Networking.wifiEnabled = checked
            }

            Text {
                text: root.wifiDevice
                    ? `${root.wifiDevice.networks.values.length} networks available`
                    : "No Wi-Fi adapter"
                color: Theme.Palette.muted
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 10
            }

            Repeater {
                model: ScriptModel { values: root.wifiNetworks }

                NetworkRow {
                    required property var modelData

                    width: content.width
                    network: modelData
                    onActivated: root.connectNetwork(modelData)
                }
            }

            ActionButton {
                width: parent.width
                text: "󰑓  Rescan networks"
                enabled: Networking.wifiEnabled && root.wifiDevice !== null
                onClicked: {
                    root.setScanning(false)
                    scanRestart.restart()
                }
            }

            Text {
                visible: root.wiredDevices.length > 0
                topPadding: 6
                text: "Wired"
                color: Theme.Palette.muted
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 10
            }

            Repeater {
                model: ScriptModel { values: root.wiredDevices }

                WiredRow {
                    required property var modelData

                    width: content.width
                    device: modelData
                }
            }

            Text {
                visible: root.errorMessage.length > 0
                width: parent.width
                text: root.errorMessage
                color: Theme.Palette.error
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 10
                wrapMode: Text.Wrap
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: root.passwordNetwork !== null
        color: Theme.Palette.backgroundDark
        radius: 10

        Column {
            id: passwordContent
            anchors {
                left: parent.left
                right: parent.right
                verticalCenter: parent.verticalCenter
                margins: 18
            }
            spacing: 10

            Text {
                width: parent.width
                text: `Connect to ${root.passwordNetwork?.name ?? "network"}`
                color: Theme.Palette.success
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 14
                font.bold: true
                elide: Text.ElideRight
            }

            Rectangle {
                width: parent.width
                height: 38
                radius: 9
                color: Theme.Palette.surface

                TextInput {
                    id: password

                    anchors.fill: parent
                    anchors.margins: 10
                    color: Theme.Palette.foreground
                    selectionColor: Theme.Palette.primaryDark
                    selectedTextColor: Theme.Palette.foreground
                    font.family: "JetBrainsMono Nerd Font"
                    font.pixelSize: 11
                    echoMode: TextInput.Password
                    clip: true

                    Keys.onReturnPressed: root.submitPassword()
                    Keys.onEnterPressed: root.submitPassword()
                    Keys.onEscapePressed: root.closePassword()

                    Text {
                        anchors.fill: parent
                        visible: password.text.length === 0
                        text: "Password"
                        color: Theme.Palette.muted
                        font: password.font
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }

            Text {
                visible: root.errorMessage.length > 0
                width: parent.width
                text: root.errorMessage
                color: Theme.Palette.error
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 10
                wrapMode: Text.Wrap
            }

            ActionButton {
                width: parent.width
                text: "Connect"
                onClicked: root.submitPassword()
            }

            ActionButton {
                width: parent.width
                text: "Cancel"
                onClicked: root.closePassword()
            }
        }
    }

    component NetworkRow: Rectangle {
        id: networkRow

        required property var network
        signal activated()

        readonly property bool secure: network.security !== WifiSecurityType.Open
            && network.security !== WifiSecurityType.Unknown

        height: 36
        activeFocusOnTab: true
        radius: 9
        color: network.connected ? Theme.Palette.selection
            : networkHover.hovered ? Theme.Palette.surface : "transparent"
        opacity: network.stateChanging ? 0.55 : 1
        border.width: activeFocus ? 1 : 0
        border.color: Theme.Palette.secondary

        Keys.onReturnPressed: networkRow.activated()
        Keys.onEnterPressed: networkRow.activated()
        Keys.onSpacePressed: networkRow.activated()
        Keys.onDownPressed: networkRow.nextItemInFocusChain(true).forceActiveFocus(Qt.TabFocusReason)
        Keys.onUpPressed: networkRow.nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            text: StatusModel.wifiIcon(networkRow.network.signalStrength)
            color: networkRow.network.connected ? Theme.Palette.secondary : Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 13
        }

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 34
            anchors.right: status.left
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            text: networkRow.network.name
            color: networkRow.network.connected ? Theme.Palette.secondary : Theme.Palette.foreground
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 11
            elide: Text.ElideRight
        }

        Text {
            id: status

            anchors.right: parent.right
            anchors.rightMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            text: networkRow.network.stateChanging ? "…"
                : networkRow.network.connected ? "󰌾"
                : networkRow.secure ? "" : ""
            color: networkRow.network.connected ? Theme.Palette.secondary : Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 11
        }

        HoverHandler { id: networkHover; cursorShape: Qt.PointingHandCursor }
        TapHandler {
            enabled: !networkRow.network.stateChanging && Networking.wifiEnabled
            onTapped: networkRow.activated()
        }
    }

    component WiredRow: Rectangle {
        id: wiredRow

        required property var device
        readonly property var network: device.network

        height: 36
        activeFocusOnTab: true
        radius: 9
        color: network?.connected ? Theme.Palette.selection
            : wiredHover.hovered ? Theme.Palette.surface : "transparent"
        border.width: activeFocus ? 1 : 0
        border.color: Theme.Palette.secondary

        Keys.onReturnPressed: root.connectNetwork(wiredRow.network)
        Keys.onEnterPressed: root.connectNetwork(wiredRow.network)
        Keys.onSpacePressed: root.connectNetwork(wiredRow.network)
        Keys.onDownPressed: wiredRow.nextItemInFocusChain(true).forceActiveFocus(Qt.TabFocusReason)
        Keys.onUpPressed: wiredRow.nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            text: "󰈀"
            color: wiredRow.network?.connected ? Theme.Palette.secondary : Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 12
        }

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 34
            anchors.right: speed.left
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            text: wiredRow.network?.name || wiredRow.device.name
            color: Theme.Palette.foreground
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 11
            elide: Text.ElideRight
        }

        Text {
            id: speed

            anchors.right: parent.right
            anchors.rightMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            text: wiredRow.device.hasLink ? `${wiredRow.device.linkSpeed} Mb/s` : "unplugged"
            color: Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 9
        }

        HoverHandler { id: wiredHover; cursorShape: Qt.PointingHandCursor }
        TapHandler {
            enabled: wiredRow.network !== null && !wiredRow.network.stateChanging
            onTapped: root.connectNetwork(wiredRow.network)
        }
    }
}
