pragma Singleton
import QtQml
import Quickshell

QtObject {
    readonly property bool authenticationRequired: Quickshell.env("ICEWINE_AUTHENTICATION_REQUIRED") !== "false"
}
