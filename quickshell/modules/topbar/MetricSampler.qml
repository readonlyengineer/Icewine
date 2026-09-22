import QtQuick
import Quickshell
import Quickshell.Io
import "Metrics.js" as Metrics

Scope {
    id: root

    required property var clock
    required property string path
    required property string kind
    property var interfaces: []
    property var history: []
    property var previous: null
    property double previousTime: 0
    property bool busy: false

    function record(text) {
        const now = Date.now()
        const seconds = (now - previousTime) / 1000
        let values
        if (kind === "network") {
            const current = Metrics.network(text, interfaces)
            values = Metrics.networkRate(current, previous, seconds)
            previous = current
        } else if (kind === "cpu") {
            const current = Metrics.cpu(text)
            values = [seconds > 0 && seconds <= 3 ? Metrics.cpuUsage(current, previous) : null]
            previous = current
        } else if (kind === "memory") {
            values = [Metrics.memoryUsage(text)]
        } else {
            values = [Metrics.sensor(text, kind === "temperature")]
        }
        previousTime = now
        history = Metrics.append(history, now, values)
        busy = false
    }

    Connections {
        target: root.clock
        function onTick() {
            if (!root.busy) {
                root.busy = true
                file.reload()
            }
        }
    }

    FileView {
        id: file
        path: root.path
        printErrors: false
        onLoaded: root.record(text())
        onLoadFailed: {
            root.previous = null
            root.history = Metrics.append(root.history, Date.now(),
                root.kind === "network" ? [null, null] : [null])
            root.busy = false
        }
    }
}
