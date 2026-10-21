pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import "../modules/topbar/Layouts.js" as Layouts

QtObject {
    id: adapter

    signal configReloaded()
    signal monitorsChanged()
    signal navigationRequested()

    readonly property string activeWindowAddress: Hyprland.activeToplevel?.address ?? ""
    readonly property var toplevels: Hyprland.toplevels.values
    readonly property var fullscreenScreens: Hyprland.monitors.values.filter(monitor =>
        Hyprland.workspaces.values.some(workspace => workspace.hasFullscreen
            && workspace.monitor?.name === monitor.name
            && (workspace.id > 0 ? workspace.active
                : workspace.id < 0 && workspace.id === monitor.lastIpcObject?.specialWorkspace?.id)))
        .map(monitor => monitor.name)

    // Native refresh drops busy calls. Keep one follow-up until a snapshot
    // arrives; no event during that request can be lost permanently.
    property bool specialRefreshPending: false
    function flushSpecialRefresh() {
        if (!specialRefreshPending) return
        specialRefreshPending = false
        Qt.callLater(Hyprland.refreshMonitors)
    }
    property Instantiator monitorUpdates: Instantiator {
        model: Hyprland.monitors
        onObjectAdded: (_, object) => {
            // monitoraddedv2 creates placeholders before any snapshot completes.
            if (object.modelData.lastIpcObject?.name) adapter.flushSpecialRefresh()
        }
        delegate: Connections {
            required property var modelData
            target: modelData
            function onLastIpcObjectChanged() { adapter.flushSpecialRefresh() }
        }
    }

    readonly property string activeWindowClass: String(
        Hyprland.activeToplevel?.wayland?.appId
            ?? Hyprland.activeToplevel?.lastIpcObject?.class
            ?? "")

    function activateWindow(address) {
        const window = Hyprland.toplevels.values.find(window => window.address === address)
        window?.wayland?.activate()
    }

    function activateToplevel(window) {
        // Object identity prevents a closed window address from selecting its replacement.
        if (!Hyprland.toplevels.values.includes(window) || !window.wayland)
            return
        window.workspace?.activate()
        window.wayland.activate()
    }

    function toggleFullscreen() {
        Quickshell.execDetached([
            "hyprctl",
            "eval",
            "require(\"icewine.modules.WindowPolicy\").toggle_fullscreen()"
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
            'require("icewine.modules.Binds").supress_mouse_binds('
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

    // Ponytail: preview Tab arming/cancellation has IPC latency, like hover
    // protection above. Reload Hyprland after a shell crash; compositor-side
    // preview ownership would remove that timing/recovery ceiling.
    property var pendingPreviewTabs: null
    function setPreviewTabs(enabled) {
        pendingPreviewTabs = enabled
        flushPreviewTabs()
    }
    function flushPreviewTabs() {
        if (previewTabs.running || pendingPreviewTabs === null) return
        previewTabs.command = ["hyprctl", "eval",
            'require("icewine.modules.Binds").set_preview_tabs('
                + (pendingPreviewTabs ? "true" : "false") + ')']
        pendingPreviewTabs = null
        previewTabs.running = true
    }
    property Process previewTabs: Process {
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0 || exitStatus !== 0)
                console.warn("Failed to update preview Tab bindings; reload Hyprland to reset them")
            Qt.callLater(adapter.flushPreviewTabs)
        }
    }

    function monitorFor(screen) {
        // The native lookup does not track monitor model replacement in QML bindings.
        return Hyprland.monitors.values.find(monitor => monitor.name === screen?.name) ?? null
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

    function workspaceIdsForMonitor(monitor) {
        return Hyprland.workspaces.values
            .filter(workspace => workspace.monitor?.name === monitor?.name)
            .map(workspace => workspace.id)
            .sort((a, b) => a - b)
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

    readonly property int layoutWorkspaceId: focusedWorkspaceId()
    property bool layoutActive: false
    // A newer open/focus request invalidates a status result already in flight.
    property bool layoutRefreshPending: false
    property var layoutStatus: null
    property string layoutActionError: ""
    property int layoutErrorWorkspace: 0
    property string layoutErrorIdentity: ""
    readonly property string layoutError: layoutErrorWorkspace === layoutWorkspaceId
        && layoutStatus?.identity === layoutErrorIdentity ? layoutActionError : ""
    property string layoutUnavailable: ""
    property var nextLayoutRequest: null
    readonly property bool layoutPending: nextLayoutRequest !== null || (layoutProcess.running && layoutProcess.action)
    readonly property bool layoutAvailable: layoutStatus?.workspace === layoutWorkspaceId
        && layoutUnavailable === ""
    onLayoutWorkspaceIdChanged: refreshLayout()
    onLayoutActiveChanged: {
        layoutStatus = null
        layoutUnavailable = ""
        if (layoutActive) refreshLayout()
        else layoutRefreshPending = false
    }

    function refreshLayout() {
        if (!layoutActive || !layoutWorkspaceId) return
        if (layoutProcess.running) {
            layoutRefreshPending = true
            return
        }
        layoutRefreshPending = false
        layoutProcess.action = false
        layoutProcess.workspace = layoutWorkspaceId
        layoutProcess.command = ["hyprctl", "repl",
            'return require("icewine.modules.Layouts").status(' + layoutWorkspaceId + ')']
        layoutProcess.running = true
    }

    function selectLayout(layout) {
        requestLayoutChange(layout)
    }

    function selectAutofullscreen(enabled) {
        requestLayoutChange(enabled)
    }

    function requestLayoutChange(choice) {
        if (!layoutActive || !layoutAvailable || layoutPending) return
        try {
            // Capture before waiting for an in-flight status query or focus change.
            nextLayoutRequest = { workspace: layoutStatus.workspace, identity: layoutStatus.identity,
                command: Layouts.request(layoutStatus.workspace, layoutStatus.identity, choice) }
            layoutActionError = ""
            flushLayoutRequest()
        } catch (error) {
            layoutErrorWorkspace = layoutStatus.workspace
            layoutErrorIdentity = layoutStatus.identity
            layoutActionError = String(error)
        }
    }

    function flushLayoutRequest() {
        if (layoutProcess.running || nextLayoutRequest === null) return
        layoutProcess.command = nextLayoutRequest.command
        layoutProcess.workspace = nextLayoutRequest.workspace
        layoutProcess.identity = nextLayoutRequest.identity
        layoutProcess.action = true
        nextLayoutRequest = null
        layoutProcess.running = true
    }

    property Process layoutProcess: Process {
        property bool action: false
        property int workspace: 0
        property string identity: ""
        stdout: StdioCollector {}
        stderr: StdioCollector {}
        onExited: (exitCode, exitStatus) => {
            const output = stdout.text.trim()
            if (action) {
                if (exitCode !== 0 || exitStatus !== 0 || output !== "ok") {
                    adapter.layoutErrorWorkspace = workspace
                    adapter.layoutErrorIdentity = identity
                    adapter.layoutActionError = output || stderr.text.trim() || "Layout request failed"
                }
            } else {
                try {
                    if (exitCode !== 0 || exitStatus !== 0) throw new Error(stderr.text.trim() || "Hyprland unavailable")
                    const state = Layouts.status(output, workspace)
                    if (adapter.layoutActive && !adapter.layoutRefreshPending
                            && workspace === adapter.layoutWorkspaceId) {
                        adapter.layoutStatus = state
                        adapter.layoutUnavailable = ""
                    }
                } catch (error) {
                    if (adapter.layoutActive && !adapter.layoutRefreshPending
                            && workspace === adapter.layoutWorkspaceId) {
                        adapter.layoutStatus = null
                        adapter.layoutUnavailable = String(error)
                    }
                }
            }
            if (adapter.nextLayoutRequest !== null)
                Qt.callLater(adapter.flushLayoutRequest)
            else if (action || adapter.layoutRefreshPending || workspace !== adapter.layoutWorkspaceId)
                Qt.callLater(adapter.refreshLayout)
        }
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
            // qs 0.3.2 does not refresh its visible-special snapshot itself.
            if (name === "activespecialv2") {
                adapter.specialRefreshPending = true
                Qt.callLater(Hyprland.refreshMonitors)
            } else if (/^monitor(added|removed)/.test(name)) {
                adapter.monitorsChanged()
            } else if (name === "configreloaded") {
                adapter.configReloaded()
                adapter.monitorsChanged()
            }
        }
    }
}
