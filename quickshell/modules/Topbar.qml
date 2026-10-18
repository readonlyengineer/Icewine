pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Effects
import QtQuick.Controls
import Quickshell
import qs.config as Config
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Services.Mpris
import Quickshell.Wayland
import "topbar" as Bar
import "ShellState.js" as State
import "topbar/CardModules.js" as Cards
import qs.icewine.theme as Theme

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
    property bool layoutsEnabled: true
    readonly property bool layoutActive: layoutsEnabled && !sessionLocked
        && panels.instances.some(panel => panel.widgetHere && panel.layoutActive)
    readonly property int barHeight: 38
    readonly property int shadowDrop: 4
    readonly property bool fullBar: fullWidth || radialVisible || Config.Settings.barWidth === 100
    readonly property bool floatingBar: !fullWidth && !radialVisible && Config.Settings.barStyle === "floating"
    readonly property int barGap: floatingBar ? 4 : 0
    readonly property int barExtent: barHeight + barGap
    readonly property bool bottomBar: Config.Settings.barLocation === "bottom"
    readonly property var player: Mpris.players.values.find(candidate => candidate.isPlaying)
        ?? Mpris.players.values[0] ?? null

    property var ui: State.initial()
    property string hoveredScreen: ""
    readonly property bool radialVisible: radial?.opened ?? false
    readonly property bool widgetEngaged: ui.engaged
    readonly property bool barVisible: !sessionLocked
        && State.barVisible(ui, radialVisible, hoveredScreen !== "", Config.Settings.barBehaviour)
    readonly property bool mouseBindsSuppressed: !sessionLocked
        && (radialVisible || widgetEngaged || (barVisible && hoveredScreen !== "")
            || panels.instances.some(panel => panel.widgetHere && panel.widgetHovered))
    onMouseBindsSuppressedChanged: compositor.supress_mouse_binds(mouseBindsSuppressed)
    Component.onCompleted: compositor.supress_mouse_binds(mouseBindsSuppressed)
    readonly property bool interactionWanted: !sessionLocked && !ui.suppressed
        && (ui.held || ui.latched || ui.page !== "" || radialVisible || hoveredScreen !== "")
    onInteractionWantedChanged: if (!interactionWanted) finishInteraction()
    property bool interactionActive: false
    property string previousWindow: ""
    property var previousToplevel: null
    property int focusGeneration: 0
    property int widgetFocusGeneration: 0
    property bool reportedRender: false
    property var keyboard: null
    readonly property bool oskVisible: keyboard?.desktopVisible ?? false
    property bool instantBarHide: false
    property var clipboardPaste: null
    property var keyboardRequest: null
    property int barModifiersHeld: 0

    function cancelKeyboardRequest() {
        keyboardRequest = null
        keyboardWait.stop()
    }

    function keyboardRequestValid() {
        const request = keyboardRequest
        return request && !sessionLocked && request.mode === Config.Settings.oskAccess
            && request.generation === focusGeneration
            && (request.awaitingRelease || (!ui.page && !ui.held && !radialVisible))
            && compositor.toplevels.includes(request.window)
            && (!compositor.activeWindowAddress || compositor.activeWindowAddress === request.window.address)
    }

    function showKeyboard(mode) {
        if (sessionLocked || !["launcher", "topbar"].includes(mode)
                || mode !== Config.Settings.oskAccess || !keyboard || keyboard.busy)
            return
        // An invalidated original target must not fall back to the newly active app.
        const window = interactionActive
            ? (previousWindow ? previousToplevel : null)
            : compositor.toplevels.find(candidate => candidate.address === compositor.activeWindowAddress)
        if (!window || !compositor.toplevels.includes(window)) return
        cancelClipboardPaste()
        cancelKeyboardRequest()
        keyboardRequest = {window: window, mode: mode, generation: focusGeneration, awaitingRelease: true}
        if (!ui.held && barModifiersHeld === 0) handoffKeyboardRequest()
    }

    function handoffKeyboardRequest() {
        if (!keyboardRequestValid()) { cancelKeyboardRequest(); return }
        const request = keyboardRequest
        instantHandoff()
        finishInteraction()
        request.awaitingRelease = false
        request.generation = focusGeneration
        keyboardRequest = request
        Qt.callLater(() => {
            if (root.keyboardRequest !== request) return
            if (!root.keyboardRequestValid()) { root.cancelKeyboardRequest(); return }
            root.compositor.activateToplevel(request.window)
            keyboardWait.attempts = 0
            keyboardWait.start()
        })
    }

    function finishKeyboardRequest() {
        if (!keyboardRequestValid() || ++keyboardWait.attempts > 30) {
            cancelKeyboardRequest()
            return
        }
        if (keyboardRequest.awaitingRelease || barModifiersHeld > 0
                || compositor.activeWindowAddress !== keyboardRequest.window.address || keyboard.busy) return
        // The owner retains its existing live-target, finite-input and lock gates.
        cancelKeyboardRequest()
        keyboard.show()
    }

    Timer {
        id: keyboardWait
        property int attempts: 0
        interval: 30; repeat: true
        onTriggered: root.finishKeyboardRequest()
    }

    Bar.ClipboardHistory {
        id: clipboardHistory
        locked: root.sessionLocked || !Cards.containing(Config.Settings.cardStacks, "clipboard")
        onLoaded: request => root.clipboardLoaded(request)
        onBusyChanged: if (!busy && root.clipboardPaste?.phase === "loading" && error)
            root.cancelClipboardPaste()
        onAvailableChanged: if (!available) root.cancelClipboardPaste()
        onActiveEntryChanged: if (root.clipboardPaste && root.clipboardPaste.phase !== "loading"
                && activeEntry !== root.clipboardPaste.entry) root.cancelClipboardPaste()
    }

    function cancelClipboardPaste() {
        if (!clipboardPaste) return
        const dismissed = clipboardPaste.phase !== "loading"
        clipboardPaste = null
        pasteWait.stop()
        pasteDelivery.running = false
        clipboardHistory.error = "Paste cancelled: original app or session changed"
        if (dismissed)
            Quickshell.execDetached(["notify-send", "--app-name=Icewine", "Clipboard paste", clipboardHistory.error])
    }

    function pasteClipboard(entry) {
        const window = previousToplevel
        const stableId = String(window?.lastIpcObject?.stableId ?? "")
        if (sessionLocked || ui.held || clipboardPaste || !previousWindow || !window
                || !compositor.toplevels.includes(window) || !/^[0-9a-fA-F]{1,16}$/.test(stableId)) {
            clipboardHistory.error = ui.held ? "Release the opening shortcut before paste"
                : "Paste unavailable: no original application"
            return
        }
        const request = clipboardHistory.request("load", entry)
        if (request) clipboardPaste = {window: window, stableId: stableId, request: request, entry: entry,
            generation: focusGeneration, widgetGeneration: widgetFocusGeneration, phase: "loading"}
    }

    function clipboardPasteValid() {
        const intent = clipboardPaste
        return intent && !sessionLocked && intent.generation === focusGeneration
            && intent.widgetGeneration === widgetFocusGeneration
            && compositor.toplevels.includes(intent.window)
            && String(intent.window.lastIpcObject?.stableId ?? "") === intent.stableId
    }

    function clipboardLoaded(request) {
        const intent = clipboardPaste
        if (!intent || intent.phase !== "loading" || intent.request !== request) return
        if (!clipboardPasteValid() || !Cards.containing(Config.Settings.cardStacks, "clipboard")?.modules.includes(ui.page)
                || previousWindow !== intent.window.address) {
            cancelClipboardPaste()
            return
        }
        intent.phase = "handoff"
        intent.selection = clipboardHistory.selection
        instantHandoff()
        intent.phase = "restoring"
        intent.generation = focusGeneration
        intent.widgetGeneration = widgetFocusGeneration
        Qt.callLater(() => {
            if (!root.clipboardPasteValid()) { root.cancelClipboardPaste(); return }
            root.compositor.activateToplevel(intent.window)
            pasteWait.attempts = 0
            pasteWait.start()
        })
    }

    function deliverClipboardPaste() {
        if (clipboardPaste?.phase !== "restoring") return
        if (!clipboardPasteValid() || ui.page || ++pasteWait.attempts > 30) {
            cancelClipboardPaste()
            return
        }
        if (compositor.activeWindowAddress !== clipboardPaste.window.address) return
        pasteWait.stop()
        clipboardPaste.phase = "sending"
        // The helper independently checks native lock state and stable focus before
        // finite virtual-keyboard input. The compositor retains input/lock policy.
        pasteDelivery.command = ["icewine-clipboard", "paste", clipboardPaste.stableId,
            clipboardPaste.selection[0], clipboardPaste.selection[1]]
        pasteDelivery.running = true
    }

    Timer {
        id: pasteWait
        property int attempts: 0
        interval: 30; repeat: true
        onTriggered: root.deliverClipboardPaste()
    }
    Process {
        id: pasteDelivery
        stdout: StdioCollector {}
        onExited: (code, status) => {
            if (!root.clipboardPaste) return
            root.clipboardPaste = null
            if (code !== 0 || status !== 0 || stdout.text.trim() !== "ok") {
                clipboardHistory.error = "Paste failed; clipboard remains available for manual paste"
                Quickshell.execDetached(["notify-send", "--app-name=Icewine", "Clipboard paste", clipboardHistory.error])
            }
        }
    }

    signal widgetDismissed()
    signal focusWidgetRequested(string screenName, string openingPage)
    signal rendered()

    function focusedScreenName() {
        return Quickshell.screens.find(screen => root.compositor.monitorFor(screen)?.focused)?.name
            ?? Quickshell.screens[0]?.name ?? ""
    }

    function beginInteraction() {
        cancelKeyboardRequest()
        if (interactionActive || sessionLocked)
            return
        ui = State.reduce(ui, { type: "resume" })
        keyboard?.hide()
        ++focusGeneration
        previousWindow = compositor.activeWindowAddress
        previousToplevel = compositor.toplevels.find(window => window.address === previousWindow) ?? null
        interactionActive = true
    }

    function pressBar() {
        if (sessionLocked) return
        cancelClipboardPaste()
        beginInteraction()
        const closing = Config.Settings.barBehaviour === "toggle" && ui.latched && !ui.held
        ui = State.reduce(ui, { type: "press", behaviour: Config.Settings.barBehaviour })
        if (closing) { dismissWidget(); hoveredScreen = "" }
    }

    function releaseBar() {
        if (keyboardRequest?.awaitingRelease) {
            // A click under the opening chord retains intent until Super is up.
            // Keep its interaction alive if grave was released before Super.
            if (barModifiersHeld > 0) return
            handoffKeyboardRequest()
        }
        ui = State.reduce(ui, { type: "release" })
    }

    function finishInteraction() {
        if (!interactionActive)
            return
        interactionActive = false
        const address = previousWindow
        const window = previousToplevel
        const generation = ++focusGeneration
        previousWindow = ""
        previousToplevel = null
        // Let the layer release its keyboard ownership before restoring focus.
        Qt.callLater(() => {
            if (address && window && root.compositor.toplevels.includes(window)
                    && generation === root.focusGeneration && !root.interactionWanted && !root.sessionLocked)
                root.compositor.activateWindow(address)
        })
    }

    function openWidget(page, engaged, screenName) {
        if (sessionLocked || !screenName || (page === "layout" && !layoutsEnabled) || (page === "switcher" && !Config.Settings.windowSwitcher))
            return
        if (page !== "switcher" && !Cards.containing(Config.Settings.cardStacks, page)) return
        cancelClipboardPaste()
        const next = State.reduce(ui, { type: "open", page: page, engaged: engaged, screen: screenName })
        if (next === ui) return
        beginInteraction()
        ui = next
        const generation = ++widgetFocusGeneration
        if (engaged)
            Qt.callLater(() => {
                if (!root.sessionLocked && generation === root.widgetFocusGeneration)
                    root.focusWidgetRequested(next.screen, page)
            })
    }

    function toggleSwitcher() {
        if (ui.page === "switcher") dismissWidget()
        else openWidget("switcher", true, focusedScreenName())
    }

    function activateSwitcherWindow(window) {
        if (sessionLocked || !compositor.toplevels.includes(window))
            return
        instantHandoff()
        const generation = focusGeneration
        Qt.callLater(() => {
            if (!root.sessionLocked && generation === root.focusGeneration && !root.ui.page)
                root.compositor.activateToplevel(window)
        })
    }

    function engageWidget() {
        ui = State.reduce(ui, { type: "engage" })
    }

    function dismissWidget() {
        cancelKeyboardRequest()
        if (clipboardPaste?.phase !== "handoff") cancelClipboardPaste()
        ++widgetFocusGeneration
        if (ui.engaged) radial?.drainInput()
        widgetDismissed()
        ui = State.reduce(ui, { type: "dismiss" })
    }

    function dismiss(suppress = true) {
        cancelKeyboardRequest()
        if (clipboardPaste?.phase !== "handoff") cancelClipboardPaste()
        ++widgetFocusGeneration
        if (ui.engaged) radial?.drainInput()
        widgetDismissed()
        ui = State.reduce(ui, { type: suppress ? "hide" : "reset" })
        hoveredScreen = ""
        radial?.dismiss()
    }

    function yieldFocus() {
        cancelKeyboardRequest()
        previousWindow = ""
        ++focusGeneration
    }

    // Ordinary app handoffs release focus; capture/lock explicitly suppress chrome.
    function handoff(suppress = false) {
        yieldFocus()
        dismiss(suppress)
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

    onSessionLockedChanged: {
        if (sessionLocked) { barModifiersHeld = 0; cancelClipboardPaste(); handoff(true) }
        else ui = State.initial()
    }

    Connections {
        target: Config.Settings
        function onOskAccessChanged() { root.cancelKeyboardRequest() }
        function onBarBehaviourChanged() { root.handoff(false) }
        function onBarLocationChanged() { root.handoff(false) }
        function onCardStacksChanged() { root.dismissWidget() }
        function onWindowSwitcherChanged() {
            if (!Config.Settings.windowSwitcher && root.ui.page === "switcher")
                root.dismissWidget()
        }
    }

    Connections {
        target: Quickshell
        function onScreensChanged() {
            if (!Quickshell.screens.some(screen => screen.name === root.hoveredScreen)) root.hoveredScreen = ""
            if (root.ui.page && !Quickshell.screens.some(screen => screen.name === root.ui.screen)) root.dismissWidget()
        }
    }

    Connections {
        target: root.compositor
        function onNavigationRequested() { root.cancelClipboardPaste(); root.handoff(false) }
        function onActiveWindowAddressChanged() {
            const address = root.compositor.activeWindowAddress
            if (root.keyboardRequest && address && address !== root.keyboardRequest.window.address)
                root.cancelKeyboardRequest()
            if (root.clipboardPaste && address && address !== root.clipboardPaste.window.address)
                root.cancelClipboardPaste()
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
        onPressed: root.barModifiersHeld++
        onReleased: {
            root.barModifiersHeld = Math.max(0, root.barModifiersHeld - 1)
            root.releaseBar()
        }
    }

    LazyLoader {
        active: Config.Settings.windowSwitcher
        component: GlobalShortcut {
            name: "windowSwitcher"
            onReleased: root.toggleSwitcher()
        }
    }

    Variants {
        id: panels
        model: Quickshell.screens

        PanelWindow {
            id: panel
            required property var modelData
            readonly property bool layoutActive: statusPopout.layoutActive
            readonly property bool widgetHere: root.ui.page !== "" && root.ui.screen === screen.name
            readonly property bool modal: root.radialVisible || root.widgetEngaged
            readonly property string keyboardScreen: root.widgetEngaged ? root.ui.screen : root.radial?.monitorName ?? ""
            readonly property string hoverPage: logo.visible && logo.hovered ? "launcher" : statusIcons.hoveredPage
            readonly property bool widgetHovered: statusPopout.hovered
            readonly property int reservation: root.barVisible && Config.Settings.barLocation !== "above" ? root.barExtent : 0
            readonly property bool pointerInside: barHover.hovered || edgeHover.hovered || (widgetHere && widgetHovered)
            onPointerInsideChanged: {
                if (pointerInside) {
                    pointerLeave.stop()
                    if (edgeHover.hovered) root.ui = State.reduce(root.ui, { type: "resume" })
                    root.hoveredScreen = screen.name
                } else pointerLeave.restart()
            }
            Timer {
                id: pointerLeave
                interval: 180
                onTriggered: if (!panel.pointerInside && root.hoveredScreen === panel.screen.name) root.hoveredScreen = ""
            }

            property PanelWindow workArea: PanelWindow {
                screen: panel.screen
                visible: panel.reservation > 0
                anchors { left: true; right: true; top: !root.bottomBar; bottom: root.bottomBar }
                implicitHeight: root.barExtent
                exclusiveZone: panel.reservation
                color: "transparent"
                mask: Region {}
                WlrLayershell.namespace: "icewine:bar-reservation"
                WlrLayershell.layer: WlrLayer.Top
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            }

            function focusWidget(openingPage) {
                if (!widgetHere || !root.widgetEngaged) return
                if (switcher.item) switcher.item.forceActiveFocus()
                else {
                    if (openingPage) statusPopout.openPage(openingPage)
                    statusPopout.focusInitial()
                }
            }

            onHoverPageChanged: {
                previewOpen.stop()
                if (hoverPage && (!root.widgetEngaged || root.ui.page === "switcher"))
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
            // Reclaim our own reservation, while respecting other native zones (e.g. OSK).
            margins.top: root.bottomBar ? 0 : -reservation
            margins.bottom: root.bottomBar ? -reservation : 0
            exclusiveZone: 0
            color: "transparent"
            WlrLayershell.namespace: "quickshell:topbar"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: modal && root.ui.page !== "switcher"
                && screen.name === keyboardScreen && !root.sessionLocked
                ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

            HyprlandFocusGrab {
                windows: [panel]
                active: panel.widgetHere && root.ui.page === "switcher"
                    && root.widgetEngaged && !root.sessionLocked
                onCleared: if (root.ui.page === "switcher") root.handoff()
            }

            // Only mouse-autohide keeps a one-logical-pixel reveal edge while hidden.
            mask: Region {
                Region { item: panel.modal && !root.oskVisible && !root.sessionLocked ? input : null }
                Region { item: root.barVisible ? surface : null }
                Region { item: edge.enabled ? edge : null }
                Region { item: switcher.active ? switcher : null }
                Region { item: statusPopout.shown ? statusPopout : null }
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
                    anchors { fill: parent; topMargin: root.bottomBar ? 0 : root.barHeight; bottomMargin: root.bottomBar ? root.barHeight : 0 }
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

                Item {
                    id: edge
                    width: parent.width
                    height: 1
                    y: root.bottomBar ? parent.height - height : 0
                    enabled: Config.Settings.barBehaviour === "keyboard-mouse" && !root.sessionLocked
                    HoverHandler { id: edgeHover; enabled: edge.enabled }
                }

                Rectangle {
                    id: surface
                    x: (parent.width - width) / 2
                    y: root.bottomBar ? (root.barVisible ? parent.height - height - root.barGap : parent.height) : (root.barVisible ? root.barGap : -height)
                    width: root.fullBar ? parent.width : parent.width * Config.Settings.barWidth / 100
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
                        shadowVerticalOffset: root.shadowDrop
                    }
                    topLeftRadius: !root.fullBar && (root.floatingBar || root.bottomBar) ? (root.floatingBar ? height / 2 : 10) : 0
                    topRightRadius: topLeftRadius
                    bottomLeftRadius: !root.fullBar && (root.floatingBar || !root.bottomBar) ? (root.floatingBar ? height / 2 : 10) : 0
                    bottomRightRadius: bottomLeftRadius

                    // Consume bar input below its controls, above outside-dismiss.
                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.AllButtons
                        onWheel: event => event.accepted = true
                    }

                    // Bound intrinsic rows around the centred clock; overflow remains draggable.
                    readonly property real controlWidth: Math.max(0, (width - barClock.implicitWidth) / 2 - 12)
                    Flickable {
                        id: workspaceScroll
                        anchors { left: parent.left; leftMargin: 4; verticalCenter: parent.verticalCenter }
                        width: Math.min(contentWidth, surface.controlWidth)
                        height: 29
                        contentWidth: workspaceRow.implicitWidth
                        contentHeight: height
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        flickableDirection: Flickable.HorizontalFlick
                        ScrollBar.horizontal: ScrollBar {}
                        Row {
                            id: workspaceRow
                            spacing: 4
                            Bar.Logo {
                                id: logo
                                visible: Config.Settings.cardStacks.some(stack => stack.modules[0] === "launcher")
                                backgroundCount: statusPopout.backgroundCount
                                backgroundAttention: statusPopout.backgroundAttention
                                onActivated: root.openWidget("launcher", true, panel.screen.name)
                            }
                            Bar.Workspaces { id: workspaces; compositor: root.compositor; screen: panel.screen }
                        }
                    }
                    Bar.Clock { id: barClock; anchors.centerIn: parent; now: clock.date }
                    Flickable {
                        id: statusScroll
                        anchors { right: parent.right; rightMargin: 4; verticalCenter: parent.verticalCenter }
                        width: Math.min(contentWidth, surface.controlWidth)
                        height: 29
                        contentWidth: statusIcons.implicitWidth
                        contentHeight: height
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        flickableDirection: Flickable.HorizontalFlick
                        ScrollBar.horizontal: ScrollBar {}
                        Bar.StatusIcons {
                            id: statusIcons
                            cardStacks: Config.Settings.cardStacks.filter(stack => stack.modules[0] !== "launcher")
                            notificationService: root.notificationService
                            player: root.player
                            layoutsEnabled: root.layoutsEnabled
                            backgroundCount: statusPopout.backgroundCount
                            backgroundAttention: statusPopout.backgroundAttention
                            onKeyboardRequested: root.showKeyboard("topbar")
                            onMediaRequested: root.raiseMedia()
                            onPopoutActivated: page => root.openWidget(page, true, panel.screen.name)
                        }
                    }
                    HoverHandler {
                        id: barHover
                        enabled: root.barVisible
                    }
                    Behavior on y { NumberAnimation { duration: root.instantBarHide ? 0 : 160; easing.type: Easing.OutCubic } }
                    Behavior on opacity { NumberAnimation { duration: root.instantBarHide ? 0 : 140 } }
                }

                Loader {
                    id: switcher
                    active: Config.Settings.windowSwitcher === true && panel.widgetHere && root.ui.page === "switcher" && !root.sessionLocked
                    anchors.centerIn: parent
                    width: Math.max(0, Math.min(1000, panel.width - 2 * Math.min(24, panel.width / 20), implicitWidth))
                    height: Math.max(0, Math.min(720, panel.height - 2 * Math.min(24, panel.height / 20), implicitHeight))
                    onLoaded: item.forceActiveFocus()
                    sourceComponent: WindowSwitcher {
                        compositor: root.compositor
                        monitorName: panel.screen.name
                        onDismissRequested: root.dismissWidget()
                        onActivateRequested: window => root.activateSwitcherWindow(window)
                    }
                }
                Bar.StatusPopout {
                    id: statusPopout
                    shadowDrop: root.shadowDrop
                    layer.enabled: visible
                    layer.effect: MultiEffect {
                        shadowEnabled: !statusPopout.floatingCards
                        shadowColor: "#000000"
                        shadowOpacity: 0.35
                        shadowBlur: 0.6
                        blurMax: 16
                        shadowVerticalOffset: root.shadowDrop
                    }
                    shown: panel.widgetHere && root.ui.page !== "switcher"
                    animateClose: !root.instantBarHide && !root.sessionLocked
                    engaged: root.widgetEngaged
                    Binding {
                        target: statusPopout
                        property: "currentPage"
                        value: root.ui.page
                        when: statusPopout.shown
                        restoreMode: Binding.RestoreNone
                    }
                    x: Math.max(8, Math.min(statusPopout.configuration?.modules[0] === "launcher"
                        ? surface.x : surface.x + surface.width - width,
                        panel.width - width - 8))
                    y: root.bottomBar ? Math.max(0, panel.height - root.barExtent - 4 - height) : root.barExtent + 4
                    width: Math.max(0, Math.min(implicitWidth, panel.width - 16))
                    height: Math.max(0, Math.min(implicitHeight, panel.height - root.barExtent - 12))
                    layoutsEnabled: root.layoutsEnabled
                    excludeSteamApps: root.excludeSteamApps
                    compositor: root.compositor
                    notificationService: root.notificationService
                    session: root.session
                    powerState: root
                    metrics: metrics
                    monitorName: panel.screen.name
                    player: root.player
                    clipboardHistory: clipboardHistory
                    pasteBusy: root.clipboardPaste !== null
                    onPasteRequested: entry => root.pasteClipboard(entry)
                    onEngageRequested: root.engageWidget()
                    onDismissRequested: root.dismissWidget()
                    onHandoffRequested: root.handoff()
                    onKeyboardRequested: root.showKeyboard("launcher")
                    onMediaRequested: root.raiseMedia()
                }
            }

            Connections {
                target: root
                function onWidgetDismissed() { previewOpen.stop() }
                function onFocusWidgetRequested(screenName, openingPage) {
                    if (screenName === panel.screen.name) panel.focusWidget(openingPage)
                }
            }
        }
    }

    IpcHandler {
        target: "topbar"
        function mediaNext(): void { if (root.player?.canGoNext) root.player.next() }
        function mediaPrevious(): void { if (root.player?.canGoPrevious) root.player.previous() }
        function mediaToggle(): void { if (root.player?.canTogglePlaying) root.player.togglePlaying() }
        function press(): void { root.pressBar() }
        function release(): void { root.releaseBar() }
        function hide(): void { root.dismiss() }
        function audio(): void { root.openWidget("audio", true, root.focusedScreenName()) }
        function layout(): void { if (root.layoutsEnabled) root.openWidget("layout", true, root.focusedScreenName()) }
        function network(): void { root.openWidget("network", true, root.focusedScreenName()) }
        function performance(): void { root.openWidget("performance", true, root.focusedScreenName()) }
        function bluetooth(): void { root.openWidget("bluetooth", true, root.focusedScreenName()) }
        function battery(): void { root.openWidget("battery", true, root.focusedScreenName()) }
        function launcher(): void { root.openWidget("launcher", true, root.focusedScreenName()) }
    }
}
