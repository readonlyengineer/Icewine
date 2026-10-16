pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Networking
import "StatusModel.js" as StatusModel
import ".." as Bar
import qs.icewine.theme as Theme

FocusScope {
    id: root

    required property var metrics
    implicitHeight: Math.max(64 + 44 + Math.max(content.implicitHeight + 24, tailscale.implicitHeight),
        passwordNetwork ? passwordContent.implicitHeight + 36 : 0)
    clip: true

    readonly property Item initialFocus: passwordNetwork ? password : exchanging ? motionFocus
        : selectedCard === 0 ? networkCard.selector : tailscaleCard.selector
    property int selectedCard: 0
    property int frontCard: 0
    property int outgoingCard: 0
    property real progress: 0
    property bool exchanging: false
    readonly property bool available: visible && enabled && !passwordNetwork

    function selectCard(index) {
        if (!available) return
        if (selectedCard === index) {
            if (exchanging && root.activeFocus) motionFocus.forceActiveFocus()
            return
        }
        tailscale.closeMenus()
        if (root.activeFocus) motionFocus.forceActiveFocus()
        exchange.stop()
        if (!exchanging) {
            outgoingCard = frontCard
            progress = 0
        }
        selectedCard = index
        exchanging = true
        exchange.to = index === outgoingCard ? 0 : 1
        exchange.duration = 560 * Math.abs(exchange.to - progress)
        if (exchange.duration === 0) finishExchange()
        else exchange.start()
    }

    function finishExchange() {
        exchange.stop()
        frontCard = selectedCard
        exchanging = false
        progress = 0
        if (available && motionFocus.activeFocus) initialFocus.forceActiveFocus()
    }

    function inOutCubic(t) {
        return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
    }

    NumberAnimation {
        id: exchange
        target: root
        property: "progress"
        easing.type: Easing.Linear
        onFinished: root.finishExchange()
    }

    // A stationary keyboard target while either title may be clipped by the sweep.
    Item {
        id: motionFocus
        anchors.fill: parent
        property int activationKey: 0
        onActiveFocusChanged: if (!activeFocus) activationKey = 0
        Keys.onPressed: event => {
            if (![Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space].includes(event.key)) return
            event.accepted = true
            if (!event.isAutoRepeat) activationKey = event.key
        }
        Keys.onReleased: event => {
            if (event.isAutoRepeat || event.key !== activationKey) return
            event.accepted = true
            activationKey = 0
            root.selectCard(1 - root.selectedCard)
        }
    }
    Rectangle {
        anchors.fill: parent
        anchors.margins: 2
        z: 3
        visible: motionFocus.activeFocus
        radius: 12
        color: "transparent"
        border.width: 2
        border.color: Theme.Palette.secondary
    }

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
            wifiDevice.scannerEnabled = enabled && root.available && selectedCard === 0 && Networking.wifiEnabled
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

    onAvailableChanged: {
        setScanning(available)
        if (!available) {
            scanRestart.stop()
            tailscale.closeMenus()
            if (exchanging) finishExchange()
        }
    }
    onSelectedCardChanged: {
        setScanning(available)
        if (selectedCard !== 0) scanRestart.stop()
    }
    onWifiDeviceChanged: setScanning(visible)
    Component.onCompleted: setScanning(visible)
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
                    Qt.callLater(() => {
                        if (password.visible && password.enabled) password.forceActiveFocus()
                    })
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

    // Two real consumers share geometry locally; page/service ownership stays unchanged.
    component Card: Rectangle {
        id: card
        required property int index
        required property string title
        required property color titleColor
        property alias selector: heading
        default property alias contentData: body.data
        readonly property bool outgoing: index === root.outgoingCard
        readonly property real advance: root.inOutCubic(root.progress)
        readonly property real sweep: root.progress < 0.5 ? root.inOutCubic(root.progress * 2)
            : 1 - Math.pow(1 - (root.progress - 0.5) * 2, 3)
        width: Math.max(0, root.width - 34)
        height: Math.max(0, root.height - 64)
        x: 8 + (!root.exchanging ? (index === root.frontCard ? 18 : 0)
            : !outgoing ? 18 * advance
            : root.progress < 0.5 ? 18 + (-width - 30) * sweep : (-width - 12) * (1 - sweep))
        y: 8 + (!root.exchanging ? (index === root.frontCard ? 48 : 0)
            : !outgoing ? 48 * advance
            : root.progress < 0.5 ? 48 - 24 * sweep : 24 * (1 - sweep))
        // The outgoing card clears the clipped host before this handoff, also in reverse.
        z: !root.exchanging ? (index === root.frontCard ? 2 : 1)
            : outgoing === (root.progress < 0.5) ? 2 : 1
        radius: 12
        color: Theme.Palette.backgroundDark
        border.width: 1
        border.color: Theme.Palette.border
        clip: true
        enabled: !root.passwordNetwork
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onWheel: event => event.accepted = true
        }
        ActionButton {
            id: heading
            width: parent.width
            height: 44
            text: card.title
            checked: root.selectedCard === card.index
            focusPolicy: root.exchanging ? Qt.ClickFocus : Qt.StrongFocus
            Accessible.name: card.title + " card"
            Accessible.checkable: true
            Accessible.checked: checked
            font.pixelSize: 15
            font.bold: true
            onClicked: root.selectCard(card.index)
            background: Rectangle {
                radius: 12
                color: heading.hovered ? Theme.Palette.surface : Theme.Palette.backgroundDark
                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 4
                    visible: heading.activeFocus
                    radius: 8
                    color: "transparent"
                    border.width: 2
                    border.color: Theme.Palette.secondary
                }
            }
            contentItem: Text {
                text: heading.text
                color: card.titleColor
                font: heading.font
                leftPadding: 12
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
        }
        Item {
            id: body
            anchors { top: heading.bottom; bottom: parent.bottom; left: parent.left; right: parent.right }
            enabled: !root.exchanging && root.selectedCard === card.index
        }
    }

    Card {
        id: networkCard
        index: 0
        title: "Networking"
        titleColor: Theme.Palette.success
    Flickable {
        anchors.fill: parent
        contentHeight: content.implicitHeight + 24
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: content

            x: 12
            y: 12
            width: parent.width - 24
            spacing: 7

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

    }
    Card {
        id: tailscaleCard
        index: 1
        title: "Tailscale"
        titleColor: Theme.Palette.secondary
        Tailscale {
            id: tailscale
            anchors.fill: parent
            active: root.available && root.selectedCard === 1
        }
    }

    Rectangle {
        anchors.fill: parent
        z: 4
        visible: root.passwordNetwork !== null
        color: Theme.Palette.backgroundDark
        radius: 10
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onWheel: event => event.accepted = true
        }

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
