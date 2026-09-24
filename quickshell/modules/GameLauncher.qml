pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import "GameLauncher.js" as Launcher

Scope {
    id: root

    required property var compositor

    readonly property var monitors: compositor.getMonitors().map(monitor => monitorRecord(monitor))
    property var monitorCapabilities: ({})

    function monitorRecord(m) {
        var capabilities = monitorCapabilities[String(m.name || "")] || {}
        return {
            id: m.id,
            name: m.name,
            description: String(m.description || m.name || ""),
            width: Number(m.width || 0),
            height: Number(m.height || 0),
            x: Number(m.x || 0),
            y: Number(m.y || 0),
            scale: Number(m.scale || 1),
            refreshHz: Number(m.refreshHz || 0),
            focused: !!m.focused,
            hdr: !!capabilities.hdr,
            vrr: !!capabilities.vrr
        }
    }

    function updateMonitorCapabilities(output) {
        var next = {}
        var lines = String(output || "").trim().split("\n")

        for (var i = 0; i < lines.length; i++) {
            var fields = lines[i].split("\t")
            if (fields.length === 3 && fields[0]) {
                next[fields[0]] = {
                    hdr: fields[1] === "true",
                    vrr: fields[2] === "true"
                }
            }
        }

        monitorCapabilities = next
    }

    function probeMonitorCapabilities() {
        monitorCapabilities = ({})
        monitorCapabilityProbeTimer.restart()
    }

    function focusedMonitor() {
        return monitors.find(monitor => monitor.focused) ?? monitors[0] ?? null
    }

    function gamescopePlan(appCommand, steamIntegration) {
        var monitor = focusedMonitor()
        var width = Math.round(Number(monitor && monitor.width || 0))
        var height = Math.round(Number(monitor && monitor.height || 0))
        if (!monitor || width <= 0 || height <= 0) {
            return {
                ok: false,
                error: "No focused monitor with a valid mode",
                arguments: []
            }
        }

        var args = [
            "gamescope",
            "-W", String(width),
            "-H", String(height),
            "-w", String(width),
            "-h", String(height)
        ]
        var refreshHz = Math.round(Number(monitor.refreshHz || 0))
        if (refreshHz > 0)
            args.push("-r", String(refreshHz))

        args.push("-f", "--expose-wayland")
        if (monitor.vrr)
            args.push("--adaptive-sync")
        if (monitor.hdr)
            args.push("--hdr-enabled")
        if (steamIntegration)
            args.push("-e")

        args.push("--")

        return {
            ok: true,
            monitor: monitor,
            arguments: args.concat(appCommand)
        }
    }

    function launchGamescope(appCommand, steamIntegration) {
        var plan = gamescopePlan(appCommand, steamIntegration)
        if (plan.ok) {
            // Assumes the child opens on the workspace focused at launch; add
            // tokenized placement only if delayed Flatpak startup disproves it.
            Quickshell.execDetached(["uwsm", "app", "--"].concat(plan.arguments))
        }

        return JSON.stringify(plan, null, 2)
    }

    function focusExistingGamescope() {
        var window = Launcher.existingSteamWindow(compositor.toplevels)
        if (!window)
            return false
        compositor.activateWindow(window.address)
        return true
    }

    Process {
        id: monitorCapabilityProbe

        stdout: StdioCollector {
            onStreamFinished: root.updateMonitorCapabilities(this.text)
        }
    }

    Timer {
        id: monitorCapabilityProbeTimer
        interval: 100
        repeat: false
        onTriggered: {
            if (monitorCapabilityProbe.running)
                monitorCapabilityProbeTimer.restart()
            else
                monitorCapabilityProbe.exec(["icewine-monitor-capabilities"])
        }
    }

    Connections {
        target: compositor

        function onMonitorsChanged() {
            root.probeMonitorCapabilities()
        }

    }

    IpcHandler {
        target: "gameLauncher"

        function dump(): string {
            return JSON.stringify({
                monitors: root.monitors,
                monitorCapabilities: root.monitorCapabilities
            }, null, 2)
        }

        function gamescopePlan(): string {
            return JSON.stringify(root.gamescopePlan(["icewine-steam-session"], true), null, 2)
        }

        function launchSteamGamescope(): string {
            if (root.focusExistingGamescope())
                return JSON.stringify({ok: true, reused: true}, null, 2)
            return root.launchGamescope(["icewine-steam-session"], true)
        }

        function launchCommand(commandJson: string): string {
            var command
            try { command = JSON.parse(commandJson) } catch (error) {
                return JSON.stringify({ok: false, error: "Expected a JSON argument array"})
            }
            if (!Array.isArray(command) || command.length === 0
                    || !command.every(arg => typeof arg === "string" && arg.indexOf("\u0000") === -1)
                    || command[0].length === 0)
                return JSON.stringify({ok: false, error: "Expected a nonempty command"})
            return root.launchGamescope(command, false)
        }
    }

    Component.onCompleted: {
        probeMonitorCapabilities()
    }
}
