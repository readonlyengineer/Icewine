pragma ComponentBehavior: Bound

import QtQuick
import "Metrics.js" as Metrics
import qs.icewine.theme as Theme

Rectangle {
    id: root

    required property string title
    required property var history
    required property double now
    property var labels: [title]
    property var colours: [Theme.Palette.secondary, Theme.Palette.tertiary]
    property string unit: "%"
    property string details: ""
    property real minimumMaximum: unit === "B/s" ? 1024 : 100
    readonly property var latest: history.length && now - history[history.length - 1].time < 3000
        ? history[history.length - 1].values : []
    readonly property real minimum: {
        let minimum = 0
        for (const point of history) {
            if (point.time < now - 120000) continue
            for (const value of point.values)
                if (value !== null) minimum = Math.min(minimum, value)
        }
        return minimum
    }
    readonly property real maximum: {
        let maximum = minimumMaximum
        for (const point of history) {
            if (point.time < now - 120000) continue
            for (const value of point.values)
                if (value !== null) maximum = Math.max(maximum, value)
        }
        return maximum
    }

    implicitHeight: 154
    radius: 9
    color: Theme.Palette.surface
    onHistoryChanged: graph.requestPaint()
    onNowChanged: graph.requestPaint()
    onMaximumChanged: graph.requestPaint()
    onMinimumChanged: graph.requestPaint()
    onColoursChanged: graph.requestPaint()

    Text {
        x: 10; y: 8
        width: parent.width - detailsText.width - (root.details ? 30 : 20)
        text: root.title
        elide: Text.ElideRight
        color: Theme.Palette.foreground
        font.family: "JetBrainsMono Nerd Font"
        font.pixelSize: 11
        font.bold: true
    }

    Text {
        id: detailsText
        anchors.right: parent.right
        anchors.rightMargin: 10
        y: 9
        text: root.details
        color: Theme.Palette.muted
        font.family: "JetBrainsMono Nerd Font"
        font.pixelSize: 9
    }

    Row {
        x: 10; y: 27
        spacing: 14
        Repeater {
            model: root.labels
            Text {
                required property int index
                required property string modelData
                text: `${modelData} ${Metrics.format(root.latest[index], root.unit)}`
                color: root.colours[index % root.colours.length]
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 9
            }
        }
    }

    Text {
        anchors.right: parent.right
        anchors.rightMargin: 10
        y: 44
        text: (root.minimum < 0 ? Metrics.format(root.minimum, root.unit) + " – " : "")
            + Metrics.format(root.maximum, root.unit)
        color: Theme.Palette.foregroundDark
        font.family: "JetBrainsMono Nerd Font"
        font.pixelSize: 8
    }

    Canvas {
        id: graph
        x: 10; y: 58
        width: parent.width - 20
        height: 72
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.strokeStyle = Theme.Palette.alpha(Theme.Palette.muted, 0.2)
            ctx.lineWidth = 1
            ctx.beginPath()
            for (let i = 0; i <= 2; ++i) {
                const y = 1 + (height - 2) * i / 2
                ctx.moveTo(0, y); ctx.lineTo(width, y)
            }
            ctx.stroke()
            for (let series = 0; series < root.labels.length; ++series) {
                ctx.strokeStyle = root.colours[series % root.colours.length]
                ctx.lineWidth = 1.5
                ctx.beginPath()
                let lastTime = 0
                for (const point of root.history) {
                    const value = point.values[series]
                    if (point.time < root.now - 120000 || value === null || value === undefined) {
                        lastTime = 0
                        continue
                    }
                    const x = Math.min(width, (point.time - root.now + 120000) / 120000 * width)
                    const y = height - 1 - (value - root.minimum) / (root.maximum - root.minimum) * (height - 2)
                    if (!lastTime || point.time - lastTime > 3000) ctx.moveTo(x, y)
                    else ctx.lineTo(x, y)
                    lastTime = point.time
                }
                ctx.stroke()
            }
        }
    }

    Text {
        x: 10; y: 136
        text: "−2 min"
        color: Theme.Palette.foregroundDark
        font.family: "JetBrainsMono Nerd Font"
        font.pixelSize: 8
    }
    Text {
        anchors.right: parent.right
        anchors.rightMargin: 10
        y: 136
        text: "now"
        color: Theme.Palette.foregroundDark
        font.family: "JetBrainsMono Nerd Font"
        font.pixelSize: 8
    }
}
