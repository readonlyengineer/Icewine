pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io

QtObject {
    id: adapter

    signal configReloaded()
    signal monitorsChanged()
    signal navigationRequested()

    readonly property string activeWindowAddress: Hyprland.activeToplevel?.address ?? ""
    readonly property var toplevels: Hyprland.toplevels.values

    readonly property string activeWindowClass: String(
        Hyprland.activeToplevel?.wayland?.appId
            ?? Hyprland.activeToplevel?.lastIpcObject?.class
            ?? "")

    function activateWindow(address) {
        const window = Hyprland.toplevels.values.find(window => window.address === address)
        window?.wayland?.activate()
    }

    function toggleFullscreen() {
        Quickshell.execDetached([
            "hyprctl",
            "eval",
            "require(\"modules.WindowPolicy\").toggle_fullscreen()"
        ])
    }

    function dispatch(request) {
        Hyprland.dispatch(request)
    }

    // Ponytail: hover protection has IPC latency; a compositor-side hit test
    // would close that gap. Reload Hyprland to restore binds after a shell crash.
    property var pendingMouseSuppression: null

    function supress_mouse_binds(enabled) {
        pendingMouseSuppression = enabled
        flushMouseSuppression()
    }

    function flushMouseSuppression() {
        if (mouseSuppression.running || pendingMouseSuppression === null)
            return
        mouseSuppression.command = ["hyprctl", "eval",
            'require("modules.Binds").supress_mouse_binds('
                + (pendingMouseSuppression ? "true" : "false") + ')']
        pendingMouseSuppression = null
        mouseSuppression.running = true
    }

    property Process mouseSuppression: Process {
        // Coalesce hover changes while one update is in flight.
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0 || exitStatus !== 0)
                console.warn("Failed to update Super+mouse bindings; reload Hyprland to restore them")
            Qt.callLater(adapter.flushMouseSuppression)
        }
    }

    function monitorFor(screen) {
        return Hyprland.monitorFor(screen)
    }

    function focusedWorkspaceId() {
        return Hyprland.focusedWorkspace?.id
            ?? Hyprland.focusedMonitor?.activeWorkspace?.id
            ?? 0
    }

    function workspaceForId(id) {
        return Hyprland.workspaces.values.find(workspace => workspace.id === id) ?? null
    }

    function toplevelsForWorkspace(id) {
        return workspaceForId(id)?.toplevels?.values ?? []
    }

    function activateWorkspace(id) {
        navigationRequested()
        const workspace = workspaceForId(id)
        if (workspace) {
            workspace.activate()
            return
        }
        Hyprland.dispatch(Hyprland.usingLua
            ? "hl.dsp.focus({ workspace = " + JSON.stringify(String(id)) + " })"
            : "workspace " + id)
    }

    function getMonitors() {
        var monitors = []
        var values = Hyprland.monitors.values
        for (var i = 0; i < values.length; i++) {
            var monitor = values[i]
            var ipc = monitor.lastIpcObject || {}
            var rawWidth = Number(ipc.width || monitor.width || 0)
            var rawHeight = Number(ipc.height || monitor.height || 0)
            var swapsAxes = Number(ipc.transform || 0) % 2 === 1

            monitors.push({
                id: monitor.id,
                name: monitor.name,
                description: monitor.description,
                // Hyprland transforms 1, 3, 5 and 7 rotate the output axes.
                width: swapsAxes ? rawHeight : rawWidth,
                height: swapsAxes ? rawWidth : rawHeight,
                x: Number(ipc.x || monitor.x || 0),
                y: Number(ipc.y || monitor.y || 0),
                scale: Number(ipc.scale || monitor.scale || 1),
                refreshHz: Number(ipc.refreshRate || 0),
                focused: monitor.focused
            })
        }

        return monitors
    }

    property Connections hyprlandEvents: Connections {
        target: Hyprland

        function onRawEvent(event) {
            const name = event.name
            if (/^monitor(added|removed)/.test(name)) {
                adapter.monitorsChanged()
            } else if (name === "configreloaded") {
                adapter.configReloaded()
                adapter.monitorsChanged()
            }
        }
    }
}
