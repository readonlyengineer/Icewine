pragma Singleton
import QtQml
import Quickshell

QtObject {
    readonly property bool authenticationRequired: Quickshell.env("ICEWINE_AUTHENTICATION_REQUIRED") !== "false"
    readonly property int batteryLow: 20
    readonly property int batteryCritical: 10
    readonly property int batteryDanger: 5
    readonly property int batterySleep: 3
}
