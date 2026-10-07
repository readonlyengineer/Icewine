pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import qs.icewine.theme as Theme
import "GameLauncher.js" as Launcher

Scope {
    id: root

    required property var compositor
    property bool handheld: false
    readonly property bool steamEnabled: Quickshell.env("ICEWINE_STEAM_ENABLED") !== "false"

    readonly property var monitors: compositor.getMonitors().map(monitor => monitorRecord(monitor))
    property var monitorCapabilities: ({})
    property bool steamLaunching: false
    property bool steamSplashVisible: false
    property string steamSplashScreen: ""
    property var pendingSteamCommand: null
    property int steamAutostartRetries: 0
    property double steamGamescopePid: 0
    property bool steamRequestPending: false

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
        var monitor = root.focusedMonitor()
        var width = Math.round(Number(monitor && monitor.width || 0))
        var height = Math.round(Number(monitor && monitor.height || 0))
        if (!monitor || width <= 0 || height <= 0) {
            return {
                ok: false,
                error: "No focused monitor with a valid mode",
                arguments: []
            }
        }

        var args = ["gamescope"]
        if (steamIntegration && root.handheld)
            args.push("--backend", "wayland", "--default-touch-mode", "1")
        args.push(
            "-W", String(width),
            "-H", String(height),
            "-w", String(width),
            "-h", String(height)
        )
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

    function finishSteamLaunch() {
        root.steamLaunching = false
        root.steamSplashVisible = false
        root.steamSplashScreen = ""
        root.pendingSteamCommand = null
        root.steamRequestPending = false
        steamSessionProbe.running = false
        steamLaunchTimeout.stop()
    }

    function startSteamProcess() {
        if (!root.steamLaunching || root.pendingSteamCommand === null)
            return
        var command = root.pendingSteamCommand
        root.pendingSteamCommand = null
        try {
            Quickshell.execDetached(command)
        } catch (error) {
            console.warn("Could not start Steam Gamescope:", error)
            root.finishSteamLaunch()
        }
    }

    function launchSteamGamescope() {
        if (!root.steamEnabled)
            return JSON.stringify({ok: false, error: "Steam integration is disabled"}, null, 2)
        var decision = Launcher.steamLaunchAction(compositor.toplevels, root.steamLaunching)
        if (decision.action === "focus") {
            root.finishSteamLaunch()
            compositor.activateWindow(decision.window.address)
            return JSON.stringify({ok: true, reused: true}, null, 2)
        }
        if (decision.action === "wait" || root.steamRequestPending || steamSessionProbe.running)
            return JSON.stringify({ok: true, pending: true}, null, 2)

        var plan = root.gamescopePlan(["icewine-steam"], true)
        if (!plan.ok)
            return JSON.stringify(plan, null, 2)

        root.steamRequestPending = true
        root.steamGamescopePid = 0
        steamLaunchTimeout.restart()
        root.probeSteamSession()
        return JSON.stringify({ok: true, pending: true}, null, 2)
    }

    function probeSteamSession() {
        if (!steamSessionProbe.running) {
            steamSessionProbe.output = ""
            steamSessionProbe.exec(["systemctl", "--user", "show", "icewine-steam-gamescope.service",
                                   "--property=MainPID", "--property=LoadState"])
        }
    }

    function resolveSteamRequest(output) {
        var pid = Launcher.steamServicePid(output)
        if (pid === null) {
            root.finishSteamLaunch()
            console.warn("Could not identify the Steam Gamescope service")
            return
        }
        if (root.steamRequestPending && root.steamGamescopePid > 0 && pid === 0) {
            root.finishSteamLaunch()
            return
        }
        root.steamGamescopePid = pid
        if (!root.steamRequestPending) {
            root.handoffSteam()
            return
        }
        var decision = Launcher.steamLaunchAction(compositor.toplevels, root.steamLaunching, pid)
        if (decision.action === "focus") {
            root.finishSteamLaunch()
            compositor.activateWindow(decision.window.address)
            return
        }
        if (decision.action === "wait")
            return
        root.steamRequestPending = false
        var plan = root.gamescopePlan(["icewine-steam"], true)
        if (!plan.ok)
            return

        root.steamSplashScreen = plan.monitor.name
        root.steamLaunching = true
        root.steamSplashVisible = true
        // The stable service prevents duplicates after QML's launch timeout.
        // Follow Gamescope's lifetime and clean up Steam when it exits;
        // UWSM otherwise defaults services to ExitType=cgroup.
        root.pendingSteamCommand = [
            "uwsm", "app", "-t", "service",
            "-u", "icewine-steam-gamescope.service",
            "-p", "ExitType=main", "-p", "KillMode=control-group", "--"
        ].concat(plan.arguments)
        steamLaunchTimeout.restart()
    }

    function handoffSteam() {
        var existing = Launcher.existingSteamWindow(compositor.toplevels, root.steamGamescopePid)
        if (root.steamRequestPending && existing) {
            root.finishSteamLaunch()
            compositor.activateWindow(existing.address)
            return
        }
        if (root.steamLaunching && Launcher.gamescopeWindow(compositor.toplevels, root.steamGamescopePid))
            Quickshell.execDetached(["hyprctl", "eval",
                'require("icewine.modules.WindowPolicy").handoff_steam(' + root.steamGamescopePid + ')'])
    }

    function autostartSteamGamescope() {
        var result = JSON.parse(root.launchSteamGamescope())
        if (result.ok) {
            root.steamAutostartRetries = 0
            steamAutostartRetry.stop()
        } else if (++root.steamAutostartRetries < 40) {
            steamAutostartRetry.restart()
        } else {
            root.steamAutostartRetries = 0
        }
    }

    Process {
        id: steamSessionProbe
        property string output: ""
        stdout: StdioCollector { onStreamFinished: steamSessionProbe.output = this.text }
        onExited: root.resolveSteamRequest(output)
    }

    Timer {
        // Ponytail: bounded startup polling until MainPID appears; use service
        // notifications if repeated systemctl calls become measurable.
        interval: 250
        repeat: true
        running: root.steamRequestPending
            || (root.steamLaunching && root.pendingSteamCommand === null && root.steamGamescopePid === 0)
        onTriggered: root.probeSteamSession()
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

    Timer {
        id: steamLaunchTimeout
        interval: 120000
        onTriggered: root.finishSteamLaunch()
    }

    Timer {
        id: steamAutostartRetry
        interval: 250
        onTriggered: root.autostartSteamGamescope()
    }

    Connections {
        target: compositor

        function onMonitorsChanged() {
            root.probeMonitorCapabilities()
        }
        function onToplevelsChanged() { root.handoffSteam() }
    }

    Variants {
        model: root.steamSplashVisible
            ? Quickshell.screens.filter(screen => screen.name === root.steamSplashScreen)
            : []

        FloatingWindow {
            id: panel
            required property var modelData
            screen: modelData
            visible: true
            title: "Icewine Steam launch"
            implicitWidth: screen.width
            implicitHeight: screen.height
            color: "#000000"
            onClosed: root.finishSteamLaunch()

            RenderReady {
                item: panel.contentItem
                onReady: root.startSteamProcess()
            }

            Column {
                anchors.centerIn: parent
                spacing: 20

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: ""
                    color: Theme.Palette.foreground
                    font.family: "JetBrainsMono Nerd Font"
                    font.pixelSize: 64
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: ""
                    color: Theme.Palette.primary
                    font.family: "JetBrainsMono Nerd Font"
                    font.pixelSize: 32

                    RotationAnimator on rotation {
                        from: 0
                        to: 360
                        duration: 900
                        loops: Animation.Infinite
                        running: true
                    }
                }
            }
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
            return JSON.stringify(root.gamescopePlan(["icewine-steam"], true), null, 2)
        }

        function launchSteamGamescope(): string {
            return root.launchSteamGamescope()
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

    Component.onCompleted: root.probeMonitorCapabilities()
}
