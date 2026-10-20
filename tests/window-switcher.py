#!/usr/bin/env python3
"""Run the real switcher QML with synthetic native-object stand-ins and offscreen Qt.
Run: python3 tests/window-switcher.py . (qs on PATH).
"""
import os
from pathlib import Path
from qml_fixture import theme_fixture
import re
import shutil
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
qml = '''import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Effects
import QtTest
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pam
import qs.config as Config
import "icewine/modules" as Modules
import "icewine/modules/topbar" as Bar
import "icewine/adapters" as Adapters
import "icewine/theme" as Theme
import HyprlandFixtures
ShellRoot {
    id: shell
    Modules.SessionControl { id: mockSession; authenticationRequired: true }
    QtObject {
        id: mockNotifications
        property int count: 0
        property int highestUrgency: 0
        property bool doNotDisturb: false
        property int pulseToken: 0
    }
    QtObject { id: clock; property date date: new Date(2026, 9, 18, 12, 30) }
    QtObject {
        id: statusPopout
        property int backgroundCount: 0
        property bool backgroundAttention: false
        function openPage(page) {}
        function focusInitial() {}
    }
    QtObject { id: switcher; property var item: null }
    Adapters.Hyprland { id: workspaceCompositor }
    Modules.NotificationService { id: notificationService }
    Modules.Topbar {
        id: topbar
        compositor: mockCompositor
        notificationService: mockNotifications
        session: mockSession
        keyboard: mockKeyboard
        sessionLocked: mockSession.locked
        function focusedScreenName() { return "DP-1" } // Offscreen output has no name.
    }
    QtObject {
        id: mockKeyboard
        property bool busy: false
        property int opens: 0
        function hide() {}
        function show() { opens++ }
    }
    Process {
        id: preferenceWriter
        command: ["python3", "-c",
            "import os,sys; p=sys.argv[1]; open(p+'.next','w').write(sys.argv[2]); os.replace(p+'.next',p)",
            Quickshell.env("XDG_STATE_HOME") + "/icewine/widgets.json", preferenceWriter.contents]
        property string contents: ""
    }
    QtObject {
        id: mockCompositor
        property var toplevels: [a, b, c]
        property string activeWindowAddress: "0x2"
        property bool suppressed: false
        property string restored: ""
        signal navigationRequested()
        signal monitorsChanged()
        signal configReloaded()
        function supress_mouse_binds(value) { suppressed = value }
        function activateWindow(address) { restored = address }
        function activateToplevel(target) {
            if (toplevels.includes(target)) { restored = target.address; activeWindowAddress = target.address }
        }
        property var fullscreenScreens: []
        function monitorFor(screen) { return {focused:true} }
    }
    QtObject { id: ws1; property int id: 1; property string name: "1"; property var monitor: ({name: "DP-1"}) }
    QtObject { id: ws3; property int id: 3; property string name: "3"; property var monitor: ({name: "DP-1"}) }
    QtObject { id: a; property string address: "0x1"; property string title: "First"; property var workspace: ws1; property var wayland: null }
    QtObject { id: b; property string address: "0x2"; property string title: "Selected"; property var workspace: ws1; property var wayland: null }
    QtObject { id: c; property string address: "0x3"; property string title: "Third"; property var workspace: ws3; property var wayland: null }
    QtObject { id: d; property string address: "0x4"; property string title: "Fourth"; property var workspace: ws1; property var wayland: null }
    Component {
        id: fixtureMonitor
        QtObject {
            property string name
            property bool focused: true
            property var activeWorkspace
            property var lastIpcObject: ({specialWorkspace: {id: 0}})
        }
    }
    Component {
        id: fixtureWorkspace
        QtObject {
            property int id
            property string name: String(id)
            property var monitor
            property bool active: false
            property bool hasFullscreen: false
            property var toplevels: QtObject { property var values: [] }
            function activate() { Hyprland.activatedWorkspace = id }
        }
    }
    Window {
        id: workspaceWindow
        width: 1280; height: 720; visible: true
        Item {
            id: workspacePanel
            anchors.fill: parent
            property var screen: ({name: "DP-1"})
            readonly property bool widgetHere: topbar.ui.page !== "" && topbar.ui.screen === screen.name
            property var barWindow: workspaceWindow
            __PANEL_FOCUS__
            // Observe actual QML setter/activation ordering using only the grab
            // protocol contract. This is NOT compositor keyboard-enter evidence.
            QtObject {
                id: widgetGrab
                property bool active: __GRAB_ACTIVE__
                property var windows: __GRAB_WINDOWS__
                property var entered: workspacePanel.barWindow
                onWindowsChanged: {
                    if (!windows.length) throw new Error("Acquisition dropped the grab")
                    if (!windows.includes(entered)) entered = windows[windows.length - 1]
                }
                __GRAB_ACTIVATED__
            }
            Connections {
                target: topbar
                __FOCUS_REQUESTED__
            }
            readonly property string hoverPage: __HOVER_PAGE__
            __HOVER_SCHEDULER__
            __WORKSPACE_SURFACE__
            Bar.Widget {
                id: interactionCard
                y: 70; width: 350; height: 100
                shown: topbar.ui.page !== "" && topbar.ui.page !== "switcher"
                engaged: topbar.widgetEngaged
                onEngageRequested: topbar.engageWidget()
                onDismissRequested: topbar.dismissWidget()
                Slider { id: interactionSlider; x: 20; y: 20; width: 250 }
            }
        }
    }
    Window {
        id: keyboardActionWindow
        visible: false
        width: 420; height: 500
        Bar.StatusIcons {
            id: keyboardIcons
            notificationService: notificationService
            cardStacks: []
            visible: topbar.barVisible
            onKeyboardRequested: topbar.showKeyboard("topbar")
        }
        Bar.StatusPopout {
            id: keyboardLauncher
            y: 40; width: 400; height: 424
            compositor: mockCompositor
            notificationService: notificationService
            cardStacks: [{id: "held-action", modules: ["launcher"]}]
            currentPage: "launcher"
            shown: topbar.ui.page === "launcher"
            engaged: topbar.widgetEngaged
            backgroundItems: []
            onKeyboardRequested: topbar.showKeyboard("launcher")
        }
    }
    Window {
        id: window
        width: 420; height: 280; visible: true
        property int activations: 0
        property int dismissals: 0
        property var activated: null
        Loader {
            id: loader
            anchors.fill: parent
            sourceComponent: Modules.WindowSwitcher {
                compositor: mockCompositor
                monitorName: "DP-1"
                onActivateRequested: selected => { ++window.activations; window.activated = selected }
                onDismissRequested: ++window.dismissals
            }
        }
        // The real Topbar loader, in panel-local logical coordinates. Native
        // layer surfaces and input regions still require compositor checks.
        Item {
            id: geometryHost
            x: 137; y: 91
            width: 1920; height: 1080
            property var screen: ({name: "DP-1"})
            property bool widgetHere: false
            __SIZING_LOADER__
        }
        Component {
            id: fixtureWindow
            QtObject {
                property string address
                property string title
                property var workspace
                property var wayland: null
            }
        }
        Button { id: otherControl; text: "Other top-bar control" }
        TestCase {
            id: keys
            when: false
            function descendants(item, predicate) {
                let result = predicate(item) ? [item] : []
                for (const child of item.children ?? []) result = result.concat(descendants(child, predicate))
                return result
            }
            function selectedCardVisible(target = loader) {
                const card = descendants(target.item, item => item.modelData === target.item.selected
                    && item.border !== undefined)[0]
                if (!card) return false
                const position = card.mapToItem(target.item, 0, 0)
                return position.x >= 16 && position.x + card.width <= target.width - 15
                    && position.y >= 16 && position.y + card.height <= target.height - 15
            }
            function centeredAndBounded() {
                return Math.abs(sizedLoader.x * 2 + sizedLoader.width - geometryHost.width) < 1
                    && Math.abs(sizedLoader.y * 2 + sizedLoader.height - geometryHost.height) < 1
                    && sizedLoader.x >= Math.min(24, geometryHost.width / 20) - 1
                    && sizedLoader.y >= Math.min(24, geometryHost.height / 20) - 1
                    && sizedLoader.width <= 1000 && sizedLoader.height <= 720
                    && sizedLoader.width <= geometryHost.width && sizedLoader.height <= geometryHost.height
            }
            function workspacesAfterUnlock() {
                Config.Settings.widgetSelections = {barBehaviour: "keyboard", barWidth: 100}
                const secondary = fixtureMonitor.createObject(shell, {name: "DP-2"})
                let primary = fixtureMonitor.createObject(shell, {name: "DP-1"})
                const first = fixtureWorkspace.createObject(shell, {id: 1, monitor: primary})
                const second = fixtureWorkspace.createObject(shell, {id: 3, monitor: primary})
                const other = fixtureWorkspace.createObject(shell, {id: 8, monitor: secondary})
                primary.activeWorkspace = first; secondary.activeWorkspace = other
                Hyprland.monitors.values = [primary, secondary]
                Hyprland.workspaces.values = [first, second, other]
                workspacePanel.screen = {name: "DP-1"}
                function buttons() {
                    return descendants(workspaces, item => item.workspaceId !== undefined)
                }
                function shown(ids, active) {
                    verify(topbar.barVisible && surface.opacity === 1, "Whole bar recovered")
                    compare(workspaces.workspaceIds.join(","), ids.join(","), "Output workspace model recovered")
                    compare(buttons().length, ids.length)
                    verify(workspaces.width > 9 && workspaces.height > 0, "Workspace component has geometry")
                    verify(workspaceScroll.width > 0 && workspaceScroll.width >= workspaces.width,
                        "Workspace buttons are not clipped")
                    verify(surface.y >= 0 && surface.y + surface.height <= workspacePanel.height)
                    compare(workspaces.activeId, active)
                    compare(buttons().filter(button => button.active).length, 1)
                }
                topbar.pressBar()
                wait(200)
                shown([1,3], 1)
                const original = workspaces
                for (let cycle = 0; cycle < 3; ++cycle) {
                    mockSession.beginLock()
                    verify(mockSession.locked && !topbar.barVisible)
                    compare(workspaces, original, "Lock hides rather than destroys workspace component")
                    if (cycle === 1) {
                        // Real QObject invalidation, same ShellScreen identity.
                        Hyprland.monitors.values = [secondary]
                        first.monitor = null; second.monitor = null
                        primary.destroy()
                        wait(1)
                        primary = fixtureMonitor.createObject(shell, {name: "DP-1", activeWorkspace: second})
                        Hyprland.monitors.values = [primary, secondary]
                        first.monitor = primary; second.monitor = primary
                    } else if (cycle === 2) {
                        first.monitor = secondary
                        primary.activeWorkspace = second
                    }
                    mockSession.fixturePam.completed(PamResult.Success)
                    verify(!mockSession.locked)
                    topbar.pressBar()
                    wait(200)
                    shown(cycle === 2 ? [3] : [1,3], cycle === 0 ? 1 : 3)
                    const occupied = buttons().find(button => button.workspaceId === 3)
                    second.toplevels.values = [b]
                    tryCompare(occupied, "occupied", true)
                    second.toplevels.values = []
                    tryCompare(occupied, "occupied", false)
                    mouseClick(occupied, occupied.width / 2, occupied.height / 2)
                    compare(Hyprland.activatedWorkspace, 3, "Real workspace TapHandler activates after unlock")
                    Hyprland.activatedWorkspace = 0
                }
                // Screen replacement and a monitor arriving after its screen.
                workspacePanel.screen = {name: "DP-2"}
                wait(200)
                shown([1,8], 8)
                workspacePanel.screen = {name: "DP-3"}
                tryCompare(workspaces, "monitor", null)
                const added = fixtureMonitor.createObject(shell, {name: "DP-3", activeWorkspace: second})
                second.monitor = added
                Hyprland.monitors.values = [primary, secondary, added]
                wait(200)
                shown([3], 3)
                // Same-object active-workspace notifications remain reactive.
                added.activeWorkspace = first; first.monitor = added
                wait(200)
                shown([1,3], 1)
                topbar.dismiss(false)
                workspaceWindow.visible = false
                console.log("WORKSPACES_UNLOCK_PASSED")
            }
            function sizing() {
                geometryHost.widgetHere = true
                topbar.openWidget("switcher", true, "DP-1")
                tryVerify(() => sizedLoader.item !== null)
                const view = sizedLoader.item
                tryVerify(centeredAndBounded)
                const emptyHeight = sizedLoader.height
                mockCompositor.toplevels = [a]
                tryVerify(() => sizedLoader.height > emptyHeight)
                const singleWidth = sizedLoader.width
                const singleHeight = sizedLoader.height
                mockCompositor.toplevels = [a, b, d]
                tryVerify(() => sizedLoader.width > singleWidth)
                compare(sizedLoader.height, singleHeight)
                mockCompositor.toplevels = [a, b, d, c]
                tryVerify(() => sizedLoader.height > singleHeight)
                const many = []
                for (let row = 1; row <= 4; ++row)
                    for (let column = 0; column < 6; ++column)
                        many.push(fixtureWindow.createObject(window, {
                            address: row + ":" + column, title: "Window " + row + ":" + column,
                            workspace: {id: row, name: String(row), monitor: {name: "DP-1"}}}))
                mockCompositor.toplevels = many
                tryVerify(() => sizedLoader.width > singleWidth && sizedLoader.height > singleHeight)
                // Shrink and regrow with an offscreen selection; size is not a bar mode.
                for (const size of [[1920,1080], [320,200], [1280,720]]) {
                    geometryHost.width = size[0]; geometryHost.height = size[1]
                    view.selected = many[many.length - 1]
                    tryVerify(centeredAndBounded)
                    tryVerify(() => selectedCardVisible(sizedLoader), 2000,
                        "Last card visible after output resize")
                    view.navigate(0, -1)
                    tryVerify(() => selectedCardVisible(sizedLoader), 2000,
                        "Workspace navigation scrolls selected card into view")
                    view.navigate(-1, 0)
                    tryVerify(() => selectedCardVisible(sizedLoader))
                    const scrolls = descendants(view, item => item.contentX !== undefined
                        && item.contentY !== undefined)
                    for (const scroll of scrolls) {
                        verify(scroll.contentX >= -1 && scroll.contentY >= -1)
                        verify(scroll.contentX <= Math.max(0, scroll.contentWidth - scroll.width) + 1)
                        verify(scroll.contentY <= Math.max(0, scroll.contentHeight - scroll.height) + 1)
                    }
                }
                geometryHost.width = 1920; geometryHost.height = 1080
                mockCompositor.toplevels = [a]
                tryCompare(sizedLoader, "width", singleWidth)
                tryCompare(sizedLoader, "height", singleHeight)
                tryVerify(() => selectedCardVisible(sizedLoader))
                mockCompositor.toplevels = []
                tryCompare(sizedLoader, "height", emptyHeight)
                tryCompare(view, "selected", null)
                tryVerify(centeredAndBounded)
                topbar.dismissWidget()
                tryVerify(() => sizedLoader.item === null, 2000, "Closing destroys preview owner")
                geometryHost.widgetHere = false
                for (const item of many) item.destroy()
                console.log("SWITCHER_SIZING_PASSED")
            }
            function fullscreenFlow() {
                // Native special-workspace facts: active=false, visibility comes
                // from the monitor snapshot, and that snapshot notifies readers.
                const monitor = fixtureMonitor.createObject(shell, {name: "DP-1"})
                const special = fixtureWorkspace.createObject(shell, {id: -99, monitor: monitor, hasFullscreen: true})
                const inactive = fixtureWorkspace.createObject(shell, {id: 3, monitor: monitor, hasFullscreen: true})
                Hyprland.monitors.values = [monitor]
                Hyprland.workspaces.values = [special, inactive]
                compare(workspaceCompositor.fullscreenScreens.length, 0)
                monitor.lastIpcObject = {specialWorkspace: {id: -99}}
                compare(workspaceCompositor.fullscreenScreens.join(","), "DP-1")
                const before = Hyprland.monitorRefreshes
                Hyprland.rawEvent({name: "activespecialv2"})
                tryCompare(Hyprland, "monitorRefreshes", before + 1)
                monitor.lastIpcObject = {specialWorkspace: {id: 0}}
                tryCompare(Hyprland, "monitorRefreshes", before + 2)
                compare(workspaceCompositor.fullscreenScreens.length, 0)

                Config.Settings.widgetSelections = {barBehaviour: "toggle"}
                topbar.dismiss(false)
                topbar.pressBar()
                mockCompositor.fullscreenScreens = ["DP-1"]
                verify(topbar.barVisible && !topbar.ui.latched, "Conversion is synchronous, before release or exit")
                mockCompositor.fullscreenScreens = []
                topbar.openWidget("audio", true, "DP-2")
                topbar.releaseBar()
                verify(!topbar.ui.latched && topbar.ui.screen === "DP-2", "Release preserves independent widget")
                topbar.dismiss(false)
                topbar.pressBar()
                wait(1)
                verify(topbar.ui.latched && topbar.ui.held.toggle, "No stale callback can alter a later ordinary chord")
                topbar.dismiss(false)
                console.log("FULLSCREEN_FLOW_PASSED")
            }
            function check() {
                // A pending OSK request is the sole owner after physical release.
                // Cancelling it on explicit focus must not restore the old app.
                Config.Settings.widgetSelections = {barBehaviour: "keyboard", oskAccess: "topbar"}
                topbar.dismiss(false)
                mockCompositor.activeWindowAddress = b.address
                mockCompositor.restored = ""
                topbar.barModifiersHeld = 1
                topbar.pressBar()
                topbar.showKeyboard("topbar")
                topbar.releaseBar()
                verify(topbar.keyboardRequest?.awaitingRelease && topbar.interactionWanted)
                mockCompositor.activeWindowAddress = a.address
                compare(topbar.keyboardRequest, null)
                wait(1)
                compare(mockCompositor.restored, "", "Explicit focus wins over cancellation of the final owner")
                topbar.barModifiersHeld = 0
                mockCompositor.activeWindowAddress = b.address
                topbar.pressBar()
                topbar.releaseBar() // Queue ordinary restoration before the app choice.
                mockCompositor.activeWindowAddress = a.address
                wait(1)
                compare(mockCompositor.restored, "", "Explicit focus also cancels already queued restoration")
                fullscreenFlow()
                workspacesAfterUnlock()
                cardSwitching()
                // Keep the real session/PAM-result handlers and topbar bindings.
                // Only native lock delivery is replaced: acquisition notifies,
                // unlock changes the getter without a notification (qs 0.3.2).
                mockSession.fixtureNativeLock = {locked: true, secure: true}
                verify(mockSession.locked, "A native lock still guards UI without recorded intent")
                mockSession.beginLock()
                verify(mockSession.lockRequested, "Existing native ownership still records new intent")
                mockSession.fixturePam.completed(PamResult.Success)
                verify(!mockSession.locked, "Shared entry restores release notification even for native-only state")
                mockSession.fixtureNativeLock = {locked: false, secure: false}
                mockCompositor.restored = ""
                topbar.openWidget("launcher", true, "DP-1")
                topbar.pressBar()
                verify(topbar.barVisible && topbar.widgetEngaged)
                mockSession.beginLock()
                verify(mockSession.locked && mockSession.lockRequested)
                verify(!topbar.barVisible && !topbar.widgetEngaged)
                compare(topbar.ui.page, "")
                verify(!topbar.ui.held && !mockCompositor.suppressed)
                topbar.pressBar()
                topbar.toggleSwitcher()
                topbar.openWidget("audio", true, "DP-1")
                verify(!topbar.barVisible && !topbar.ui.held && !topbar.ui.page)
                mockSession.password = "fixture response"
                mockSession.authenticating = true
                let clearAtIdle = false
                const observeCompletion = () => {
                    if (!mockSession.authenticating) clearAtIdle = !mockSession.password
                }
                mockSession.authenticatingChanged.connect(observeCompletion)
                mockSession.fixturePam.completed(PamResult.Success + 1)
                verify(clearAtIdle, "Completed response clears before input becomes ready")
                verify(mockSession.locked && mockSession.failed && !mockSession.password)
                verify(!mockSession.authenticating && !topbar.barVisible)
                mockSession.password = "successful fixture response"
                mockSession.authenticating = true
                clearAtIdle = false
                mockSession.fixturePam.completed(PamResult.Success)
                verify(clearAtIdle, "Successful response clears before input becomes ready")
                mockSession.authenticatingChanged.disconnect(observeCompletion)
                verify(!mockSession.locked && !mockSession.lockRequested,
                    "Successful unlock releases every UI guard without native notify")
                verify(!mockSession.password && !mockSession.failed && !mockSession.authenticating)
                wait(1)
                compare(mockCompositor.restored, "", "Lock handoff cancels old focus restoration")
                topbar.pressBar()
                verify(topbar.barVisible && topbar.ui.held, "Hold opens after unlock")
                topbar.releaseBar()
                verify(!topbar.barVisible && !topbar.ui.held, "Release hides after unlock")
                topbar.toggleSwitcher()
                compare(topbar.ui.page, "switcher")
                topbar.toggleSwitcher()
                compare(topbar.ui.page, "")
                // Mode changes share one native interaction/focus lifetime.
                // Layer placement is covered by bar-geometry, not repeated here.
                for (const behaviour of ["keyboard", "keyboard-mouse", "toggle", "always"]) {
                    Config.Settings.widgetsFile.setText(JSON.stringify({barBehaviour: behaviour, barLocation: "above"}))
                    Config.Settings.widgetsFile.reload()
                    tryCompare(Config.Settings, "barBehaviour", behaviour)
                    topbar.dismiss(false)
                    topbar.pressBar(); topbar.releaseBar()
                    const visible = behaviour === "toggle" || behaviour === "always"
                    compare(topbar.barVisible, visible)
                    mockCompositor.restored = ""
                    topbar.toggleSwitcher()
                    compare(topbar.ui.page, "switcher")
                    compare(topbar.barVisible, visible, "Switcher adds no visibility owner")
                    topbar.activateSwitcherWindow(b)
                    wait(1)
                    compare(mockCompositor.restored, b.address)
                    topbar.openWidget("audio", true, "DP-1")
                    topbar.instantHandoff()
                    wait(1)
                    compare(topbar.barVisible, behaviour === "always")
                    verify(!topbar.interactionActive && !topbar.widgetEngaged)
                    topbar.handoff(true)
                    verify(!topbar.barVisible, "Capture suppression overrides every mode")
                    mockCompositor.navigationRequested()
                    compare(topbar.barVisible, behaviour === "always")
                }
                // Actual Topbar bindings/signals/timer; native layer focus remains a device check.
                Config.Settings.widgetsFile.blockWrites = true
                for (const mode of ["launcher", "topbar"]) {
                    Config.Settings.widgetsFile.setText(JSON.stringify({oskAccess: mode, barBehaviour: "always"}))
                    Config.Settings.widgetsFile.reload()
                    tryCompare(Config.Settings, "oskAccess", mode)
                    topbar.openWidget("launcher", true, "DP-1")
                    const original = topbar.previousToplevel
                    verify(original !== null)
                    const count = mockKeyboard.opens
                    topbar.showKeyboard(mode)
                    verify(!topbar.widgetEngaged && !topbar.interactionActive && topbar.barVisible)
                    tryCompare(mockKeyboard, "opens", count + 1)
                    compare(mockCompositor.restored, original.address)
                    compare(topbar.keyboardRequest, null)
                    topbar.openWidget("launcher", true, "DP-1")
                    topbar.showKeyboard(mode)
                    topbar.sessionLocked = true
                    wait(80)
                    compare(mockKeyboard.opens, count + 1, "Lock cancels deferred desktop request")
                    topbar.sessionLocked = Qt.binding(() => mockSession.locked)
                    topbar.openWidget("launcher", true, "DP-1")
                    topbar.showKeyboard(mode)
                    Config.Settings.widgetSelections = {oskAccess: "none", barBehaviour: "always"}
                    wait(80)
                    compare(topbar.keyboardRequest, null)
                    compare(mockKeyboard.opens, count + 1, "Mode change cancels pending request")
                }
                // Regression: real icon/result pointer handlers under default hold-to-show.
                keyboardActionWindow.visible = true
                keyboardActionWindow.requestActivate()
                tryCompare(keyboardActionWindow, "active", true)
                for (const mode of ["topbar", "launcher"]) for (const touch of [false, true]) {
                    Config.Settings.widgetsFile.setText(JSON.stringify({oskAccess: mode, barBehaviour: "keyboard"}))
                    Config.Settings.widgetsFile.reload()
                    tryCompare(Config.Settings, "oskAccess", mode)
                    tryCompare(Config.Settings, "barBehaviour", "keyboard")
                    topbar.dismiss(false)
                    topbar.barModifiersHeld = 1 // Native topbarModifier press stand-in.
                    topbar.pressBar()
                    let button
                    if (mode === "launcher") {
                        topbar.openWidget("launcher", true, "DP-1")
                        tryVerify(() => keyboardLauncher.cardFor("launcher") !== null)
                        keyboardLauncher.focusInitial()
                        keyboardLauncher.cardFor("launcher").initialFocus.text = "osk"
                        const results = descendants(keyboardLauncher, item => item instanceof ListView)[0]
                        tryVerify(() => results.currentItem?.entry?.action === "keyboard")
                        button = results.currentItem
                    } else button = descendants(keyboardIcons, item => item.page === "keyboard")[0]
                    verify(button.visible)
                    wait(220) // Let popup reveal/row positioning finish before pointer delivery.
                    const count = mockKeyboard.opens
                    const original = topbar.previousToplevel
                    if (touch) {
                        const pointer = touchEvent(keyboardActionWindow)
                        pointer.press(0, button, 8, 8).commit()
                        pointer.release(0, button, 8, 8).commit()
                    } else {
                        mouseClick(button, 8, 8, Qt.LeftButton, Qt.MetaModifier)
                    }
                    if (!topbar.keyboardRequest) throw new Error("Held action dropped: " + mode + "/" + touch
                        + " held=" + topbar.ui.held + " modifiers=" + topbar.barModifiersHeld
                        + " previous=" + topbar.previousToplevel?.address)
                    compare(topbar.keyboardRequest.window, original)
                    verify(topbar.keyboardRequest.awaitingRelease)
                    const request = topbar.keyboardRequest
                    topbar.pressBar()
                    compare(topbar.keyboardRequest, request, "Repeat preserves the pending action")
                    wait(80)
                    compare(mockKeyboard.opens, count, "No keyboard while opening modifier is held")
                    if (!touch) {
                        topbar.releaseBar() // grave released first; Super remains down.
                        compare(topbar.ui.held, null)
                        wait(80)
                        verify(topbar.keyboardRequest?.awaitingRelease)
                        compare(mockKeyboard.opens, count)
                    }
                    topbar.barModifiersHeld = 0 // Native topbarModifier release stand-in.
                    topbar.releaseBar()
                    tryCompare(mockKeyboard, "opens", count + 1)
                    compare(mockCompositor.restored, original.address)
                    compare(topbar.keyboardRequest, null)
                    topbar.releaseBar(); wait(40)
                    compare(mockKeyboard.opens, count + 1, "Second release does not replay activation")
                }
                topbar.barModifiersHeld = 1
                topbar.pressBar()
                topbar.showKeyboard("launcher")
                verify(topbar.keyboardRequest?.awaitingRelease)
                const beforeLock = mockKeyboard.opens
                topbar.sessionLocked = true
                compare(topbar.keyboardRequest, null)
                compare(topbar.barModifiersHeld, 0, "Lock cannot leave stale modifier ownership")
                topbar.sessionLocked = Qt.binding(() => mockSession.locked)
                topbar.releaseBar(); wait(80)
                compare(mockKeyboard.opens, beforeLock, "Lock cancels held intent before release")
                keyboardActionWindow.visible = false
                window.requestActivate()
                tryCompare(window, "active", true)
                Config.Settings.widgetsFile.setText("{}")
                Config.Settings.widgetsFile.reload()
                tryCompare(Config.Settings, "barBehaviour", "keyboard")
                tryCompare(Config.Settings, "barLocation", "above")
                mockSession.lockRequested = true
                verify(mockSession.locked, "Pending acquisition already guards UI")
                topbar.pressBar()
                verify(!topbar.barVisible && !topbar.ui.held)
                mockSession.lockRequested = false
                console.log("SESSION_LOCK_GUARDS_PASSED")
                const view = loader.item
                view.forceActiveFocus()
                tryVerify(() => view.activeFocus)
                compare(view.selected, b)
                tryVerify(() => descendants(view, item => item.text === "Selected"
                    && item.wrapMode === Text.Wrap && item.visible).length > 0, 2000, "Unavailable preview has visible fallback")
                keyRelease(Qt.Key_Return)
                compare(window.activations, 0, "Opening release is inert")
                keyPress(Qt.Key_Return)
                keyClick(Qt.Key_Left)
                compare(view.selected, a)
                keyRelease(Qt.Key_Return)
                compare(window.activated, b, "Activate the pressed window despite selection changing")
                compare(window.activations, 1)
                view.selected = b
                keyPress(Qt.Key_Return)
                mockCompositor.toplevels = [a, c]
                tryCompare(view, "selected", a)
                keyRelease(Qt.Key_Return)
                compare(window.activations, 1, "Closed armed window is not replaced")
                keyPress(Qt.Key_Return)
                view.focus = false
                window.contentItem.forceActiveFocus()
                tryVerify(() => !view.activeFocus)
                view.forceActiveFocus()
                keyRelease(Qt.Key_Return)
                compare(window.activations, 1, "Focus loss cancels activation")
                keyClick(Qt.Key_Escape)
                compare(window.dismissals, 1)
                otherControl.forceActiveFocus()
                tryVerify(() => otherControl.activeFocus)
                keyClick(Qt.Key_Escape)
                compare(window.dismissals, 2, "Escape dismisses after focus leaves the window cards")
                view.forceActiveFocus()
                mockCompositor.toplevels = [a, b, d, c]
                tryVerify(() => view.rows[0].windows.length === 3)
                view.selected = a
                keyClick(Qt.Key_Right)
                keyClick(Qt.Key_Right)
                compare(view.selected, d)
                tryVerify(selectedCardVisible, 2000, "Selected card is visible after horizontal navigation")
                keyClick(Qt.Key_Down)
                compare(view.selected, c)
                tryVerify(selectedCardVisible, 2000, "Selected card is visible after workspace navigation")
                const selectedCard = descendants(view, item => item.modelData === c && item.border !== undefined)[0]
                otherControl.forceActiveFocus()
                mouseClick(selectedCard, selectedCard.width / 2, selectedCard.height / 2)
                compare(view.selected, c)
                tryVerify(() => view.activeFocus, 2000, "Visible card click restores selector focus on 420x280")
                mockCompositor.toplevels = []
                tryVerify(() => view.rows.length === 0)
                keyClick(Qt.Key_Return)
                compare(window.activations, 1, "Empty switcher cannot activate a stale selection")
                sizing()
                // Actual settings watcher and retained service/controller state;
                // native layer/capture teardown remains a real-session check.
                mockCompositor.toplevels = [b]
                verify(Config.Settings.notificationToasts && Config.Settings.windowSwitcher)
                notificationService.popups = [{transient:false, tracked:true}]
                topbar.openWidget("switcher", true, "DP-1")
                verify(topbar.widgetEngaged && mockCompositor.suppressed)
                preferenceWriter.contents = '{"notificationToasts":false,"windowSwitcher":false}'
                preferenceWriter.running = true
                tryVerify(() => !preferenceWriter.running)
                tryVerify(() => !Config.Settings.windowSwitcher)
                compare(topbar.ui.page, "")
                verify(!topbar.widgetEngaged && !mockCompositor.suppressed)
                tryCompare(mockCompositor, "restored", "0x2")
                compare(notificationService.popups.length, 0)
                topbar.openWidget("switcher", true, "DP-1")
                compare(topbar.ui.page, "", "Disabled switcher cannot reopen")
                preferenceWriter.contents = '{"windowSwitcher":"false"}'
                preferenceWriter.running = true
                tryVerify(() => !preferenceWriter.running)
                wait(100)
                verify(!Config.Settings.windowSwitcher)
                preferenceWriter.contents = '{"notificationToasts":true,"windowSwitcher":true}'
                preferenceWriter.running = true
                tryVerify(() => !preferenceWriter.running)
                tryVerify(() => Config.Settings.windowSwitcher)
                console.log("SWITCHER_PASSED")
                Qt.quit()
            }
            function cardSwitching() {
                workspaceWindow.visible = true
                workspaceWindow.requestActivate()
                tryCompare(workspaceWindow, "active", true)
                workspacePanel.screen = {name: "DP-1"}
                for (const [behaviour, location] of [["keyboard-mouse", "top"], ["always", "bottom"]]) {
                    Config.Settings.widgetSelections = {barBehaviour: behaviour, barLocation: location, barWidth: 100}
                    topbar.pressBar()
                    wait(200)
                    const audio = descendants(statusIcons, item => item.page === "audio")[0]
                    const network = descendants(statusIcons, item => item.page === "network")[0]
                    const targets = [[logo, "launcher"], [audio, "audio"], [network, "network"], [logo, "launcher"]]
                    topbar.openWidget("network", false, "DP-1")
                    for (const [icon, page] of targets) {
                        // The shipped Widget PointHandler sees a real native control
                        // press before the delayed preview of another visible icon.
                        mouseMove(interactionSlider, 80, interactionSlider.height / 2)
                        mouseClick(interactionSlider, 80, interactionSlider.height / 2)
                        verify(topbar.widgetEngaged)
                        mouseMove(icon, 10, 10)
                        widgetGrab.entered = workspacePanel.barWindow
                        mouseClick(icon, 10, 10)
                        compare(topbar.ui.page, page, "Click switches immediately after card input")
                        verify(topbar.widgetEngaged)
                        tryCompare(widgetGrab, "entered", workspacePanel, 1000, "Explicit open acquires the widget even if the bar was entered")
                        verify(widgetGrab.windows.includes(workspacePanel.barWindow))
                        mouseMove(interactionSlider, 80, interactionSlider.height / 2)
                        mouseClick(interactionSlider, 80, interactionSlider.height / 2)
                        const [hoverIcon, hoverPage] = page === "launcher" ? [audio, "audio"] : [logo, "launcher"]
                        mouseMove(hoverIcon, 10, 10)
                        wait(200)
                        if (topbar.ui.page !== hoverPage) throw new Error(behaviour + "/" + location + ": wanted=" + hoverPage
                            + " actual=" + topbar.ui.page + " hover=" + workspacePanel.hoverPage
                            + " bar=" + topbar.barVisible)
                        verify(!topbar.widgetEngaged, "Hover opens a normal preview after card input")
                        widgetGrab.entered = workspacePanel.barWindow
                        mouseMove(interactionSlider, 80, interactionSlider.height / 2)
                        mouseClick(interactionSlider, 80, interactionSlider.height / 2)
                        tryCompare(widgetGrab, "entered", workspacePanel, 1000, "Preview engagement activation acquires native keyboard destination")
                        mouseMove(hoverIcon, 10, 10)
                        mouseClick(hoverIcon, 10, 10)
                        compare(topbar.ui.page, hoverPage)
                        verify(topbar.widgetEngaged, "Click engages the destination immediately")
                        verify(topbar.ui.held, "Switching preserves the opening chord")
                    }
                    topbar.releaseBar()
                    verify(!topbar.ui.held && topbar.widgetEngaged)
                    interactionCard.forceActiveFocus()
                    keyPress(Qt.Key_Escape)
                    verify(topbar.widgetEngaged, "Escape acts on release")
                    keyRelease(Qt.Key_Escape)
                    compare(topbar.ui.page, "")
                    topbar.handoff(true)
                    wait(200)
                    verify(!topbar.barVisible)
                }
                workspaceWindow.visible = false
                Config.Settings.widgetSelections = {}
                topbar.dismiss(false)
                window.requestActivate()
                tryCompare(window, "active", true)
                console.log("CARD_SWITCHING_PASSED")
            }
        }
        Timer {
            interval: 100; running: true
            onTriggered: {
                try { keys.check() }
                catch (error) { console.error("Switcher check failed:", error, error.stack); Qt.exit(1) }
            }
        }
    }
}
'''
with tempfile.TemporaryDirectory(prefix='.switcher-check-') as directory:
    root = Path(directory)
    (root / 'icewine').mkdir()
    # Disposable QML copies must be writable even when source is in the store.
    shutil.copytree(source / 'quickshell/modules', root / 'icewine/modules', copy_function=shutil.copyfile)
    shutil.copytree(source / 'quickshell/adapters', root / 'icewine/adapters', copy_function=shutil.copyfile)
    adapter_source = root / 'icewine/adapters/Hyprland.qml'
    adapter_source.write_text(adapter_source.read_text().replace(
        'import Quickshell.Hyprland', 'import HyprlandFixtures'))
    fixtures = root / 'HyprlandFixtures'
    fixtures.mkdir()
    (fixtures / 'qmldir').write_text('module HyprlandFixtures\nsingleton Hyprland 1.0 Hyprland.qml\n')
    (fixtures / 'Hyprland.qml').write_text('''pragma Singleton
import QtQuick
QtObject {
    id: native
    property var monitors: ListModel {
        property var values: []
        onValuesChanged: {
            native.lookup.values = values
            clear()
            for (const monitor of values) append({modelData: monitor})
        }
    }
    property var workspaces: QtObject { property var values: [] }
    property var toplevels: QtObject { property var values: [] }
    property var activeToplevel: null
    property var focusedMonitor: null
    property var focusedWorkspace: null
    property bool usingLua: true
    property int monitorRefreshes: 0
    function refreshMonitors() { ++monitorRefreshes }
    property int activatedWorkspace: 0
    signal rawEvent(var event)
    // Model the C++ invokable's unobservable ObjectModel::valueList() read.
    // Mutating this JS field has no notifier, unlike monitors.values.
    readonly property var lookup: ({values: []})
    function monitorFor(screen) {
        return lookup.values.find(monitor => monitor.name === screen?.name) ?? null
    }
    function dispatch(request) {}
}
''')
    notification_source = root / 'icewine/modules/NotificationService.qml'
    notification_source.write_text(notification_source.read_text().replace(
        "import Quickshell.Services.Notifications", "import NotificationFixtures"))
    fixtures = root / 'NotificationFixtures'
    fixtures.mkdir()
    (fixtures / 'qmldir').write_text("module NotificationFixtures\nNotificationServer 1.0 NotificationServer.qml\n")
    (fixtures / 'NotificationServer.qml').write_text("""import Quickshell
Scope {
    property var trackedNotifications: ({values:[]})
    property bool keepOnReload: false
    property bool persistenceSupported: false
    property bool actionsSupported: false
    property bool imageSupported: false
    signal notification(var notification)
}
""")
    session_source = root / 'icewine/modules/SessionControl.qml'
    native_session = session_source.read_text()
    # A JS object's fields have no QML notifier. Replacing the object on acquire
    # but mutating it on unlock models the native getter/NOTIFY mismatch, without
    # acquiring a compositor lock or starting a PAM conversation. An alias read
    # is represented by its equivalent binding so it can target the JS getter.
    native_session = native_session.replace('property alias locked: sessionLock.locked',
        'readonly property bool locked: sessionLock.locked')
    native_session = native_session.replace('    property string password: ""',
        '    property var fixtureNativeLock: ({locked: false, secure: false})\n'
        '    readonly property var fixturePam: pam\n'
        '    readonly property var fixtureLockState: lockState\n'
        '    readonly property var fixtureLockHint: lockHint\n    property string password: ""')
    native_session, count = re.subn(r'^        WlSessionLock \{[\s\S]*?^        \}', '''        Connections {
            target: lockState
            function onAcquiredChanged() {
                if (lockState.acquired) root.fixtureNativeLock = {locked: true, secure: true}
                else {
                    root.fixtureNativeLock.locked = false
                    root.fixtureNativeLock.secure = false
                }
            }
        }''', native_session, flags=re.M)
    assert count == 1, 'Expected one native session-lock boundary'
    # Hold helper completion deterministically for pending intent across real QML reloads.
    native_session, count = re.subn(r'^    Process \{\n        id: lockHint\n', '''    QtObject {
        id: lockHint
        property var command: []
        property bool running: false
        signal exited(int exitCode, int exitStatus)
''', native_session, flags=re.M)
    assert count == 1, 'Expected one hint subprocess boundary'
    session_source.write_text(native_session.replace('sessionLock.', 'root.fixtureNativeLock.'))
    topbar_source = root / 'icewine/modules/Topbar.qml'
    native_topbar = topbar_source.read_text()
    surface_start = native_topbar.index('                Rectangle {\n                    id: surface')
    surface_open = native_topbar.index('{', surface_start)
    surface_end = surface_open + 1
    depth = 1
    while depth:
        depth += (native_topbar[surface_end] == '{') - (native_topbar[surface_end] == '}')
        surface_end += 1
    workspace_surface = native_topbar[surface_start:surface_end].replace('root.', 'topbar.')
    workspace_surface = workspace_surface.replace('panel.', 'workspacePanel.')
    workspace_surface = workspace_surface.replace('compositor: topbar.compositor', 'compositor: workspaceCompositor')
    hover_page = re.search(r'readonly property string hoverPage: (.+)', native_topbar)[1]
    hover_scheduler = re.search(r'            onHoverPageChanged: \{[\s\S]*?^            \}', native_topbar, re.M)[0]
    hover_scheduler += '\n' + re.search(r'            Timer \{\n                id: previewOpen[\s\S]*?^            \}', native_topbar, re.M)[0]
    hover_scheduler = hover_scheduler.replace('root.', 'topbar.').replace('panel.', 'workspacePanel.')
    panel_focus = '\n'.join(re.findall(r'            function (?:acquireKeyboard|focusWidget)\([^\n]*\) \{[\s\S]*?^            \}', native_topbar, re.M))
    panel_focus = re.sub(r'\bpanel\b', 'workspacePanel', panel_focus.replace('root.', 'topbar.'))
    grab_source = native_topbar.split('id: widgetGrab')[1]
    grab_active = re.search(r'active: (.+)', grab_source)[1].replace('root.', 'topbar.').replace('panel.', 'workspacePanel.')
    grab_windows = re.search(r'windows: (.+)', grab_source)[1].replace('panel', 'workspacePanel')
    grab_activated = re.search(r'onActiveChanged: \{[\s\S]*?^                \}', grab_source, re.M)[0].replace('panel', 'workspacePanel')
    focus_requested = re.search(r'function onFocusWidgetRequested\([^\n]*\) \{[\s\S]*?^                \}', native_topbar, re.M)[0].replace('panel.', 'workspacePanel.')
    # Keep actual shared state/IPC/settings methods without Wayland panels or
    # host metric discovery. This does not establish real compositor capture.
    loader_start = native_topbar.index("                Loader {\n                    id: switcher")
    loader_end = native_topbar.index("                Bar.StatusPopout {", loader_start)
    sizing_loader = native_topbar[loader_start:loader_end].replace("id: switcher", "id: sizedLoader")
    sizing_loader = sizing_loader.replace("root.", "topbar.").replace("panel.", "geometryHost.").replace("input.", "geometryHost.")
    sizing_loader = sizing_loader.replace("sourceComponent: WindowSwitcher {", "sourceComponent: Modules.WindowSwitcher {")
    panel_start = native_topbar.index("    Variants {")
    panel_end = native_topbar.index("    IpcHandler {", panel_start)
    topbar_source.write_text((native_topbar[:panel_start]
        + "    QtObject { id: panels; property var instances: [] }\n"
        + native_topbar[panel_end:]).replace("Bar.SystemMetrics { id: metrics }", "QtObject { id: metrics }"))
    (root / 'icewine/theme').symlink_to(root / 'theme')
    (root / 'config').symlink_to(source / 'quickshell/config')
    fixture_config = theme_fixture(source, root)
    (root / 'shell.qml').write_text(qml.replace("__SIZING_LOADER__", sizing_loader)
                                  .replace("__WORKSPACE_SURFACE__", workspace_surface)
                                  .replace("__HOVER_PAGE__", hover_page)
                                  .replace("__HOVER_SCHEDULER__", hover_scheduler)
                                  .replace("__PANEL_FOCUS__", panel_focus)
                                  .replace("__GRAB_ACTIVE__", grab_active)
                                  .replace("__GRAB_WINDOWS__", grab_windows)
                                  .replace("__GRAB_ACTIVATED__", grab_activated)
                                  .replace("__FOCUS_REQUESTED__", focus_requested))
    (root / 'runtime').mkdir(mode=0o700)
    (root / 'state/icewine').mkdir(parents=True)
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QML_IMPORT_PATH=str(root),
               HYPRLAND_INSTANCE_SIGNATURE='', WAYLAND_DISPLAY='',
               DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(root / 'no-session-bus'),
               DBUS_SYSTEM_BUS_ADDRESS='unix:path=' + str(root / 'no-system-bus'),
               XDG_CACHE_HOME=str(root / 'cache'), XDG_RUNTIME_DIR=str(root / 'runtime'),
               XDG_STATE_HOME=str(root / 'state'), ICEWINE_WIDGET_POLICY='{}')
    env["XDG_CONFIG_HOME"] = fixture_config
    result = subprocess.run(['qs', '-p', str(root), '--no-color'], env=env,
                            capture_output=True, text=True, timeout=40)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and 'SWITCHER_PASSED' in output and 'SWITCHER_SIZING_PASSED' in output, output
    assert 'WORKSPACES_UNLOCK_PASSED' in output, output
    assert 'CARD_SWITCHING_PASSED' in output and 'FULLSCREEN_FLOW_PASSED' in output, output
    assert not re.search(r'ReferenceError|TypeError|Binding loop|Unable to assign|not a type', output), output
    # One lightweight mixed policy case exercises both fixed directions against
    # opposing saved choices; nullable user choice was covered by the watcher.
    (root / 'state/icewine/widgets.json').write_text('{"notificationToasts":false,"windowSwitcher":true,"barBehaviour":"keyboard","barLocation":"above"}')
    (root / 'shell.qml').write_text("""import QtQuick
import Quickshell
import qs.config as Config
ShellRoot {
    Timer {
        interval: 100; running: true
        onTriggered: {
            Config.Settings.widgetsFile.waitForJob()
            if (!Config.Settings.notificationToasts || Config.Settings.windowSwitcher
                    || Config.Settings.barBehaviour !== "always" || Config.Settings.barLocation !== "bottom") Qt.exit(1)
            else { console.log("MIXED_POLICY_PASSED"); Qt.quit() }
        }
    }
}
""")
    env["ICEWINE_WIDGET_POLICY"] = '{"notificationToasts":true,"windowSwitcher":false,"barBehaviour":"always","barLocation":"bottom"}'
    result = subprocess.run(['qs', '-p', str(root), '--no-color'], env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and 'MIXED_POLICY_PASSED' in result.stdout + result.stderr, result.stdout + result.stderr
    # Reload the actual SessionControl Scope/PersistentProperties tree while a
    # helper is stalled, then again with an acquired target. No compositor lock.
    (root / 'shell.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Services.Pam
import "icewine/modules" as Modules
ShellRoot {
    PersistentProperties { id: progress; property int stage: 0 }
    Modules.SessionControl { id: session; authenticationRequired: true }
    function verify(value, message = "session reload invariant") {
        if (!value) throw new Error(message)
    }
    Timer {
        interval: 100; running: true
        onTriggered: {
            try {
                if (progress.stage === 0) {
                    session.logindSessionPath = "/org/freedesktop/login1/session/_32"
                    session.beginLock()
                    verify(session.lockRequested && session.locked)
                    verify(!session.fixtureLockState.acquired && session.fixtureLockHint.running)
                    progress.stage = 1
                    Quickshell.reload(false)
                } else if (progress.stage === 1) {
                    verify(session.lockRequested && session.locked, "reload keeps pending intent/UI guard")
                    verify(!session.fixtureLockState.acquired, "pending target is restored before native reload")
                    session.logindSessionPath = "/org/freedesktop/login1/session/_32"
                    session.restoreLock("(<false>,)")
                    verify(session.fixtureLockHint.running, "reload restarts pending persistence")
                    session.fixtureLockHint.running = false
                    session.fixtureLockHint.exited(0, 0)
                    verify(session.fixtureLockState.acquired && session.fixtureNativeLock.locked)
                    progress.stage = 2
                    Quickshell.reload(false)
                } else {
                    verify(session.lockRequested && session.fixtureLockState.acquired,
                        "acquired reload restores both persistent responsibilities")
                    verify(session.locked, "desktop privacy guard survives acquired reload")
                    session.fixturePam.completed(PamResult.Success + 1)
                    verify(session.locked, "failure after reload retains lock")
                    session.fixturePam.completed(PamResult.Success)
                    verify(!session.locked && !session.lockRequested && !session.fixtureLockState.acquired,
                        "success after reload releases target and privacy guard")
                    console.log("SESSION_RELOAD_PASSED")
                    Qt.quit()
                }
            } catch (error) { console.error("Session reload check failed:", error, error.stack); Qt.exit(1) }
        }
    }
}
''')
    result = subprocess.run(['qs', '-p', str(root), '--no-color'], env=env,
                            capture_output=True, text=True, timeout=10)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and 'SESSION_RELOAD_PASSED' in output, output
    assert not re.search(r'ReferenceError|TypeError|Binding loop|Unable to assign|not a type', output), output
    print('Card native hover/click/focus in representative mouse/Always modes, fullscreen special-workspace refresh/hold conversion, switcher bounds/scroll/keys, lock/privacy/reload and workspace lifecycle pass')
