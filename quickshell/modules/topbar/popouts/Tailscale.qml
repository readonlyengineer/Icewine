pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
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
    property bool statusError: false
    property var request: null
    property int generation: 0
    property string confirming: ""
    property var menuData: ({devices: [], countries: []})
    readonly property bool busy: request !== null
    implicitHeight: content.implicitHeight + 24
    contentHeight: implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    function refresh() {
        if (!active || busy || process.running || exitPicker.visible) return
        request = { generation: generation, kind: "status" }
        process.command = ["tailscale", "status", "--json"]
        deadline.restart()
        process.running = true
    }

    function selectExit(id) {
        if (!active || confirming) return
        if (request?.kind === "status") {
            if (!request.next) request.next = { kind: "set", id: id, self: data.self }
            return
        }
        if (busy || process.running) return
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

    function toggleConnection() {
        if (!active || confirming || exitPicker.visible) return
        if (request?.kind === "status") {
            if (!request.next) request.next = { kind: "connection", self: data.self, state: data.state }
            return
        }
        if (busy || process.running) return
        const command = Model.connectionCommand(data)
        if (!command) return
        error = ""
        request = { generation: generation, kind: "connection", self: data.self,
            state: data.state === "Stopped" ? "Running" : "Stopped" }
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
        // Even a failed/timed-out command may have changed the daemon's state.
        if (completed.kind === "connection") confirming = JSON.stringify(completed)
        if (completed.timedOut || code !== 0 || status !== 0) {
            const denied = /access denied|permission denied|not permitted/i.test(errors)
            error = denied ? "Permission denied. Ask the host administrator to configure a Tailscale operator, then retry."
                : completed.kind === "connection" ? "Connection request failed or timed out. Checking the current state automatically."
                : completed.kind === "set" ? "Exit-node request failed or timed out. The current setting will be checked automatically."
                : "Tailscale unavailable. Check the client and service; status retries automatically."
            if (completed.kind === "status") {
                data = Model.empty("Unavailable")
                statusError = true
            }
            if (completed.kind !== "connection") confirming = ""
            else if (active) Qt.callLater(root.refresh)
        } else if (completed.kind === "connection") {
            if (active) Qt.callLater(root.refresh)
        } else if (completed.kind === "set") {
            confirming = JSON.stringify({ id: completed.id, self: completed.self })
            if (active) Qt.callLater(root.refresh)
        } else {
            try {
                const updated = Model.decode(text)
                // Retain delegates when only the headline/exit state changes.
                if (JSON.stringify(updated.peers) === JSON.stringify(data.peers)) updated.peers = data.peers
                if (JSON.stringify(updated) !== JSON.stringify(data)) data = updated
                if (statusError) error = ""
                statusError = false
                if (confirming) {
                    const selected = JSON.parse(confirming)
                    if (selected.kind === "connection") {
                        error = selected.self && data.self && data.self !== selected.self
                            ? "Tailscale profile changed. Check the current connection."
                            : data.state === "NeedsLogin" ? "Sign in with Tailscale; status retries automatically."
                            : data.state === "NeedsMachineAuth" ? "Device approval required. Ask the tailnet administrator; status retries automatically."
                            : data.state !== selected.state || (selected.state === "Running" && !data.connected)
                                ? (error || "Connection change not confirmed. Check the current state and retry.") : ""
                    } else {
                        error = data.self !== selected.self ? "Tailscale profile changed. Check the current exit node."
                            : data.selected !== selected.id ? "Exit-node change not confirmed. Check the current state and retry." : ""
                    }
                    confirming = ""
                }
            } catch (e) {
                data = Model.empty("Error")
                statusError = true
                error = "Invalid Tailscale response. Status retries automatically."
                confirming = ""
            }
        }
        syncPicker()
        // Keep read-time input responsive without overlapping processes or losing focus.
        const next = completed.next
        if (next && !statusError && active && completed.generation === generation) {
            if (next.self !== data.self || (next.kind === "connection" && next.state !== data.state))
                error = "Tailscale state changed. Check the current state and retry."
            else if (next.kind === "set") selectExit(next.id)
            else toggleConnection()
        }
    }

    function closeMenus() {
        // Native submenus are separate popups; close them before their parent card recedes.
        for (let i = 0; i < exitPicker.count; ++i) exitPicker.menuAt(i)?.close()
        exitPicker.close()
    }

    function syncPicker() {
        if (!exitPicker || exitPicker.visible) return
        const updated = Model.exitMenu(data)
        if (JSON.stringify(updated) !== JSON.stringify(menuData)) menuData = updated
    }

    onActiveChanged: {
        ++generation
        if (active) refresh()
        else closeMenus()
    }
    Component.onCompleted: if (active) refresh()
    onDataChanged: syncPicker()

    Timer { interval: 5000; repeat: true; running: root.active; onTriggered: root.refresh() }
    Timer {
        id: deadline
        interval: 8000
        onTriggered: {
            if (process.running) {
                // Keep the request locked until this process exits; no late result can finish a retry.
                root.request.timedOut = true
                process.signal(9)
            } else root.finish(1, 1, "", "timeout") // Includes a missing CLI that never started.
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
        RowLayout {
            width: parent.width
            spacing: 8
            Text {
                textFormat: Text.PlainText
                Layout.fillWidth: true
                text: root.data.selfName + " · " + (root.busy
                    ? (root.request.kind === "set" ? "Changing exit node…"
                        : root.request.kind === "connection" ? "Changing connection…" : root.data.label) : root.data.label)
                color: root.data.connected ? Theme.Palette.success : Theme.Palette.muted
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 13
                font.bold: true
                wrapMode: Text.Wrap
                Accessible.role: Accessible.StaticText
                Accessible.name: text
            }
            Toggle {
                id: connectionToggle
                Layout.preferredWidth: 44
                implicitHeight: 44
                checked: root.data.state === "Running"
                enabled: root.active && (!root.busy || root.request.kind === "status") && !root.confirming && !exitPicker.visible
                    && Model.connectionCommand(root.data) !== null
                Accessible.name: "Tailscale connection"
                Accessible.description: root.data.label
                // The switch shows daemon state, never an optimistic click result.
                checkable: false
                Accessible.checkable: true
                Accessible.checked: checked
                onClicked: root.toggleConnection()
            }
        }
        Text {
            textFormat: Text.PlainText
            text: "Exit node"
            color: Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 10
        }
        ActionButton {
            id: exitButton
            width: parent.width
            text: root.data.exits.find(peer => peer.id === root.data.selected)?.name ?? "None"
            enabled: Model.exitCommand(root.data, "") !== null && (!root.busy || root.request.kind === "status") && !root.confirming
            Accessible.name: "Exit node"
            onClicked: exitPicker.popup(exitButton, 0, exitButton.height)

            Controls.Menu {
                id: exitPicker
                width: root.width - 24
                palette.window: Theme.Palette.surface
                palette.base: Theme.Palette.surface
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 11
                palette.active.text: Theme.Palette.foreground
                palette.inactive.text: Theme.Palette.foreground
                palette.disabled.text: Theme.Palette.foregroundDark
                palette.windowText: Theme.Palette.foreground
                palette.light: Theme.Palette.selection
                palette.midlight: Theme.Palette.primaryDark
                palette.dark: Theme.Palette.border
                palette.buttonText: Theme.Palette.foreground
                palette.highlight: Theme.Palette.primary
                palette.highlightedText: Theme.Palette.highlightedText
                onClosed: root.syncPicker()
                Controls.MenuItem {
                    text: "None"
                    checkable: true
                    checked: root.data.selected === ""
                    onTriggered: root.selectExit("")
                }
                Instantiator {
                    id: deviceItems
                    model: root.menuData.devices
                    onObjectAdded: (index, object) => exitPicker.insertItem(index + 1, object)
                    onObjectRemoved: (index, object) => exitPicker.removeItem(object)
                    delegate: Controls.MenuItem {
                        required property var modelData
                        text: modelData.name
                        checkable: true
                        checked: root.data.selected === modelData.id
                        enabled: Model.exitCommand(root.data, modelData.id) !== null
                        onTriggered: root.selectExit(modelData.id)
                    }
                }
                Controls.MenuSeparator {
                    visible: deviceItems.count > 0 && countryMenus.count > 0
                    contentItem: Rectangle {
                        implicitWidth: 188
                        implicitHeight: 1
                        color: Theme.Palette.muted
                    }
                }
                Instantiator {
                    id: countryMenus
                    model: root.menuData.countries
                    onObjectAdded: (index, object) => exitPicker.insertMenu(index + deviceItems.count + 2, object)
                    onObjectRemoved: (index, object) => exitPicker.removeMenu(object)
                    delegate: Controls.Menu {
                        id: countryMenu
                        required property var modelData
                        title: modelData.name
                        enabled: modelData.cities.some(city => Model.exitCommand(root.data, city.id) !== null)
                        width: exitPicker.width
                        palette: exitPicker.palette
                        Instantiator {
                            model: countryMenu.modelData.cities
                            onObjectAdded: (index, object) => countryMenu.insertItem(index, object)
                            onObjectRemoved: (index, object) => countryMenu.removeItem(object)
                            delegate: Controls.MenuItem {
                                required property var modelData
                                text: modelData.name
                                checkable: true
                                checked: modelData.selected
                                enabled: Model.exitCommand(root.data, modelData.id) !== null
                                onTriggered: root.selectExit(modelData.id)
                            }
                        }
                    }
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
