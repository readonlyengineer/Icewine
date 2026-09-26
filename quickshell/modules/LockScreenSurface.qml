pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import qs.theme as Theme

Item {
    id: root

    required property var session

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
        readonly property string message: failed ? "Incorrect password" : ""
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
        function onPasswordChanged() {
            if (controller.password !== root.session.password)
                controller.password = root.session.password
        }
    }

    WinterScreen {
        anchors.fill: parent
        controller: controller
        palette: Theme.Palette
    }
}
