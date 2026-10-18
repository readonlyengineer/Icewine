pragma ComponentBehavior: Bound

import QtQuick
import qs.icewine.theme as Theme

Item {
    id: root
    property color accent: Theme.Palette.primary

    readonly property Item initialFocus: monitor
    signal captureRequested(var command)

    function capture(mode) {
        const command = mode === "monitor"
            ? ["flameshot", "screen", "--edit"] : ["flameshot", "gui"]
        if (delay.checked) command.push("--delay", "3000")
        root.captureRequested(command)
    }

    implicitHeight: annotationHint.y + annotationHint.height + 12

    Item {
        id: header
        anchors { top: parent.top; left: parent.left; right: parent.right; margins: 12 }
        height: 34

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "Screenshot"
            color: root.accent
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 15
            font.bold: true
        }
    }

    Row {
        id: actions
        anchors { top: header.bottom; left: parent.left; right: parent.right; margins: 12 }
        spacing: 6

        ActionButton {
            id: monitor
            width: (actions.width - actions.spacing) / 2
            text: "Monitor"
            onClicked: root.capture("monitor")
        }
        ActionButton {
            width: (actions.width - actions.spacing) / 2
            text: "Region"
            onClicked: root.capture("region")
        }
    }

    Toggle {
        id: delay
        x: 12
        y: actions.y + actions.implicitHeight + 12
        width: parent.width - 24
        text: "3-second delay"
    }

    Text {
        id: annotationHint
        x: 12
        y: delay.y + delay.height + 12
        width: parent.width - 24
        text: "Region: drag to select. Monitor: press Ctrl+A in Flameshot. Then edit, Save or Copy. Esc cancels."
        color: Theme.Palette.muted
        font.family: "JetBrainsMono Nerd Font"
        font.pixelSize: 11
        wrapMode: Text.WordWrap
    }
}
