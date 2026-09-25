pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Bluetooth
import "StatusModel.js" as StatusModel
import qs.theme as Theme

Flickable {
    id: root

    readonly property Item initialFocus: adapterToggle
    readonly property var adapter: Bluetooth.defaultAdapter
    readonly property var allDevices: adapter ? adapter.devices.values : []
    readonly property var devices: adapter
        ? StatusModel.bluetoothDevices(allDevices)
        : []
    property var pairingDevice: null

    signal advancedRequested(string tool)

    function activate(device) {
        if (device.connected) {
            device.disconnect()
        } else if (device.paired || device.bonded) {
            device.connect()
        } else {
            pairingDevice = device
            device.pair()
        }
    }

    implicitHeight: contentHeight
    contentHeight: content.implicitHeight + 24
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    Connections {
        target: root.pairingDevice
        ignoreUnknownSignals: true

        function onPairedChanged() {
            if (root.pairingDevice?.paired) {
                root.pairingDevice.connect()
                root.pairingDevice = null
            }
        }
    }

    Column {
        id: content

        x: 12
        y: 12
        width: root.width - 24
        spacing: 7

        Text {
            text: "Bluetooth"
            color: Theme.Palette.info
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 15
            font.bold: true
        }

        Toggle {
            id: adapterToggle

            width: parent.width
            text: "Adapter"
            enabled: root.adapter !== null
            checked: root.adapter?.enabled ?? false
            onToggled: {
                if (root.adapter)
                    root.adapter.enabled = checked
            }
        }

        Toggle {
            width: parent.width
            text: "Discover devices"
            enabled: root.adapter?.enabled ?? false
            checked: root.adapter?.discovering ?? false
            onToggled: {
                if (root.adapter)
                    root.adapter.discovering = checked
            }
        }

        Text {
            text: root.adapter ? `${root.allDevices.length} devices available` : "No Bluetooth adapter"
            color: Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 10
        }

        Repeater {
            model: ScriptModel { values: root.devices }

            DeviceRow {
                required property var modelData

                width: content.width
                device: modelData
                onActivated: root.activate(modelData)
                onForgotten: modelData.forget()
            }
        }

        ActionButton {
            width: parent.width
            text: "Advanced · bluetui"
            onClicked: root.advancedRequested("bluetui")
        }
    }

    component DeviceRow: Rectangle {
        id: deviceRow

        required property var device
        readonly property bool loading: device.pairing
            || device.state === BluetoothDeviceState.Connecting
            || device.state === BluetoothDeviceState.Disconnecting
        signal activated()
        signal forgotten()

        height: 40
        activeFocusOnTab: true
        radius: 9
        color: device.connected ? Theme.Palette.selection
            : deviceHover.hovered ? Theme.Palette.surface : "transparent"
        opacity: loading ? 0.55 : 1
        border.width: activeFocus ? 1 : 0
        border.color: Theme.Palette.info

        Keys.onReturnPressed: deviceRow.activated()
        Keys.onEnterPressed: deviceRow.activated()
        Keys.onSpacePressed: deviceRow.activated()
        Keys.onDownPressed: deviceRow.nextItemInFocusChain(true).forceActiveFocus(Qt.TabFocusReason)
        Keys.onUpPressed: deviceRow.nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            text: deviceRow.device.icon.includes("head") ? "󰋋"
                : deviceRow.device.icon.includes("audio") ? "󰓃" : ""
            color: deviceRow.device.connected ? Theme.Palette.info : Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 13
        }

        Column {
            anchors.left: parent.left
            anchors.leftMargin: 34
            anchors.right: battery.left
            anchors.rightMargin: 7
            anchors.verticalCenter: parent.verticalCenter
            spacing: 0

            Text {
                width: parent.width
                text: deviceRow.device.name || deviceRow.device.deviceName || "Unknown device"
                color: deviceRow.device.connected ? Theme.Palette.info : Theme.Palette.foreground
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 11
                elide: Text.ElideRight
            }

            Text {
                width: parent.width
                visible: deviceRow.device.connected || deviceRow.loading
                text: deviceRow.loading ? "Working…" : "Connected"
                color: Theme.Palette.muted
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 8
                elide: Text.ElideRight
            }
        }

        Text {
            id: battery

            anchors.right: forget.left
            anchors.rightMargin: 7
            anchors.verticalCenter: parent.verticalCenter
            visible: deviceRow.device.connected && deviceRow.device.batteryAvailable
            text: `${Math.round(deviceRow.device.battery * 100)}%`
            color: deviceRow.device.battery < 0.2 ? Theme.Palette.error : Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 9
        }

        Text {
            id: forget

            anchors.right: parent.right
            anchors.rightMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            visible: deviceRow.device.bonded
            text: "󰆴"
            color: forgetHover.hovered ? Theme.Palette.error : Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 11

            HoverHandler { id: forgetHover; cursorShape: Qt.PointingHandCursor }
            TapHandler { onTapped: deviceRow.forgotten() }
        }

        HoverHandler { id: deviceHover; cursorShape: Qt.PointingHandCursor }

        MouseArea {
            anchors {
                top: parent.top
                bottom: parent.bottom
                left: parent.left
                right: forget.visible ? forget.left : parent.right
            }
            enabled: !deviceRow.loading
            cursorShape: Qt.PointingHandCursor
            onClicked: deviceRow.activated()
        }
    }
}
