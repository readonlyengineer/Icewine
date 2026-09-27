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
    readonly property bool delayed: delay.checked
    readonly property bool saveClipboard: clipboard.checked
    readonly property bool savePictures: pictures.checked

    signal captureRequested(string mode, string target)

    implicitHeight: options.y + options.implicitHeight + 12

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
        enabled: root.saveClipboard || root.savePictures
        spacing: 6

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
        enabled: root.saveClipboard || root.savePictures
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

    Column {
        id: options
        x: 12
        y: (actions.visible ? actions.y + actions.implicitHeight
            : selectorList.y + selectorList.height) + 12
        width: parent.width - 24
        spacing: 6

        Toggle {
            id: delay
            width: parent.width
            text: "3-second delay"
        }
        Toggle {
            id: clipboard
            width: parent.width
            text: "Save to clipboard"
            checked: true
        }
        Toggle {
            id: pictures
            width: parent.width
            text: "Save to Pictures"
            checked: true
        }
    }
}
