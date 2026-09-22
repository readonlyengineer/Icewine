pragma ComponentBehavior: Bound

import QtQuick
import ".." as Bar
import qs.theme as Theme

Flickable {
    id: root

    required property var metrics
    readonly property Item initialFocus: root
    signal advancedRequested(string tool)
    contentHeight: content.implicitHeight + 24
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    Keys.onDownPressed: contentY = Math.min(Math.max(0, contentHeight - height), contentY + 40)
    Keys.onUpPressed: contentY = Math.max(0, contentY - 40)
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Home) contentY = 0
        else if (event.key === Qt.Key_End) contentY = Math.max(0, contentHeight - height)
        else return
        event.accepted = true
    }

    Column {
        id: content
        x: 12; y: 12
        width: root.width - 24
        spacing: 7

        Text {
            text: "Performance"
            color: Theme.Palette.secondary
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 15
            font.bold: true
        }

        Bar.HistoryGraph {
            width: parent.width
            title: "CPU usage"
            labels: ["CPU"]
            history: root.metrics.cpu.history
            now: root.metrics.now
        }

        Bar.HistoryGraph {
            width: parent.width
            title: "RAM usage"
            labels: ["RAM"]
            colours: [Theme.Palette.tertiary]
            history: root.metrics.memory.history
            now: root.metrics.now
        }

        Repeater {
            model: root.metrics.sensors
            Bar.HistoryGraph {
                required property var modelData
                width: content.width
                title: modelData.title
                labels: [modelData.kind === "temperature" ? "Temp" : "GPU"]
                unit: modelData.kind === "temperature" ? "°C" : "%"
                colours: [modelData.kind === "temperature" ? Theme.Palette.warning : Theme.Palette.secondary]
                history: modelData.history
                now: root.metrics.now
            }
        }

        Text {
            visible: !root.metrics.sensors.some(sensor => sensor.kind === "gpu")
            text: "GPU usage · Unavailable"
            color: Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 10
        }

        Text {
            visible: !root.metrics.sensors.some(sensor => sensor.kind === "temperature")
            text: "Temperatures · Unavailable"
            color: Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 10
        }

        ActionButton {
            width: parent.width
            text: "Advanced · btop"
            onClicked: root.advancedRequested("btop")
            onActiveFocusChanged: if (activeFocus)
                root.contentY = Math.max(0, root.contentHeight - root.height)
        }
    }
}
