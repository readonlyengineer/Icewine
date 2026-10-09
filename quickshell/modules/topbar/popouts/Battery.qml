pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as Controls
import Quickshell.Services.UPower
import "StatusModel.js" as StatusModel
import qs.icewine.theme as Theme

Flickable {
    id: root

    required property var powerState
    required property var session
    required property var brightness
    readonly property Item initialFocus: lockButton

    property var batteryDevice: UPower.displayDevice
    readonly property var battery: batteryDevice
    readonly property bool batteryPresent: battery?.isLaptopBattery ?? false
    readonly property int percentage: Math.round((battery?.percentage ?? 0) * 100)
    readonly property bool charging: battery?.state === UPowerDeviceState.Charging
        || battery?.state === UPowerDeviceState.PendingCharge
    readonly property bool discharging: battery?.state === UPowerDeviceState.Discharging
        || battery?.state === UPowerDeviceState.PendingDischarge
    readonly property bool full: battery?.state === UPowerDeviceState.FullyCharged
    readonly property real rate: Math.abs(battery?.changeRate ?? 0)
    readonly property string duration: StatusModel.formatDuration(charging
        ? battery?.timeToFull ?? 0 : discharging ? battery?.timeToEmpty ?? 0 : 0)
    readonly property string stateText: battery?.state === UPowerDeviceState.PendingCharge
        ? "Waiting to charge" : battery?.state === UPowerDeviceState.PendingDischarge
            ? "Waiting to discharge" : charging ? "Charging"
                : discharging ? "Discharging" : full ? "Fully charged" : "Battery"
    readonly property color stateColour: percentage < 15 && discharging
        ? Theme.Palette.error : charging || full ? Theme.Palette.success : Theme.Palette.primary
    readonly property string degradation: PowerProfiles.degradationReason
            === PerformanceDegradationReason.HighTemperature
        ? "High temperature" : PowerProfiles.degradationReason
            === PerformanceDegradationReason.LapDetected
            ? "Lap detected" : ""

    implicitHeight: contentHeight
    contentHeight: content.implicitHeight + 24
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    Column {
        id: content

        x: 12
        y: 12
        width: root.width - 24
        spacing: 8

        Text {
            text: "Power"
            color: root.stateColour
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 15
            font.bold: true
        }

        Row {
            width: parent.width
            spacing: 6

            ActionButton {
                id: lockButton
                width: (parent.width - parent.spacing) / 2
                text: "󰍁"
                Accessible.role: Accessible.Button
                Accessible.name: "Lock"
                Controls.ToolTip.visible: hovered || activeFocus
                Controls.ToolTip.text: "Lock"
                onClicked: root.session.requestLock()
            }

            ActionButton {
                width: (parent.width - parent.spacing) / 2
                text: "󰒲"
                Accessible.role: Accessible.Button
                Accessible.name: "Sleep"
                Controls.ToolTip.visible: hovered || activeFocus
                Controls.ToolTip.text: "Sleep"
                onClicked: root.session.requestSleep()
            }
        }

        Row {
            width: parent.width
            spacing: 6

            ActionButton {
                width: (parent.width - parent.spacing) / 2
                text: "󰑐"
                Accessible.role: Accessible.Button
                Accessible.name: "Reboot"
                Controls.ToolTip.visible: hovered || activeFocus
                Controls.ToolTip.text: "Reboot"
                onClicked: root.session.requestReboot()
            }

            ActionButton {
                width: (parent.width - parent.spacing) / 2
                text: "󰐥"
                Accessible.role: Accessible.Button
                Accessible.name: "Shutdown"
                Controls.ToolTip.visible: hovered || activeFocus
                Controls.ToolTip.text: "Shutdown"
                onClicked: root.session.requestShutdown()
            }
        }

        Toggle {
            id: keepAwake
            width: parent.width
            text: "Keep awake"
            checked: root.powerState.keepAwake
            onToggled: root.powerState.keepAwake = checked
        }

        Rectangle {
            visible: root.batteryPresent
            width: parent.width
            height: 98
            radius: 10
            color: Theme.Palette.surface

            Text {
                id: batteryIcon

                anchors {
                    left: parent.left
                    leftMargin: 15
                    verticalCenter: parent.verticalCenter
                }
                text: StatusModel.batteryIcon(root.battery?.percentage ?? 0, root.charging)
                color: root.stateColour
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 30
            }

            Column {
                anchors {
                    left: batteryIcon.right
                    right: parent.right
                    leftMargin: 15
                    rightMargin: 14
                    verticalCenter: parent.verticalCenter
                }
                spacing: 5

                Text {
                    text: `${root.percentage}%  ·  ${root.stateText}`
                    color: Theme.Palette.foreground
                    font.family: "JetBrainsMono Nerd Font"
                    font.pixelSize: 13
                    font.bold: true
                }

                Text {
                    text: root.full ? "Fully charged"
                        : root.duration.length > 0
                            ? `${root.duration} ${root.charging ? "until full" : "remaining"}`
                            : root.charging || root.discharging
                                ? "Calculating time remaining…" : "Not charging"
                    color: Theme.Palette.muted
                    font.family: "JetBrainsMono Nerd Font"
                    font.pixelSize: 10
                }

                Rectangle {
                    width: parent.width
                    height: 7
                    radius: height / 2
                    color: Theme.Palette.backgroundDark

                    Rectangle {
                        width: parent.width * Math.max(0, Math.min(1,
                            root.battery?.percentage ?? 0))
                        height: parent.height
                        radius: height / 2
                        color: root.stateColour

                        Behavior on width {
                            NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
                        }
                    }
                }
            }
        }

        Text {
            visible: root.batteryPresent
            text: root.rate > 0.05
                ? `${root.charging ? "Charging" : root.discharging ? "Discharging" : "Power"} at ${root.rate.toFixed(1)} W`
                : "Power rate unavailable"
            color: root.rate > 0.05 ? Theme.Palette.foreground : Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 11
        }

        SectionLabel {
            visible: root.brightness.available
            text: `Display · ${root.brightness.monitorName}`
        }

        Text {
            visible: root.brightness.available
            text: `Brightness  ${root.brightness.value}%`
            color: Theme.Palette.foreground
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 11
        }

        Slider {
            id: brightnessSlider
            visible: root.brightness.available
            width: parent.width
            enabled: root.brightness.available
            from: 0
            to: 100
            stepSize: 1
            value: root.brightness.value
            onMoved: root.brightness.setBrightness(value)
        }

        SectionLabel { text: "Power profile" }

        Row {
            width: parent.width
            spacing: 6

            ActionButton {
                width: (parent.width - parent.spacing * 2) / 3
                text: `${PowerProfiles.profile === PowerProfile.PowerSaver ? "●" : "○"} Saver`
                onClicked: PowerProfiles.profile = PowerProfile.PowerSaver
            }

            ActionButton {
                width: (parent.width - parent.spacing * 2) / 3
                text: `${PowerProfiles.profile === PowerProfile.Balanced ? "●" : "○"} Balanced`
                onClicked: PowerProfiles.profile = PowerProfile.Balanced
            }

            ActionButton {
                width: (parent.width - parent.spacing * 2) / 3
                enabled: PowerProfiles.hasPerformanceProfile
                text: `${PowerProfiles.profile === PowerProfile.Performance ? "●" : "○"} Performance`
                onClicked: PowerProfiles.profile = PowerProfile.Performance
            }
        }

        Text {
            visible: root.degradation.length > 0
            width: parent.width
            text: `Performance limited · ${root.degradation}`
            color: Theme.Palette.error
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 10
            wrapMode: Text.Wrap
        }

        SectionLabel {
            id: batteryConditionLabel

            visible: root.batteryPresent && (root.battery?.healthSupported
                || (root.battery?.energyCapacity ?? 0) > 0
            )
            text: "Battery condition"
        }

        Text {
            visible: batteryConditionLabel.visible
            width: parent.width
            text: [
                root.battery?.healthSupported
                    ? `Health ${Math.round(root.battery.healthPercentage)}%` : "",
                (root.battery?.energyCapacity ?? 0) > 0
                    ? `${root.battery.energyCapacity.toFixed(1)} Wh full` : ""
            ].filter(value => value.length > 0).join("  ·  ")
            color: Theme.Palette.foreground
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 11
        }

    }

    component SectionLabel: Text {
        topPadding: 5
        color: Theme.Palette.muted
        font.family: "JetBrainsMono Nerd Font"
        font.pixelSize: 10
    }
}
