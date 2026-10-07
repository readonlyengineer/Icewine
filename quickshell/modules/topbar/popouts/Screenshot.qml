pragma ComponentBehavior: Bound

import QtQuick
import qs.icewine.theme as Theme

Item {
    id: root

    readonly property Item initialFocus: monitor
    readonly property bool clipboardOnly: clipboard.checked

    signal captureRequested(string mode)

    implicitHeight: clipboard.y + clipboard.height + 12

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
            onClicked: root.captureRequested("output")
        }
        ActionButton {
            width: (actions.width - 2 * actions.spacing) / 3
            text: "Region"
            onClicked: root.captureRequested("region")
        }
        ActionButton {
            width: (actions.width - 2 * actions.spacing) / 3
            text: "Window"
            onClicked: root.captureRequested("window")
        }
    }

    Toggle {
        id: clipboard
        x: 12
        y: actions.y + actions.implicitHeight + 12
        width: parent.width - 24
        text: "Clipboard only"
    }
}
