pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import qs.icewine.theme as Theme

Item {
    id: root

    readonly property Item initialFocus: monitor
    signal captureRequested(var command)

    function capture(mode) {
        const command = ["hyprshot", "--freeze", "--mode", mode]
        if (mode === "output" && Quickshell.screens.length === 1)
            command.push("--mode", Quickshell.screens[0].name)
        if (clipboard.checked) command.push("--clipboard-only")
        if (delay.checked)
            command.unshift("sh", "-c", 'sleep 3 && exec "$@"', "icewine-screenshot")
        root.captureRequested(command)
    }

    implicitHeight: delay.y + delay.height + 12

    Item {
        id: header
        anchors { top: parent.top; left: parent.left; right: parent.right; margins: 12 }
        height: 34

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "Screenshot"
            color: Theme.Palette.secondary
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
            width: (actions.width - 2 * actions.spacing) / 3
            text: "Monitor"
            onClicked: root.capture("output")
        }
        ActionButton {
            width: (actions.width - 2 * actions.spacing) / 3
            text: "Region"
            onClicked: root.capture("region")
        }
        ActionButton {
            width: (actions.width - 2 * actions.spacing) / 3
            text: "Window"
            onClicked: root.capture("window")
        }
    }

    Toggle {
        id: clipboard
        x: 12
        y: actions.y + actions.implicitHeight + 12
        width: parent.width - 24
        text: "Clipboard only"
    }

    Toggle {
        id: delay
        x: 12
        y: clipboard.y + clipboard.height + 12
        width: parent.width - 24
        text: "3-second delay"
    }
}
