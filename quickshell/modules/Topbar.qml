pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Services.Mpris
import Quickshell.Wayland
import "topbar" as Bar
import "ShellState.js" as State
import qs.theme as Theme

Scope {
    id: root

    required property var compositor
    required property var notificationService
    required property var session
    property bool keepAwake: false
    property bool sessionLocked: false
    property var radial: null
    property bool fullWidth: false
    property bool excludeSteamApps: false
    readonly property int barHeight: 38
    readonly property var player: Mpris.players.values.find(candidate => candidate.isPlaying)
        ?? Mpris.players.values[0] ?? null

    property var ui: State.initial()
    property string hoveredScreen: ""
    readonly property bool radialVisible: radial?.opened ?? false
    readonly property bool widgetEngaged: ui.engaged
    readonly property bool barVisible: !sessionLocked
        && State.barVisible(ui, radialVisible, hoveredScreen !== "")
    readonly property bool mouseBindsSuppressed: !sessionLocked
        && (radialVisible || widgetEngaged || (barVisible && hoveredScreen !== "")
            || panels.instances.some(panel => panel.widgetHere && panel.widgetHovered))
    onMouseBindsSuppressedChanged: compositor.supress_mouse_binds(mouseBindsSuppressed)
    Component.onCompleted: compositor.supress_mouse_binds(mouseBindsSuppressed)
    property bool interactionActive: false
    property string previousWindow: ""
    property int focusGeneration: 0
    property bool reportedRender: false
    property bool oskVisible: false
    property bool instantBarHide: false

    signal widgetDismissed()
    signal focusWidgetRequested(string screenName)
    signal rendered()

    function focusedScreenName() {
        return Quickshell.screens.find(screen => root.compositor.monitorFor(screen)?.focused)?.name
            ?? Quickshell.screens[0]?.name ?? ""
    }

    function beginInteraction() {
        if (interactionActive || sessionLocked)
            return
        ++focusGeneration
        previousWindow = compositor.activeWindowAddress
        interactionActive = true
    }

    function pressBar() {
        if (sessionLocked) return
        beginInteraction()
        ui = State.reduce(ui, { type: "press" })
    }

    function releaseBar() {
        ui = State.reduce(ui, { type: "release" })
    }

    function finishInteraction() {
        if (!interactionActive)
            return
        interactionActive = false
        const address = previousWindow
        const generation = ++focusGeneration
        previousWindow = ""
        // Let the layer release its keyboard ownership before restoring focus.
        Qt.callLater(() => {
            if (address && generation === root.focusGeneration && !root.barVisible && !root.sessionLocked)
                root.compositor.activateWindow(address)
        })
    }

    function openWidget(page, engaged, screenName) {
        if (sessionLocked || !screenName)
            return
        const next = State.reduce(ui, { type: "open", page: page, engaged: engaged, screen: screenName })
        if (next === ui) return
        beginInteraction()
        ui = next
        if (engaged)
            Qt.callLater(() => root.focusWidgetRequested(root.ui.screen))
    }

    function engageWidget() {
        ui = State.reduce(ui, { type: "engage" })
    }

    function dismissWidget() {
        if (ui.engaged) radial?.drainInput()
        widgetDismissed()
        ui = State.reduce(ui, { type: "dismiss" })
    }

    function dismiss() {
        if (ui.engaged) radial?.drainInput()
        widgetDismissed()
        ui = State.reduce(ui, { type: "reset" })
        hoveredScreen = ""
        radial?.dismiss()
    }

    function yieldFocus() {
        previousWindow = ""
        ++focusGeneration
    }

    function handoff() {
        yieldFocus()
        dismiss()
    }

    function instantHandoff() {
        instantBarHide = true
        handoff()
        Qt.callLater(() => instantBarHide = false)
    }

    function raiseMedia() {
        const media = player
        if (!media?.canRaise)
            return
        handoff()
        Qt.callLater(() => { if (media?.canRaise) media.raise() })
    }

    onBarVisibleChanged: if (!barVisible) finishInteraction()
    onSessionLockedChanged: if (sessionLocked) handoff()

    Connections {
        target: root.compositor
        function onNavigationRequested() { root.handoff() }
        function onActiveWindowAddressChanged() {
            const address = root.compositor.activeWindowAddress
            // Never undo an application launch or an explicit focus change.
            if (root.interactionActive && address && address !== root.previousWindow)
                root.previousWindow = ""
        }
        function onMonitorsChanged() {
            if (root.ui.page && !Quickshell.screens.some(screen => screen.name === root.ui.screen))
                root.dismissWidget()
        }
        function onConfigReloaded() {
            root.ui = State.reduce(root.ui, { type: "release" })
            root.compositor.supress_mouse_binds(root.mouseBindsSuppressed)
        }
    }

    SystemClock { id: clock; precision: SystemClock.Minutes }
    Bar.SystemMetrics { id: metrics }

    // One ordered Wayland event stream; no racing press/release subprocesses.
    GlobalShortcut {
        name: "topbarHold"
        onPressed: root.pressBar()
        onReleased: root.releaseBar()
    }
    GlobalShortcut {
        name: "topbarModifier"
        onReleased: root.releaseBar()
    }

    Variants {
        id: panels
        model: Quickshell.screens

        PanelWindow {
            id: panel
            required property var modelData
            readonly property bool widgetHere: root.ui.page !== "" && root.ui.screen === screen.name
            readonly property bool modal: root.radialVisible || root.widgetEngaged
            readonly property string keyboardScreen: root.widgetEngaged ? root.ui.screen : root.radial?.monitorName ?? ""
            readonly property string hoverPage: logo.hovered ? "launcher"
                : nowPlaying.hovered ? "media" : statusIcons.hoveredPage
            readonly property bool widgetHovered: launcher.hovered || statusPopout.hovered

            function focusWidget() {
                if (!widgetHere || !root.widgetEngaged)
                    return
                if (launcher.visible) launcher.focusInitial()
                else statusPopout.focusInitial()
            }

            onHoverPageChanged: {
                previewOpen.stop()
                if (hoverPage && !root.widgetEngaged)
                    previewOpen.restart()
            }

            IdleInhibitor {
                window: panel
                enabled: root.keepAwake
            }

            screen: modelData
            visible: true
            RenderReady {
                item: panel.contentItem
                onReady: {
                    if (!root.reportedRender) {
                        root.reportedRender = true
                        root.rendered()
                    }
                }
            }
            anchors { top: true; bottom: true; left: true; right: true }
            // Reserve nothing; respect an OSK's own reservation so it stays usable.
            exclusiveZone: 0
            color: "transparent"
            WlrLayershell.namespace: "quickshell:topbar"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: modal && screen.name === keyboardScreen && !root.sessionLocked
                ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

            // Hidden means no input region, including at the top edge.
            mask: Region {
                Region { item: panel.modal && !root.oskVisible && !root.sessionLocked ? input : null }
                Region { item: root.barVisible ? surface : null }
                Region { item: launcher.visible ? launcher : null }
                Region { item: statusPopout.visible ? statusPopout : null }
            }

            Timer {
                id: previewOpen
                interval: 150
                onTriggered: {
                    if (panel.hoverPage && root.barVisible)
                        root.openWidget(panel.hoverPage, false, panel.screen.name)
                }
            }
            Timer {
                interval: 180
                running: panel.widgetHere && !root.widgetEngaged && !panel.hoverPage && !panel.widgetHovered
                onTriggered: root.dismissWidget()
            }

            FocusScope {
                id: input
                anchors.fill: parent
                focus: true

                Rectangle {
                    anchors.fill: parent
                    visible: root.radialVisible
                    color: Theme.Palette.alpha(Theme.Palette.backgroundDark, 0.82)
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: panel.modal
                    acceptedButtons: Qt.AllButtons
                    onClicked: {
                        if (root.ui.page) root.dismissWidget()
                        else root.radial?.dismiss()
                    }
                    onWheel: event => event.accepted = true
                }
                Loader {
                    id: dial
                    anchors { fill: parent; topMargin: root.barHeight }
                    active: root.radialVisible && panel.screen.name === root.radial.monitorName
                    sourceComponent: root.radial?.view ?? null
                    onLoaded: if (!root.widgetEngaged) item.forceActiveFocus()
                    Connections {
                        target: root
                        function onWidgetDismissed() {
                            Qt.callLater(() => {
                                if (dial.item && !root.widgetEngaged)
                                    dial.item.forceActiveFocus()
                            })
                        }
                    }
                }

                Rectangle {
                    id: surface
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: root.barVisible ? 0 : -height
                    width: root.fullWidth || root.radialVisible ? parent.width : Math.round(parent.width * 0.8)
                    height: root.barHeight
                    opacity: root.barVisible ? 1 : 0
                    enabled: root.barVisible
                    color: Theme.Palette.backgroundDark
                    layer.enabled: visible
                    layer.effect: MultiEffect {
                        shadowEnabled: true
                        shadowColor: "#000000"
                        shadowOpacity: 0.35
                        shadowBlur: 0.6
                        blurMax: 16
                        shadowVerticalOffset: 4
                    }
                    bottomLeftRadius: root.radialVisible ? 0 : 10
                    bottomRightRadius: root.radialVisible ? 0 : 10

                    // Consume bar input below its controls, above outside-dismiss.
                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.AllButtons
                        onWheel: event => event.accepted = true
                    }

                    Row {
                        anchors { left: parent.left; leftMargin: 4; verticalCenter: parent.verticalCenter }
                        spacing: 4
                        Bar.Logo {
                            id: logo
                            backgroundCount: launcher.backgroundCount
                            backgroundAttention: launcher.backgroundAttention
                            onActivated: root.openWidget("launcher", true, panel.screen.name)
                        }
                        Bar.Workspaces { compositor: root.compositor; screen: panel.screen }
                    }
                    Bar.Clock { anchors.centerIn: parent; now: clock.date }
                    Row {
                        anchors { right: parent.right; rightMargin: 4; verticalCenter: parent.verticalCenter }
                        spacing: 4
                        Bar.NowPlaying {
                            id: nowPlaying
                            player: root.player
                            onPopoutActivated: root.openWidget("media", true, panel.screen.name)
                            onMediaRequested: root.raiseMedia()
                        }
                        Bar.StatusIcons {
                            id: statusIcons
                            notificationService: root.notificationService
                            onPopoutActivated: page => root.openWidget(page, true, panel.screen.name)
                        }
                    }
                    HoverHandler {
                        enabled: root.barVisible
                        onHoveredChanged: {
                            if (hovered) root.hoveredScreen = panel.screen.name
                            else if (root.hoveredScreen === panel.screen.name) root.hoveredScreen = ""
                        }
                    }
                    Behavior on y { NumberAnimation { duration: root.instantBarHide ? 0 : 160; easing.type: Easing.OutCubic } }
                    Behavior on opacity { NumberAnimation { duration: root.instantBarHide ? 0 : 140 } }
                }

                Bar.Launcher {
                    id: launcher
                    layer.enabled: visible
                    layer.effect: MultiEffect {
                        shadowEnabled: true
                        shadowColor: "#000000"
                        shadowOpacity: 0.35
                        shadowBlur: 0.6
                        blurMax: 16
                        shadowVerticalOffset: 4
                    }
                    excludeSteamApps: root.excludeSteamApps
                    visible: panel.widgetHere && root.ui.page === "launcher"
                    engaged: root.widgetEngaged
                    x: Math.max(8, surface.x)
                    y: root.barHeight + 4
                    width: Math.min(400, panel.width - 16)
                    height: Math.min(424, panel.height - y - 8)
                    onEngageRequested: root.engageWidget()
                    onDismissRequested: root.dismissWidget()
                    onHandoffRequested: root.handoff()
                }
                Bar.StatusPopout {
                    id: statusPopout
                    layer.enabled: visible
                    layer.effect: MultiEffect {
                        shadowEnabled: true
                        shadowColor: "#000000"
                        shadowOpacity: 0.35
                        shadowBlur: 0.6
                        blurMax: 16
                        shadowVerticalOffset: 4
                    }
                    visible: panel.widgetHere && root.ui.page !== "launcher"
                    engaged: root.widgetEngaged
                    currentPage: visible ? root.ui.page : "audio"
                    x: Math.max(8, Math.min(surface.x + surface.width - width, panel.width - width - 8))
                    y: root.barHeight + 4
                    width: Math.min(380, panel.width - 16)
                    height: Math.min(implicitHeight, panel.height - y - 8)
                    compositor: root.compositor
                    notificationService: root.notificationService
                    session: root.session
                    powerState: root
                    metrics: metrics
                    monitorName: panel.screen.name
                    player: root.player
                    onEngageRequested: root.engageWidget()
                    onDismissRequested: root.dismissWidget()
                    onHandoffRequested: root.handoff()
                    onInstantHandoffRequested: root.instantHandoff()
                    onMediaRequested: root.raiseMedia()
                }
            }

            Connections {
                target: root
                function onWidgetDismissed() { previewOpen.stop() }
                function onFocusWidgetRequested(screenName) {
                    if (screenName === panel.screen.name) panel.focusWidget()
                }
            }
        }
    }

    IpcHandler {
        target: "topbar"
        function mediaNext(): void { if (root.player?.canGoNext) root.player.next() }
        function mediaPrevious(): void { if (root.player?.canGoPrevious) root.player.previous() }
        function mediaToggle(): void { if (root.player?.canTogglePlaying) root.player.togglePlaying() }
        function osk(visible: bool): void { root.oskVisible = visible }
        function press(): void { root.pressBar() }
        function release(): void { root.releaseBar() }
        function hide(): void { root.dismiss() }
        function audio(): void { root.openWidget("audio", true, root.focusedScreenName()) }
        function network(): void { root.openWidget("network", true, root.focusedScreenName()) }
        function performance(): void { root.openWidget("performance", true, root.focusedScreenName()) }
        function screenshot(): void { root.openWidget("screenshot", true, root.focusedScreenName()) }
        function bluetooth(): void { root.openWidget("bluetooth", true, root.focusedScreenName()) }
        function battery(): void { root.openWidget("battery", true, root.focusedScreenName()) }
        function launcher(): void { root.openWidget("launcher", true, root.focusedScreenName()) }
    }
}
