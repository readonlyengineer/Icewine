pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import qs.icewine.theme as Theme
import "Wallpaper.js" as Wallpaper

FocusScope {
    id: root
    focus: true
    Keys.forwardTo: !controller.busy && controller.authenticationRequired
        && (root.Window.window?.activeFocusItem === root || screen.neutralFocus)
        ? [screen.passwordInput] : []

    required property var session
    readonly property string dataHome: Quickshell.env("XDG_DATA_HOME")
        || (Quickshell.env("HOME") + "/.local/share")
    property bool overrideAvailable: true
    property bool selectionAvailable: true
    property string wallpaperRevision: String(Date.now())

    QtObject {
        id: controller
        readonly property int userCount: 1
        readonly property int sessionCount: 0
        readonly property string userLabel: Quickshell.env("USER") || "User"
        readonly property bool canReboot: true
        readonly property bool canShutdown: true
        readonly property string sessionLabel: ""
        property string password: root.session.password
        readonly property bool authenticationRequired: root.session.authenticationRequired
        readonly property bool busy: root.session.authenticating
        readonly property bool failed: root.session.failed
        readonly property bool secretInput: true
        readonly property string prompt: "Password"
        readonly property string message: busy ? "Authenticating…" : failed ? "Incorrect password" : ""
        readonly property var keyboardHost: root.session.keyboardHost
        readonly property bool keyboardVisible: root.session.keyboardVisible
        readonly property real keyboardHeight: root.session.keyboardHeight

        function nextUser() {}
        function nextSession() {}
        function submit() { root.session.submit() }
        function requestReboot() { root.session.requestReboot() }
        function requestShutdown() { root.session.requestShutdown() }
        function toggleKeyboard(host) { root.session.toggleKeyboard(host) }

        onPasswordChanged: {
            if (root.session.password !== password)
                root.session.password = password
        }
    }

    Connections {
        target: root.session
        function onLockedChanged() {
            if (root.session.locked) {
                root.overrideAvailable = true
                root.selectionAvailable = true
                root.wallpaperRevision = String(Date.now())
            }
        }
        function onWallpaperRevisionChanged() {
            root.overrideAvailable = true
            root.selectionAvailable = true
            root.wallpaperRevision = root.session.wallpaperRevision
        }
        function onPasswordChanged() {
            if (controller.password !== root.session.password)
                controller.password = root.session.password
        }
    }

    AuthScreen {
        id: screen
        anchors.fill: parent
        controller: controller
        restorePasswordFocus: true
        palette: Theme.Palette
        backdropSource: Wallpaper.authSource(root.dataHome, root.overrideAvailable,
            root.selectionAvailable, root.wallpaperRevision)
        onBackdropFailed: source => Qt.callLater(() => {
            if (String(source) !== String(screen.backdropSource)) return
            if (root.overrideAvailable) root.overrideAvailable = false
            else if (root.selectionAvailable) root.selectionAvailable = false
        })
    }
}
