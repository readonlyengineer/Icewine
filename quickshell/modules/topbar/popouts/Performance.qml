pragma ComponentBehavior: Bound

import QtQuick
import ".." as Bar
import "../Metrics.js" as Metrics
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
            details: root.metrics.cpuTemperature
                ? `${root.metrics.cpuTemperature.label} ${Metrics.format(root.metrics.cpuTemperature.current, "°C")}`
                : "Temperature —"
            history: root.metrics.cpu.history
            now: root.metrics.now
        }

        Bar.HistoryGraph {
            width: parent.width
            title: "RAM usage"
            labels: ["RAM"]
            colours: [Theme.Palette.tertiary]
            details: root.metrics.memory.current
                ? `${root.metrics.memory.current.usedGiB.toFixed(1)} / ${root.metrics.memory.current.totalGiB.toFixed(1)} GiB`
                : "— / — GiB"
            history: root.metrics.memory.history
            now: root.metrics.now
        }

        Repeater {
            model: root.metrics.gpus
            Column {
                required property var modelData
                width: content.width
                Bar.HistoryGraph {
                    visible: modelData.usage !== null
                    width: parent.width
                    title: modelData.title
                    labels: ["Usage"]
                    details: modelData.temperature
                        ? `${modelData.temperature.label} ${Metrics.format(modelData.temperature.current, "°C")}`
                        : "Temperature —"
                    history: modelData.usage?.history ?? []
                    now: root.metrics.now
                }
                Rectangle {
                    visible: modelData.usage === null
                    width: parent.width
                    height: 54
                    radius: 9
                    color: Theme.Palette.surface
                    Text {
                        x: 10; y: 8
                        text: modelData.title
                        color: Theme.Palette.foreground
                        font.family: "JetBrainsMono Nerd Font"
                        font.pixelSize: 11
                        font.bold: true
                    }
                    Text {
                        x: 10; y: 30
                        text: `Usage —  ·  ${modelData.temperature?.label ?? "Temperature"} ${Metrics.format(modelData.temperature?.current, "°C")}`
                        color: Theme.Palette.muted
                        font.family: "JetBrainsMono Nerd Font"
                        font.pixelSize: 9
                    }
                }
            }
        }

        Text {
            visible: root.metrics.gpus.length === 0
            text: "GPU · Unavailable"
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
