pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Services.Greetd
import qs.config as Config
import "WinterModel.js" as WinterModel

Scope {
    id: root

    readonly property var users: Config.Settings.users
    readonly property var sessions: Config.Settings.sessions
    property int userIndex: Math.max(0, users.findIndex(user => user.name === Config.Settings.defaultUser))
    property int sessionIndex: Math.max(0, sessions.indexOf(Config.Settings.defaultSession))
    property string password: ""
    property string prompt: "Password"
    property string message: Greetd.available ? "" : "Login service unavailable"
    property bool failed: !Greetd.available
    property bool busy: false
    property bool secretInput: true
    property string pendingResponse: ""
    property var keyboardHost: null
    property bool keyboardVisible: Qt.inputMethod.visible
    property real keyboardHeight: 0
    readonly property bool authenticationRequired: true
    readonly property string userLabel: users[userIndex]?.label ?? "Unknown"
    readonly property string sessionLabel: sessions[sessionIndex] ?? "Default"

    function nextUser() {
        userIndex = WinterModel.nextIndex(userIndex, users.length)
        reset()
    }

    function nextSession() {
        sessionIndex = WinterModel.nextIndex(sessionIndex, sessions.length)
    }

    function reset() {
        if (Greetd.state !== GreetdState.Inactive)
            Greetd.cancelSession()
        password = ""
        pendingResponse = ""
        prompt = "Password"
        message = ""
        failed = false
        busy = false
        secretInput = true
    }

    function submit() {
        if (busy)
            return
        const plan = WinterModel.submission(Greetd.available,
            Greetd.state === GreetdState.Inactive,
            Greetd.state === GreetdState.Authenticating,
            password, users[userIndex]?.name ?? "")
        if (!plan)
            return
        failed = false
        message = "Authenticating…"
        busy = true
        if (plan.action === "create") {
            pendingResponse = plan.response
            password = ""
            Greetd.createSession(plan.user)
        } else {
            Greetd.respond(plan.response)
            password = ""
        }
    }

    function toggleKeyboard(host) {
        if (keyboardVisible && keyboardHost === host) {
            Qt.inputMethod.hide()
        } else {
            keyboardHost = host
            Qt.inputMethod.show()
        }
    }

    function requestReboot() {
        Quickshell.execDetached(["systemctl", "reboot"])
    }

    function requestShutdown() {
        Quickshell.execDetached(["systemctl", "poweroff"])
    }

    Connections {
        target: Greetd

        function onAuthMessage(message, error, responseRequired, echoResponse) {
            const state = WinterModel.authenticationMessage(root.pendingResponse,
                message, error, responseRequired, echoResponse)
            root.prompt = state.prompt
            root.message = state.message
            root.failed = state.failed
            root.secretInput = state.secretInput
            root.busy = state.busy
            root.pendingResponse = state.pendingResponse
            if (state.response)
                Greetd.respond(state.response)
        }

        function onAuthFailure(message) {
            const state = WinterModel.authenticationFailure(message)
            root.password = ""
            root.prompt = state.prompt
            root.message = state.message
            root.failed = state.failed
            root.secretInput = state.secretInput
            root.busy = state.busy
            root.pendingResponse = state.pendingResponse
        }

        function onReadyToLaunch() {
            root.message = "Starting session…"
            Greetd.launch(WinterModel.sessionCommand(Config.Settings.sessionCommand,
                root.sessions, root.sessionIndex))
        }

        function onError(error) {
            root.message = error || "Login service error"
            root.failed = true
            root.busy = false
        }
    }
}
