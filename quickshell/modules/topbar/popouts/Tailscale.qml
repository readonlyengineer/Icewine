pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as Controls
import Quickshell
import Quickshell.Io
import "TailscaleModel.js" as Model
import qs.icewine.theme as Theme

Flickable {
    id: root
    property bool active: false
    property var data: Model.empty("Loading…")
    property string error: ""
    property var request: null
    property int generation: 0
    property string confirming: ""
    readonly property bool busy: request !== null
    implicitHeight: content.implicitHeight + 24
    contentHeight: implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    function refresh() {
        if (!active || busy || process.running || exitPicker.popup.visible) return
        request = { generation: generation, kind: "status" }
        process.command = ["tailscale", "status", "--json"]
        deadline.restart()
        process.running = true
    }

    function selectExit(id) {
        if (!active || busy || process.running || confirming) return
        const command = Model.exitCommand(data, id)
        if (!command || id === data.selected) {
            syncPicker()
            return
        }
        error = ""
        // Capture stable identity and local profile before any asynchronous completion.
        request = { generation: generation, kind: "set", id: id, self: data.self }
        process.command = command
        deadline.restart()
        process.running = true
    }

    function finish(code, status, text, errors) {
        const completed = request
        if (!completed) return
        request = null
        deadline.stop()
        if (completed.kind === "status" && completed.generation !== generation) {
            if (active) Qt.callLater(root.refresh)
            return
        }
        if (code !== 0 || status !== 0) {
            const denied = /access denied|permission denied|not permitted/i.test(errors)
            error = denied ? "Permission denied. Ask the host administrator to configure a Tailscale operator, then retry."
                : completed.kind === "set" ? "Exit-node request failed or timed out. Refresh to check the current setting."
                : "Tailscale unavailable. Check the client and service, then refresh."
            if (completed.kind === "status") data = Model.empty("Unavailable")
            confirming = ""
        } else if (completed.kind === "set") {
            confirming = JSON.stringify({ id: completed.id, self: completed.self })
            if (active) Qt.callLater(root.refresh)
        } else {
            try {
                data = Model.decode(text)
                if (confirming) {
                    const selected = JSON.parse(confirming)
                    error = data.self !== selected.self ? "Tailscale profile changed. Check the current exit node."
                        : data.selected !== selected.id ? "Exit-node change not confirmed. Refresh and retry." : ""
                    confirming = ""
                }
            } catch (e) {
                data = Model.empty("Error")
                error = "Invalid Tailscale response. Refresh and retry."
                confirming = ""
            }
        }
        syncPicker()
    }

    function syncPicker() {
        if (!exitPicker || exitPicker.popup.visible) return
        exitPicker.model = data.exits
        exitPicker.currentIndex = Math.max(0, data.exits.findIndex(peer => peer.id === data.selected))
    }

    onActiveChanged: {
        ++generation
        if (active) refresh()
    }
    Component.onCompleted: if (active) refresh()
    onDataChanged: syncPicker()

    Timer { interval: 5000; repeat: true; running: root.active; onTriggered: root.refresh() }
    Timer {
        id: deadline
        interval: 8000
        onTriggered: {
            process.running = false
            root.finish(1, 1, "", "timeout")
        }
    }
    Process {
        id: process
        stdout: StdioCollector { id: output }
        stderr: StdioCollector { id: errors }
        onExited: (code, status) => root.finish(code, status, output.text, errors.text)
    }

    Column {
        id: content
        x: 12; y: 12; width: root.width - 24
        spacing: 7
        Text {
            textFormat: Text.PlainText
            width: parent.width
            text: root.busy ? (root.request.kind === "set" ? "Changing exit node…" : "Refreshing…") : root.data.label
            color: root.data.connected ? Theme.Palette.success : Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 13
            font.bold: true
            wrapMode: Text.Wrap
            Accessible.role: Accessible.StaticText
            Accessible.name: text
        }
        Text {
            textFormat: Text.PlainText
            text: "Exit node"
            color: Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 10
        }
        Controls.ComboBox {
            id: exitPicker
            width: parent.width
            implicitHeight: 36
            model: root.data.exits
            textRole: "name"
            valueRole: "id"
            enabled: Model.exitCommand(root.data, "") !== null && !root.busy && !root.confirming
            Accessible.name: "Exit node"
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 11
            onActivated: root.selectExit(currentValue)
            // Keep the choice model stable while the dropdown is open.
            Connections { target: exitPicker.popup; function onClosed() { root.syncPicker() } }
            background: Rectangle {
                radius: 9; color: Theme.Palette.surface
                border.width: exitPicker.activeFocus ? 1 : 0
                border.color: Theme.Palette.secondary
            }
            contentItem: Text {
                textFormat: Text.PlainText
                leftPadding: 10; rightPadding: 28
                text: exitPicker.displayText
                color: exitPicker.enabled ? Theme.Palette.foreground : Theme.Palette.muted
                font: exitPicker.font
                elide: Text.ElideRight
                verticalAlignment: Text.AlignVCenter
            }
            delegate: Controls.ItemDelegate {
                required property int index
                required property var modelData
                width: exitPicker.width
                text: modelData.name
                font: exitPicker.font
                enabled: Model.exitCommand(root.data, modelData.id) !== null
                highlighted: exitPicker.highlightedIndex === index
                contentItem: Text {
                    textFormat: Text.PlainText
                    text: parent.text; font: parent.font
                    color: Theme.Palette.foreground
                    elide: Text.ElideRight
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle { color: parent.highlighted ? Theme.Palette.selection : Theme.Palette.surface }
            }
            popup: Controls.Popup {
                y: exitPicker.height
                width: exitPicker.width
                padding: 1
                implicitHeight: Math.min(240, exitList.contentHeight + 2)
                background: Rectangle { color: Theme.Palette.surface; radius: 9 }
                contentItem: ListView {
                    id: exitList
                    clip: true
                    implicitHeight: contentHeight
                    model: exitPicker.popup.visible ? exitPicker.delegateModel : null
                    currentIndex: exitPicker.highlightedIndex
                    Controls.ScrollIndicator.vertical: Controls.ScrollIndicator {}
                }
            }
        }
        Text {
            textFormat: Text.PlainText
            width: parent.width
            visible: root.error.length > 0
            text: root.error
            color: Theme.Palette.error
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 10
            wrapMode: Text.Wrap
        }
        ActionButton {
            width: parent.width
            text: "Refresh Tailscale"
            enabled: !root.busy
            onClicked: { root.error = ""; root.refresh() }
        }
        Text {
            textFormat: Text.PlainText
            text: "Devices"
            topPadding: 6
            color: Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 10
        }
        Text {
            textFormat: Text.PlainText
            width: parent.width
            visible: root.data.peers.length === 0
            text: root.data.connected ? "No tailnet devices" : "Devices unavailable while disconnected"
            color: Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 10
            wrapMode: Text.Wrap
        }
        Repeater {
            model: root.data.peers
            Rectangle {
                required property var modelData
                width: content.width
                height: 48
                radius: 9
                color: Theme.Palette.surface
                Accessible.role: Accessible.StaticText
                Accessible.name: modelData.name + ", " + (modelData.expired ? "expired" : modelData.online ? "online" : "offline") + ", " + modelData.address
                Rectangle {
                    x: 10; y: 20; width: 7; height: 7; radius: 4
                    color: parent.modelData.online && !parent.modelData.expired ? Theme.Palette.success : Theme.Palette.muted
                }
                Column {
                    x: 28; y: 7; width: parent.width - 38
                    Text {
                        textFormat: Text.PlainText
                        width: parent.width
                        text: parent.parent.modelData.name
                        color: Theme.Palette.foreground
                        font.family: "JetBrainsMono Nerd Font"
                        font.pixelSize: 11
                        elide: Text.ElideRight
                    }
                    Text {
                        textFormat: Text.PlainText
                        width: parent.width
                        text: (parent.parent.modelData.address || "Address unavailable") + " · "
                            + (parent.parent.modelData.expired ? "expired" : parent.parent.modelData.online ? "online" : "offline")
                        color: Theme.Palette.muted
                        font.family: "JetBrainsMono Nerd Font"
                        font.pixelSize: 9
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }
}
