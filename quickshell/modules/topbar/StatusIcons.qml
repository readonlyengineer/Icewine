pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Bluetooth
import Quickshell.Networking
import Quickshell.Services.Notifications
import Quickshell.Services.Pipewire
import Quickshell.Services.UPower
import "popouts/StatusModel.js" as StatusModel
import qs.theme as Theme

Rectangle {
    id: root

    required property var notificationService
    readonly property var sink: Pipewire.defaultAudioSink
    readonly property int volume: sink?.audio ? Math.round(sink.audio.volume * 100) : 0
    readonly property bool muted: !sink?.audio || sink.audio.muted
    readonly property bool networkConnected: Networking.devices.values.some(device => device.connected)
    readonly property bool wifiConnected: Networking.devices.values.some(device => device.type === DeviceType.Wifi && device.connected)
    readonly property var bluetoothAdapter: Bluetooth.defaultAdapter
    readonly property int bluetoothConnections: Bluetooth.devices.values.filter(device => device.connected).length
    readonly property var battery: UPower.displayDevice
    readonly property bool batteryCharging: battery?.state === UPowerDeviceState.Charging
        || battery?.state === UPowerDeviceState.PendingCharge
    readonly property color notificationColour: notificationService.count === 0
        ? Theme.Palette.muted
        : notificationService.highestUrgency === NotificationUrgency.Critical
            ? Theme.Palette.error
            : notificationService.highestUrgency === NotificationUrgency.Normal
                ? Theme.Palette.secondary : Theme.Palette.muted
    property string hoveredPage: ""

    signal popoutActivated(string page)

    function adjustVolume(delta) {
        if (!sink?.audio || delta === 0)
            return
        sink.audio.volume = StatusModel.adjustedVolume(sink.audio.volume, delta)
        sink.audio.muted = false
    }

    function updateHoveredPage(position) {
        const point = root.mapToItem(statusRow, position.x, position.y)
        const page = StatusModel.pageAt(statusRow.children, point.x, point.y)
        if (page === hoveredPage)
            return
        hoveredPage = page
    }

    implicitWidth: statusRow.implicitWidth + 9
    implicitHeight: 29
    radius: height / 2
    color: Theme.Palette.alpha(Theme.Palette.surface, 0.92)
    border.color: Theme.Palette.alpha(Theme.Palette.secondary, 0.45)
    border.width: 1

    PwObjectTracker {
        objects: root.sink ? [root.sink] : []
    }

    Row {
        id: statusRow

        anchors.centerIn: parent
        spacing: 2

        StatusButton {
            page: "audio"
            icon: root.muted ? "󰝟" : root.volume < 34 ? "" : root.volume < 67 ? "" : ""
            colour: Theme.Palette.tertiary
            onActivated: root.popoutActivated("audio")
            onScrolled: delta => root.adjustVolume(delta)
        }

        StatusButton {
            page: "performance"
            icon: "󰓅"
            colour: Theme.Palette.caution
            onActivated: root.popoutActivated("performance")
        }

        StatusButton {
            page: "screenshot"
            icon: "󰄀"
            colour: Theme.Palette.secondary
            onActivated: root.popoutActivated("screenshot")
        }

        StatusButton {
            page: "network"
            icon: root.wifiConnected ? "" : root.networkConnected ? "" : "󰯡"
            colour: root.networkConnected ? Theme.Palette.success : Theme.Palette.muted
            onActivated: root.popoutActivated("network")
        }

        StatusButton {
            page: "bluetooth"
            visible: root.bluetoothAdapter !== null
            icon: root.bluetoothConnections > 0 ? "󰂰" : root.bluetoothAdapter?.enabled ? "" : "󰂲"
            colour: root.bluetoothAdapter?.enabled ? Theme.Palette.info : Theme.Palette.muted
            onActivated: root.popoutActivated("bluetooth")
        }

        StatusButton {
            page: "notifications"
            icon: root.notificationService.doNotDisturb ? "󰂛"
                : root.notificationService.count > 0 ? "󰂚" : "󰂜"
            colour: root.notificationColour
            badge: root.notificationService.count > 9 ? "9+"
                : root.notificationService.count > 0
                    ? String(root.notificationService.count) : ""
            pulseToken: root.notificationService.pulseToken
            onActivated: root.popoutActivated("notifications")
        }

        StatusButton {
            page: "battery"
            // Power controls are also needed on desktops without a battery.
            icon: root.battery?.isLaptopBattery
                ? StatusModel.batteryIcon(root.battery?.percentage ?? 0, root.batteryCharging) : "󰐥"
            label: root.battery?.isLaptopBattery
                ? `${Math.round((root.battery?.percentage ?? 0) * 100)}%` : ""
            colour: root.battery?.isLaptopBattery && (root.battery?.percentage ?? 1) < 0.15
                ? Theme.Palette.error
                : root.batteryCharging ? Theme.Palette.success : Theme.Palette.primary
            onActivated: root.popoutActivated("battery")
        }
    }

    HoverHandler {
        id: groupHover

        onPointChanged: root.updateHoveredPage(point.position)
        onHoveredChanged: {
            if (hovered)
                root.updateHoveredPage(point.position)
            else
                root.hoveredPage = ""
        }
    }

    component StatusButton: Item {
        id: statusButton

        required property string page
        required property string icon
        required property color colour
        property string label: ""
        property string badge: ""
        property int pulseToken: 0

        signal activated()
        signal scrolled(real delta)

        implicitWidth: Math.max(badge.length > 0 ? 25 : 21, statusContent.implicitWidth + 8)
        implicitHeight: 22

        onPulseTokenChanged: {
            if (pulseToken > 0)
                pulse.restart()
        }

        Rectangle {
            id: pulseRing

            anchors.fill: parent
            radius: height / 2
            color: "transparent"
            border.width: 1
            border.color: statusButton.colour
            opacity: 0
        }

        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: statusHover.hovered ? Theme.Palette.selection : "transparent"

            Behavior on color {
                ColorAnimation { duration: 120 }
            }
        }

        Row {
            id: statusContent

            anchors.centerIn: parent
            spacing: 3

            Text {
                text: statusButton.icon
                color: statusButton.colour
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 13
            }

            Text {
                visible: statusButton.label.length > 0
                anchors.verticalCenter: parent.verticalCenter
                text: statusButton.label
                color: statusButton.colour
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 9
                font.bold: true
            }
        }

        Rectangle {
            visible: statusButton.badge.length > 0
            anchors {
                top: parent.top
                right: parent.right
            }
            width: Math.max(9, badgeText.implicitWidth + 3)
            height: 9
            radius: height / 2
            color: statusButton.colour

            Text {
                id: badgeText

                anchors.centerIn: parent
                text: statusButton.badge
                color: Theme.Palette.backgroundDark
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 6
                font.bold: true
            }
        }

        SequentialAnimation {
            id: pulse

            loops: 2

            PropertyAction {
                target: pulseRing
                property: "opacity"
                value: 0.75
            }

            PropertyAction {
                target: pulseRing
                property: "scale"
                value: 0.7
            }

            ParallelAnimation {
                NumberAnimation {
                    target: pulseRing
                    property: "opacity"
                    to: 0
                    duration: 260
                }

                NumberAnimation {
                    target: pulseRing
                    property: "scale"
                    to: 1.35
                    duration: 260
                    easing.type: Easing.OutCubic
                }
            }
        }

        HoverHandler {
            id: statusHover
            cursorShape: Qt.PointingHandCursor
        }

        TapHandler {
            onTapped: statusButton.activated()
        }

        WheelHandler {
            onWheel: event => statusButton.scrolled(event.angleDelta.y)
        }
    }
}
