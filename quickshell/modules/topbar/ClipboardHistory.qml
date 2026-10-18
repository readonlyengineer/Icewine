pragma ComponentBehavior: Bound

import Quickshell
import Quickshell.Io
import qs.config as Config

Scope {
    id: root
    property bool locked: false
    property var entries: []
    property string activeEntry: ""
    property var selection: null
    property string error: ""
    property bool available: false
    property bool busy: false
    property int serial: 0
    property int pending: 0
    signal loaded(int request)

    function request(action, id = "") {
        if (locked || !available || busy) return 0
        busy = true
        pending = ++serial
        error = ""
        backend.write(JSON.stringify({action: action, id: id, request: pending}) + "\n")
        return pending
    }

    function receive(line) {
        if (locked) return
        try {
            const state = JSON.parse(line)
            entries = state.entries
            activeEntry = state.active
            selection = state.selection
            error = state.error
            available = true
            if (pending && state.request === pending) {
                const completed = pending
                pending = 0
                busy = false
                if (state.loaded) loaded(completed)
            }
        } catch (error) {
            entries = []
            activeEntry = ""
            selection = null
            available = false
            busy = false
            pending = 0
            root.error = "Clipboard backend unavailable"
        }
    }

    property int expirySeconds: Config.Settings.clipboardExpiry
    function configureExpiry() {
        if (available && !locked)
            backend.write(JSON.stringify({action: "expiry", seconds: expirySeconds}) + "\n")
    }
    onExpirySecondsChanged: configureExpiry()
    onAvailableChanged: if (available) configureExpiry()

    onLockedChanged: if (locked) {
        entries = []
        activeEntry = ""
        selection = null
        available = false
        pending = 0
        busy = false
        error = ""
    }

    Process {
        id: backend
        command: ["icewine-clipboard"]
        running: !root.locked
        stdinEnabled: true
        stdout: SplitParser { onRead: line => root.receive(line) }
        onExited: {
            root.entries = []
            root.activeEntry = ""
            root.selection = null
            root.available = false
            root.busy = false
            root.pending = 0
            if (!root.locked) root.error = "Clipboard backend unavailable"
        }
    }
}
