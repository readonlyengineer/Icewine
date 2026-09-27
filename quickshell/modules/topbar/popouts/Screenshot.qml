pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import "ScreenshotModel.js" as ScreenshotModel
import qs.theme as Theme

Item {
    id: root

    required property var compositor
    readonly property Item initialFocus: actions.visible ? monitor : selectorList
    readonly property var monitors: compositor.getMonitors()
    readonly property var windows: ScreenshotModel.windows(compositor.toplevels)
    property string view: "actions"

    signal captureRequested(string mode, string target)

    implicitHeight: header.height + 12 + (actions.visible ? actions.implicitHeight : selectorList.height) + 12

    function chooseMonitor() {
        if (monitors.length === 1)
            captureRequested("monitor", monitors[0].name)
        else
            view = "monitors"
    }

    function chooseWindow() {
        if (windows.length === 1)
            captureRequested("window", windows[0].stableId)
        else
            view = "windows"
    }

    Item {
        id: header
        anchors { top: parent.top; left: parent.left; right: parent.right; margins: 12 }
        height: 34

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.view === "actions" ? "Screenshot" : root.view === "monitors" ? "Choose monitor" : "Choose window"
            color: Theme.Palette.secondary
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 15
            font.bold: true
        }

        ActionButton {
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            visible: root.view !== "actions"
            width: 64
            height: 30
            text: "Back"
            onClicked: root.view = "actions"
        }
    }

    Row {
        id: actions
        anchors { top: header.bottom; left: parent.left; right: parent.right; margins: 12 }
        visible: root.view === "actions"
        spacing: 6
        implicitHeight: monitor.implicitHeight

        ActionButton {
            id: monitor
            width: (actions.width - actions.spacing * 2) / 3
            text: "Monitor"
            onClicked: root.chooseMonitor()
        }
        ActionButton {
            width: (actions.width - actions.spacing * 2) / 3
            text: "Region"
            onClicked: root.captureRequested("region", "")
        }
        ActionButton {
            width: (actions.width - actions.spacing * 2) / 3
            text: "Window"
            enabled: root.windows.length > 0
            onClicked: root.chooseWindow()
        }
    }

    ListView {
        id: selectorList
        anchors { top: header.bottom; left: parent.left; right: parent.right; margins: 12 }
        visible: root.view !== "actions"
        height: Math.min(contentHeight, 300)
        spacing: 6
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: ScriptModel { values: root.view === "monitors" ? root.monitors : root.windows }

        delegate: ActionButton {
            required property var modelData
            width: selectorList.width
            text: root.view === "monitors"
                ? `${modelData.name} · ${modelData.description || "Monitor"}`
                : `${modelData.title}${modelData.subtitle ? " · " + modelData.subtitle : ""}`
            onClicked: root.captureRequested(root.view === "monitors" ? "monitor" : "window",
                root.view === "monitors" ? modelData.name : modelData.stableId)
        }
    }
}
