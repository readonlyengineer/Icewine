pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io

Scope {
    id: root

    required property string monitorName
    property bool active: false
    property int value: 0
    property bool available: false
    property string error: ""
    property int pending: -1

    function setBrightness(value) {
        pending = Math.max(0, Math.min(100, Math.round(value)))
        root.value = pending
        debounce.restart()
    }

    function refresh() {
        if (process.running || monitorName.length === 0)
            return
        const command = ["icewine-monitor-brightness", monitorName]
        if (pending >= 0) {
            command.push(String(pending))
            pending = -1
        }
        process.command = command
        process.running = true
    }

    onMonitorNameChanged: {
        available = false
        pending = -1
        if (active) refresh()
    }
    onActiveChanged: if (active) refresh()

    Timer {
        id: debounce
        interval: 100
        onTriggered: root.refresh()
    }

    Timer {
        interval: 3000
        repeat: true
        running: root.active
        onTriggered: if (root.pending < 0) root.refresh()
    }

    Process {
        id: process
        stdout: StdioCollector { id: output }
        stderr: StdioCollector { id: errors }
        onExited: (exitCode, exitStatus) => {
            if (command[1] !== root.monitorName) {
                if (root.active) Qt.callLater(root.refresh)
                return
            }
            const text = output.text.trim()
            root.available = exitCode === 0 && exitStatus === 0
                && /^(0|[1-9][0-9]?|100)$/.test(text)
            root.error = root.available ? "" : "Brightness unavailable"
            if (root.available && root.pending < 0)
                root.value = Number(text)
            if (!root.available)
                console.warn("Brightness for " + root.monitorName + ": " + errors.text.trim())
            if (root.pending >= 0) Qt.callLater(root.refresh)
        }
    }
}
