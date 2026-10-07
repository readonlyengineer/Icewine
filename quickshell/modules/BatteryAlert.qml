import QtQuick
import Quickshell
import Quickshell.Services.UPower
import qs.config as Config
import "BatteryAlertModel.js" as BatteryAlertModel

Scope {
    id: root

    required property var session
    property var batteryDevice: UPower.displayDevice
    readonly property bool enabled: Quickshell.env("ICEWINE_BATTERY_ENABLED") === "true"
    readonly property var policy: ({ warnings: [Config.Settings.batteryLow,
        Config.Settings.batteryCritical, Config.Settings.batteryDanger],
        sleep: Config.Settings.batterySleep })
    property var alertState: BatteryAlertModel.initial()

    function sample() {
        const state = batteryDevice?.state
        return { present: batteryDevice?.isLaptopBattery ?? false,
            percentage: batteryDevice?.percentage * 100,
            discharging: state === UPowerDeviceState.Discharging
                || state === UPowerDeviceState.PendingDischarge }
    }

    function warn(level) {
        const low = level === policy.warnings[0]
        const title = low ? "Battery Low"
            : level === policy.warnings[1] ? "Battery Critical" : "Battery Danger"
        Quickshell.execDetached(["notify-send", "--app-name=Icewine", "--app-icon", "battery-low",
            "-u", low ? "normal" : "critical", title,
            `${Math.round(batteryDevice.percentage * 100)}% remaining`])
    }

    function check() {
        if (!alertState)
            return
        const result = BatteryAlertModel.update(alertState, sample(), policy, enabled)
        alertState = result.state
        if (result.cancelSleep)
            sleepDelay.stop()
        if (result.alert !== null)
            warn(result.alert)
        if (result.startSleep)
            sleepDelay.start()
    }

    onBatteryDeviceChanged: check()
    onEnabledChanged: check()
    onPolicyChanged: check()
    Component.onCompleted: {
        if (!BatteryAlertModel.validPolicy(policy))
            console.warn("Invalid Icewine battery thresholds; battery actions disabled")
        check()
    }
    Connections {
        target: root.batteryDevice
        function onPercentageChanged() { root.check() }
        function onStateChanged() { root.check() }
        function onIsLaptopBatteryChanged() { root.check() }
    }
    Timer {
        id: sleepDelay
        interval: 1000
        onTriggered: {
            const result = BatteryAlertModel.confirmSleep(root.alertState,
                root.sample(), root.policy, root.enabled)
            root.alertState = result.state
            if (result.dispatch && !root.session.requestSleep())
                console.warn("Suspend request already in progress")
        }
    }
}
