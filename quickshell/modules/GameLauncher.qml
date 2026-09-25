pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.theme as Theme
import "GameLauncher.js" as Launcher

Scope {
    id: root

    required property var compositor
    property bool handheld: false

    readonly property var monitors: compositor.getMonitors().map(monitor => monitorRecord(monitor))
    property var monitorCapabilities: ({})
    property bool steamLaunching: false
    property bool steamSplashVisible: false
    property string steamSplashScreen: ""
    property var pendingSteamCommand: null
    property int steamAutostartRetries: 0

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
        steamSplashTimeout.stop()
        steamLaunchTimeout.stop()
    }

    function hideSteamSplash() {
        root.steamSplashVisible = false
        root.steamSplashScreen = ""
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

    function checkSteamLaunch() {
        if (!root.steamLaunching)
            return
        var window = Launcher.gamescopeWindow(compositor.toplevels)
        if (window) {
            root.finishSteamLaunch()
            compositor.activateWindow(window.address)
        }
    }

    function launchSteamGamescope() {
        var decision = Launcher.steamLaunchAction(compositor.toplevels, root.steamLaunching)
        if (decision.action === "focus") {
            root.finishSteamLaunch()
            compositor.activateWindow(decision.window.address)
            return JSON.stringify({ok: true, reused: true}, null, 2)
        }
        if (decision.action === "wait")
            return JSON.stringify({ok: true, pending: true}, null, 2)

        var plan = root.gamescopePlan(["icewine-steam"], true)
        if (!plan.ok)
            return JSON.stringify(plan, null, 2)

        root.steamSplashScreen = plan.monitor.name
        root.steamLaunching = true
        root.steamSplashVisible = true
        // The stable collected scope is the duplicate guard after QML's
        // bounded launch state expires; systemd rejects a second active unit.
        root.pendingSteamCommand = [
            "uwsm", "app", "-u", "icewine-steam-gamescope.scope", "--"
        ].concat(plan.arguments)
        steamSplashTimeout.restart()
        steamLaunchTimeout.restart()
        return JSON.stringify(plan, null, 2)
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
        id: steamSplashTimeout
        interval: 30000
        onTriggered: root.hideSteamSplash()
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

        function onToplevelsChanged() {
            root.checkSteamLaunch()
        }

    }

    Variants {
        model: root.steamSplashVisible
            ? Quickshell.screens.filter(screen => screen.name === root.steamSplashScreen)
            : []

        PanelWindow {
            id: panel
            required property var modelData
            screen: modelData
            visible: true
            color: "#000000"
            focusable: false
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.namespace: "quickshell:steam-launch"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            mask: Region {}

            RenderReady {
                item: panel.contentItem
                onReady: root.startSteamProcess()
            }

            anchors {
                top: true
                bottom: true
                left: true
                right: true
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
