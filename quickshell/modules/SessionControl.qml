pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.VirtualKeyboard
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pam
import Quickshell.Wayland
import "SessionModel.js" as SessionModel

Scope {
    id: root

    required property bool authenticationRequired

    property alias locked: sessionLock.locked
    property alias lockRequested: lockState.requested
    property string password: ""
    property bool authenticating: false
    property bool failed: false
    // A user service without a session ID uses logind's primary display session.
    // For simultaneous graphical sessions, supply an explicit XDG_SESSION_ID.
    readonly property string logindSessionId: Quickshell.env("XDG_SESSION_ID") || "auto"
    property string logindSessionPath: ""
    property var keyboardHost: null
    readonly property bool keyboardVisible: Qt.inputMethod.visible
    property real keyboardHeight: keyboard.height

    function toggleKeyboard(host) {
        if (keyboardVisible && keyboardHost === host) {
            Qt.inputMethod.hide()
        } else {
            keyboardHost = host
            Qt.inputMethod.show()
        }
    }

    function lockFromLogind() {
        if (lockRequested || sessionLock.locked)
            return
        lockRequested = true
        password = ""
        failed = false
        // Record intent before acquisition so a later client can recover it.
        if (logindSessionPath !== "")
            writeLockHint()
        else
            lockState.acquired = true
    }

    function writeLockHint() {
        if (logindSessionPath === "" || lockHint.running)
            return
        lockHint.value = lockRequested
        lockHint.command = ["gdbus", "call", "--system", "--dest", "org.freedesktop.login1",
            "--object-path", logindSessionPath,
            "--method", "org.freedesktop.login1.Session.SetLockedHint", String(lockHint.value)]
        lockHint.running = true
    }

    function restoreLock(output) {
        if (String(output).trim() === "(<true>,)") {
            lockRequested = true
            lockState.acquired = true
        }
        // A false or malformed hint never unlocks an acquired lock or bypasses PAM.
        if (lockRequested)
            writeLockHint()
    }

    function requestLock() {
        lockFromLogind()
        Quickshell.execDetached(["loginctl", "lock-session", logindSessionId])
    }

    function finishLockHint(exitCode, exitStatus) {
        if (exitCode !== 0 || exitStatus !== 0)
            console.warn("Cannot record lock intent in logind; client restart recovery is unavailable")
        if (lockRequested && lockHint.value)
            lockState.acquired = true
        // Serialise requests arriving during the previous D-Bus call.
        if (lockHint.value !== lockRequested)
            writeLockHint()
    }

    function requestSleep() {
        if (sleep.running)
            return false
        sleep.running = true
        return true
    }

    function reportSleepFailure(exitCode, exitStatus, message) {
        if (exitCode === 0 && exitStatus === 0)
            return
        const reason = message.trim() || "Suspend is unavailable"
        console.warn("Suspend failed: " + reason)
        Quickshell.execDetached(["notify-send", "--app-name=Icewine", "-u", "critical",
            "--app-icon", "battery-low", "Suspend failed", reason])
    }

    function requestReboot() {
        Quickshell.execDetached(["systemctl", "reboot"])
    }

    function requestShutdown() {
        Quickshell.execDetached(["systemctl", "poweroff"])
    }

    function releaseLock(notifyLogind) {
        if (!sessionLock.locked)
            return
        password = ""
        failed = false
        lockRequested = false
        lockState.acquired = false
        writeLockHint()
        wakeDisplay()
        if (notifyLogind)
            Quickshell.execDetached(["loginctl", "unlock-session", logindSessionId])
    }

    function submit() {
        if (!authenticationRequired) {
            releaseLock(true)
            return
        }
        if (password === "" || authenticating)
            return
        authenticating = true
        pam.start()
    }

    function wakeDisplay() {
        Quickshell.execDetached([
            "hyprctl", "dispatch", "hl.dsp.dpms({ action = \"enable\" })"
        ])
    }

    function handleLogind(line) {
        var event = SessionModel.logindEvent(line, logindSessionPath)
        if (event === "lock" || event === "sleep") {
            lockFromLogind()
        } else if (event === "resume") {
            wakeDisplay()
        }
    }

    Process {
        id: sleep
        command: ["systemctl", "suspend"]
        stderr: StdioCollector { id: sleepErrors }
        onExited: (exitCode, exitStatus) => root.reportSleepFailure(exitCode, exitStatus,
            sleepErrors.text)
    }

    PamContext {
        id: pam
        config: "icewine"

        onPamMessage: {
            if (responseRequired)
                respond(root.password)
        }
        onCompleted: result => {
            root.authenticating = false
            if (result === PamResult.Success) {
                root.releaseLock(true)
            } else {
                root.password = ""
                root.failed = true
            }
        }
    }

    // Explicit native reload order: restore the target before transferring the lock.
    Scope {
        reloadableId: "sessionLockLifecycle"
        PersistentProperties {
            id: lockState
            property bool requested: false
            property bool acquired: false
        }

        WlSessionLock {
            id: sessionLock
            locked: lockState.acquired

            // secure confirms compositor acquisition, not authentication UI readiness.
            onSecureChanged: if (locked && !secure) console.warn("Session lock is awaiting compositor acquisition")

            WlSessionLockSurface {
                color: "#000000"

                LockScreenSurface {
                    anchors.fill: parent
                    session: root
                }
            }
        }
    }

    InputPanel {
        id: keyboard
        parent: root.keyboardHost
        width: parent?.width ?? 0
        y: (parent?.height ?? 0) - height
        z: 100
        visible: active && parent !== null
    }

    Process {
        id: logindSession
        command: ["gdbus", "call", "--system", "--dest", "org.freedesktop.login1",
            "--object-path", "/org/freedesktop/login1",
            "--method", "org.freedesktop.login1.Manager.GetSession", root.logindSessionId]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                root.logindSessionPath = SessionModel.sessionPath(this.text)
                if (root.logindSessionPath !== "")
                    lockedHint.running = true
            }
        }
        onExited: {
            if (root.logindSessionPath === "") {
                console.warn("Cannot resolve logind session; ignoring session lock/unlock signals")
                logindReconnect.restart()
            }
        }
    }

    Process {
        id: lockedHint
        command: ["gdbus", "call", "--system", "--dest", "org.freedesktop.login1",
            "--object-path", root.logindSessionPath, "--method", "org.freedesktop.DBus.Properties.Get",
            "org.freedesktop.login1.Session", "LockedHint"]
        stdout: StdioCollector { onStreamFinished: root.restoreLock(this.text) }
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0 || exitStatus !== 0)
                console.warn("Cannot read lock intent from logind; client restart recovery is unavailable")
        }
    }

    Process {
        id: lockHint
        property bool value: false
        onExited: (exitCode, exitStatus) => root.finishLockHint(exitCode, exitStatus)
    }

    Process {
        id: logindEvents
        command: ["gdbus", "monitor", "--system", "--dest", "org.freedesktop.login1"]
        running: true
        stdout: SplitParser { onRead: data => root.handleLogind(data) }
        onExited: {
            root.logindSessionPath = ""
            logindReconnect.restart()
        }
    }

    Timer {
        id: logindReconnect
        interval: 1000
        onTriggered: {
            logindSession.running = true
            logindEvents.running = true
        }
    }

    IpcHandler {
        target: "session"
        function lock(): string { root.requestLock(); return "requested" }
        function refreshIcons(): void {
            if (!root.lockRequested && !root.locked)
                Quickshell.reload(false)
        }
        function status(): string {
            return JSON.stringify({ requested: root.lockRequested, locked: root.locked, secure: sessionLock.secure,
                authenticationRequired: root.authenticationRequired })
        }
    }
}
