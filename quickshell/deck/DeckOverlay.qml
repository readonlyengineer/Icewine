pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Widgets
import qs.theme as Theme
import "DeckMenu.js" as Menu
import "modules/topbar" as Bar
import "modules/topbar/LauncherSearch.js" as LauncherSearch

Scope {
    id: root
    required property var compositor
    required property bool sessionLocked

    property bool opened: false
    required property var shell
    property bool draining: false
    property string page: "root"
    property int selected: 0
    readonly property var applications: LauncherSearch.applications(
        DesktopEntries.applications.values, "", shell.excludeSteamApps, steamShortcuts.commands)
    property var menuPages: Menu.buildPages(applications)
    property var entries: menuPages[page] || []
    property var held: ({})
    property bool acceptArmed: false
    property var pendingEntry: null
    property int workspace: 0
    property string monitorName: ""
    readonly property bool gamescopeFocused: compositor.activeWindowClass === "gamescope"
    property bool streamReady: false
    property string eventTarget: ""
    property string appliedRoute: ""
    property string requestedRoute: "overlay"
    property string inputError: ""
    readonly property string wantedRoute: Menu.inputRoute(
        gamescopeFocused, opened || shell.widgetEngaged, sessionLocked, draining, streamReady)
    readonly property bool captured: appliedRoute === "overlay" && !gate.running && wantedRoute === "overlay"

    Bar.SteamShortcuts { id: steamShortcuts }

    onMenuPagesChanged: {
        if (!menuPages[page]) page = "root"
        selected = Math.min(selected, Math.max(0, entries.length - 1))
    }

    function reconcile() {
        if (gate.running)
            return
        requestedRoute = wantedRoute
        gate.exec(["icewine-inputplumber-intercept", requestedRoute])
    }
    onWantedRouteChanged: reconcile()

    function open() {
        if (opened || sessionLocked)
            return
        page = "root"
        selected = 0
        acceptArmed = false
        pendingEntry = null
        workspace = compositor.focusedWorkspaceId()
        var monitors = compositor.getMonitors()
        var focused = monitors.find(function(m) { return m.focused })
        monitorName = focused?.name ?? Quickshell.screens[0]?.name ?? ""
        if (!monitorName) return
        shell.beginInteraction()
        opened = true
        // Also verify capture when the gamepad was already muted on desktop.
        reconcile()
        if (shell.excludeSteamApps)
            steamShortcuts.refresh()
    }

    function dismiss() {
        if (opened)
            requestClose(null)
    }

    function toggle() {
        if (opened)
            dismiss()
        else
            open()
    }

    function choose(index) {
        if (!opened || draining || index < 0 || index >= entries.length)
            return
        var entry = entries[index]
        if (entry.page) {
            page = entry.page
            selected = 0
            return
        }
        if ((entry.action === "terminal" || entry.action === "application") && workspace <= 0) {
            inputError = "Cannot determine the launch workspace. Close and retry."
            return
        }
        requestClose(entry)
    }

    function requestClose(entry) {
        pendingEntry = entry
        if (entry && entry.action !== "keyboard") shell.yieldFocus()
        acceptArmed = false
        draining = true
        opened = false
        drainWarning.restart()
        finishClose()
    }

    function drainInput() {
        if (!Menu.neutral(held)) {
            draining = true
            drainWarning.restart()
        }
    }

    function finishClose() {
        if (!draining || !Menu.neutral(held))
            return
        // The UI is already dismissed. Only controller passthrough waits.
        draining = false
        drainWarning.stop()
        if (inputError.startsWith("Waiting for controller release.")) inputError = ""
        var entry = pendingEntry
        var launchWorkspace = workspace
        pendingEntry = null
        if (entry) {
            const generation = shell.focusGeneration
            Qt.callLater(function() {
                if (!root.sessionLocked && !root.opened && generation === root.shell.focusGeneration)
                    root.activate(entry, launchWorkspace)
            })
        }
    }

    function activate(entry, launchWorkspace) {
        if (entry.action === "keyboard") {
            Quickshell.execDetached(["icewine-keyboard-toggle"])
            return
        }
        shell.handoff()
        if (entry.action === "close") {
            compositor.dispatch("hl.dsp.window.close()")
        } else if (entry.action === "fullscreen") {
            compositor.toggleFullscreen()
        } else {
            var options = entry.action === "application"
                ? LauncherSearch.launchOptions(entry.application, Quickshell.env("HOME")) : null
            var expression = Menu.launchExpression(entry, launchWorkspace, options)
            if (expression)
                compositor.dispatch(expression)
        }
    }

    function receive(line) {
        if (line.indexOf("NIXDECK_TARGET ") === 0) {
            eventTarget = line.slice(15)
            return
        }
        if (line.indexOf("The name org.shadowblip.InputPlumber is owned by ") === 0) {
            streamReady = eventTarget !== ""
            return
        }
        if (line.indexOf("does not have an owner") >= 0
                || (line.indexOf("InterfacesRemoved") >= 0 && line.indexOf(eventTarget) >= 0)) {
            events.running = false
            return
        }
        var event = Menu.parseInput(line, eventTarget)
        if (!event)
            return
        var result = Menu.controllerEvent(held, event, entries.length, selected)
        const accept = acceptArmed && result.command === "accept"
        if (event.action === "ui_accept")
            acceptArmed = opened && captured && event.pressed
        if (draining) {
            finishClose()
        } else if (opened && captured) {
            selected = result.selected
            if (accept) choose(selected)
        }
    }

    Process {
        id: gate
        stderr: SplitParser { onRead: data => console.warn("Deck input:", data) }
        onExited: function(code) {
            root.appliedRoute = code === 0 ? root.requestedRoute : ""
            root.inputError = code === 0 ? "" : "Controller capture failed; check the Quickshell journal."
            if (code !== 0)
                gateRetry.restart()
            else if (root.appliedRoute !== root.wantedRoute)
                Qt.callLater(root.reconcile)
        }
    }
    Timer { id: gateRetry; interval: 500; onTriggered: root.reconcile() }

    Process {
        id: events
        command: ["icewine-inputplumber-intercept", "events"]
        stdout: SplitParser { onRead: data => root.receive(data) }
        stderr: SplitParser { onRead: data => console.warn("Deck events:", data) }
        onExited: {
            root.streamReady = false
            root.eventTarget = ""
            root.appliedRoute = ""
            root.reconcile()
            root.finishClose()
            reconnect.restart()
        }
    }
    Timer { id: reconnect; interval: 1500; onTriggered: events.running = true }

    GlobalShortcut {
        name: "deckRadial"
        onPressed: root.open()
        onReleased: root.dismiss()
    }

    Timer {
        id: drainWarning
        interval: 2000
        onTriggered: {
            root.inputError = "Waiting for controller release. Move and release the held controls to resume."
            console.warn("Deck input:", root.inputError)
        }
    }
    onSessionLockedChanged: {
        if (sessionLocked) {
            pendingEntry = null
            dismiss()
        }
    }

    Connections {
        target: root.compositor
        function onMonitorsChanged() {
            var monitors = root.compositor.getMonitors()
            if (root.opened && !monitors.some(m => m.name === root.monitorName))
                root.monitorName = monitors.length ? monitors[0].name : ""
        }
    }

    IpcHandler {
        target: "deckOverlay"
        function open(): string { root.open(); return "open" }
        function dismiss(): string { root.dismiss(); return "closed" }
        function toggle(): string { root.toggle(); return root.opened ? "open" : "closed" }
        function cycle(direction: string): string {
            if (root.opened || root.shell.widgetEngaged || root.draining || (direction !== "l" && direction !== "r"))
                return "ignored"
            root.compositor.dispatch("hl.dsp.layout(\"focus " + direction + "\")")
            return "ok"
        }
        function status(): string {
            return JSON.stringify({ open: root.opened, draining: root.draining,
                workspace: root.workspace, streamReady: root.streamReady,
                wantedRoute: root.wantedRoute, appliedRoute: root.appliedRoute, error: root.inputError })
        }
    }

    // Ordinary scene content, instantiated inside the shared shell window.
    readonly property Component view: Component {
        FocusScope {
            id: controls
            property int actionKey: 0
            onActiveFocusChanged: if (!activeFocus) actionKey = 0
            Keys.onPressed: event => {
                event.accepted = true
                if (event.isAutoRepeat) return
                if ([Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space].includes(event.key))
                    actionKey = event.key
                else if (event.key === Qt.Key_Tab)
                    root.selected = root.entries.length ? (root.selected + 1) % root.entries.length : 0
                else if (event.key === Qt.Key_Up)
                    root.selected = Menu.sector(0, -1, root.entries.length, root.selected)
                else if (event.key === Qt.Key_Right)
                    root.selected = Menu.sector(1, 0, root.entries.length, root.selected)
                else if (event.key === Qt.Key_Down)
                    root.selected = Menu.sector(0, 1, root.entries.length, root.selected)
                else if (event.key === Qt.Key_Left)
                    root.selected = Menu.sector(-1, 0, root.entries.length, root.selected)
            }
            Keys.onReleased: event => {
                event.accepted = true
                if (event.isAutoRepeat || event.key !== actionKey) return
                actionKey = 0
                if (event.key === Qt.Key_Escape) root.dismiss()
                else root.choose(root.selected)
            }
            Item {
                id: radial
                anchors.centerIn: parent
                width: Math.min(parent.width - 48, parent.height - 120, 560)
                height: width

                readonly property real orbitRadius: width * 0.385
                readonly property real buttonSize: root.entries.length <= 4 ? 104
                    : root.entries.length <= 6 ? 88 : 76

                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width * 0.96
                    height: width
                    radius: width / 2
                    color: Theme.Palette.alpha(Theme.Palette.backgroundDark, 0.9)
                    border.width: 1
                    border.color: Theme.Palette.alpha(Theme.Palette.border, 0.3)
                }

                Rectangle {
                    anchors.centerIn: parent
                    width: radial.orbitRadius * 2
                    height: width
                    radius: width / 2
                    color: "transparent"
                    border.width: 2
                    border.color: Theme.Palette.alpha(Theme.Palette.border, 0.33)
                }

                Repeater {
                    model: 24

                    Rectangle {
                        required property int index
                        readonly property real angle: index * 2 * Math.PI / 24 - Math.PI / 2
                        readonly property bool major: index % 3 === 0

                        width: major ? 6 : 3
                        height: width
                        radius: width / 2
                        x: radial.width / 2 + Math.cos(angle) * radial.orbitRadius - width / 2
                        y: radial.height / 2 + Math.sin(angle) * radial.orbitRadius - height / 2
                        color: major ? Theme.Palette.primary : Theme.Palette.foreground
                        opacity: major ? 0.9 : 0.28
                    }
                }

                Rectangle {
                    anchors.centerIn: parent
                    width: 142
                    height: width
                    radius: width / 2
                    color: Theme.Palette.backgroundDark
                    border.width: 2
                    border.color: Theme.Palette.secondary

                    Column {
                        anchors.centerIn: parent
                        width: parent.width - 24
                        spacing: 5

                        Text {
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            text: root.page.indexOf("launcher-") === 0 ? "LAUNCHER" : "NIXDECK"
                            color: Theme.Palette.secondary
                            font.family: "JetBrainsMono Nerd Font"
                            font.pixelSize: 13
                            font.bold: true
                            font.letterSpacing: 2
                        }

                        Text {
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            text: root.entries[root.selected]?.label || ""
                            color: Theme.Palette.foreground
                            font.family: "JetBrainsMono Nerd Font"
                            font.pixelSize: 12
                            font.bold: true
                            elide: Text.ElideRight
                        }
                    }
                }

                Repeater {
                    model: root.entries

                    Item {
                        id: choice
                        required property int index
                        required property var modelData
                        readonly property real angle: index * 2 * Math.PI / root.entries.length - Math.PI / 2
                        readonly property bool selected: root.selected === index

                        width: radial.buttonSize
                        height: width
                        x: radial.width / 2 + Math.cos(angle) * radial.orbitRadius - width / 2
                        y: radial.height / 2 + Math.sin(angle) * radial.orbitRadius - height / 2
                        scale: selected ? 1.1 : 1
                        z: selected ? 2 : 1

                        Rectangle {
                            anchors.centerIn: parent
                            width: parent.width + 12
                            height: width
                            radius: width / 2
                            color: "transparent"
                            border.width: 3
                            border.color: Theme.Palette.secondary
                            opacity: choice.selected ? 0.75 : 0
                        }

                        Rectangle {
                            anchors.fill: parent
                            radius: width / 2
                            color: choice.selected ? Theme.Palette.primary
                                : Theme.Palette.alpha(Theme.Palette.surface, 0.93)
                            border.width: choice.selected ? 2 : 1
                            border.color: choice.selected ? Theme.Palette.foreground
                                : Theme.Palette.alpha(Theme.Palette.border, 0.33)

                            IconImage {
                                anchors.centerIn: parent
                                implicitSize: radial.buttonSize < 80 ? 24 : 31
                                visible: choice.modelData.action === "application"
                                source: visible ? Quickshell.iconPath(
                                    choice.modelData.application.icon, "application-x-executable") : ""
                            }

                            Text {
                                anchors.centerIn: parent
                                visible: choice.modelData.action !== "application"
                                text: choice.modelData.icon || "󰋜"
                                color: choice.selected ? Theme.Palette.backgroundDark : Theme.Palette.foreground
                                font.family: "JetBrainsMono Nerd Font"
                                font.pixelSize: radial.buttonSize < 80 ? 24 : 31
                            }

                            Behavior on color { ColorAnimation { duration: 120 } }
                        }

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onEntered: root.selected = choice.index
                            onClicked: root.choose(choice.index)
                        }

                        Behavior on scale {
                            NumberAnimation { duration: 130; easing.type: Easing.OutCubic }
                        }
                    }
                }
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 18
                width: parent.width - 48
                visible: root.inputError !== ""
                text: root.inputError
                horizontalAlignment: Text.AlignHCenter
                color: Theme.Palette.error
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 12
            }

        }
    }
    Component.onCompleted: {
        reconcile()
        events.running = true
    }
}
