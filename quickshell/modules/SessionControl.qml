pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pam
import Quickshell.Wayland
import "SessionModel.js" as SessionModel

Scope {
    id: root

    required property bool authenticationRequired

    property alias locked: sessionLock.locked
    property string password: ""
    property bool authenticating: false
    property bool failed: false
    // A user service without a session ID uses logind's primary display session.
    // For simultaneous graphical sessions, supply an explicit XDG_SESSION_ID.
    readonly property string logindSessionId: Quickshell.env("XDG_SESSION_ID") || "auto"
    property string logindSessionPath: ""

    function lockFromLogind() {
        if (sessionLock.locked)
            return
        password = ""
        failed = false
        sessionLock.locked = true
    }

    function requestLock() {
        lockFromLogind()
        Quickshell.execDetached(["loginctl", "lock-session", logindSessionId])
    }

    function releaseLock(notifyLogind) {
        if (!sessionLock.locked)
            return
        password = ""
        failed = false
        sessionLock.locked = false
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
        } else if (event === "unlock") {
            releaseLock(false)
        } else if (event === "resume") {
            wakeDisplay()
        }
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

    WlSessionLock {
        id: sessionLock

        WlSessionLockSurface {
            color: "#171a21"

            LockScreenSurface {
                anchors.fill: parent
                session: root
            }
        }
    }

    Process {
        id: logindSession
        command: ["gdbus", "call", "--system", "--dest", "org.freedesktop.login1",
            "--object-path", "/org/freedesktop/login1",
            "--method", "org.freedesktop.login1.Manager.GetSession", root.logindSessionId]
        running: true
        stdout: StdioCollector {
            onStreamFinished: root.logindSessionPath = SessionModel.sessionPath(this.text)
        }
        onExited: {
            if (root.logindSessionPath === "") {
                console.warn("Cannot resolve logind session; ignoring session lock/unlock signals")
                logindReconnect.restart()
            }
        }
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
        function lock(): string { root.requestLock(); return "locked" }
        function status(): string {
            return JSON.stringify({ locked: root.locked, secure: sessionLock.secure,
                authenticationRequired: root.authenticationRequired })
        }
    }
}
