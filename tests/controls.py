#!/usr/bin/env python3
"""Check controls, live metric sampling and performance layout updates.
Run with python3 tests/controls.py . (requires qs on PATH).
"""
import base64
import os
from pathlib import Path
from qml_fixture import theme_fixture
import re
import shutil
import subprocess
import sys
import tempfile

SSH_PUBLIC = "ssh-rsa " + "A" * 700

QML = """import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import Quickshell.Services.UPower
import Quickshell.Io
import ControlFixtures as Fixtures
import qs.config as Config
import "icewine/deck" as Deck
import "icewine/modules" as Modules
import "icewine/modules/topbar" as Bar
import "icewine/modules/topbar/popouts" as Popouts
import "icewine/theme" as Theme
ShellRoot {
    id: root
    Component { id: handheldOverlay; Deck.DeckOverlay { compositor: compositor; sessionLocked: false; shell: root } }
    property bool clipboardOnly: false
    property bool sshOnly: false
    property bool keepAwake: false
    property bool doNotDisturb: false
    property int count: 0
    property var items: []
    property double now: Date.now()
    property real performanceHeightBefore: 0
    property string sessionAction: ""
    property int sleepCalls: 0
    property int toggles: 0
    property int buttonCalls: 0
    signal tick()
    QtObject {
        id: compositor
        readonly property var toplevels: []
        signal monitorsChanged()
        function activateWindow(address) {}
        function getMonitors() { return [{name: "fixture-no-screen", width: 1280, height: 800}] }
    }
    QtObject {
        id: session
        function requestLock() { root.sessionAction = "lock" }
        function requestSleep() { root.sessionAction = "sleep"; ++root.sleepCalls; return true }
        function requestReboot() { root.sessionAction = "reboot" }
        function requestShutdown() { root.sessionAction = "shutdown" }
    }
    QtObject {
        id: delayedWifi
        property bool connected: false
        property bool stateChanging: false
        signal connectionFailed(int reason)
        function connect() {}
    }
    QtObject {
        id: unavailableBrightness
        readonly property bool available: false
        readonly property int value: 0
        readonly property string monitorName: "DP-2"
        readonly property string error: "Brightness unavailable"
        function setBrightness(value) {}
    }
    QtObject {
        id: measuredBattery
        property bool isLaptopBattery: true
        property real percentage: 0.21
        property int state: UPowerDeviceState.Discharging
    }
    QtObject {
        id: chargingBattery
        property bool isLaptopBattery: true
        property real percentage: 0.21
        property int state: UPowerDeviceState.Discharging
    }
    Modules.BatteryAlert { session: session; batteryDevice: measuredBattery }
    Modules.BatteryAlert { session: session; batteryDevice: chargingBattery }
    Bar.SystemMetrics {
        id: systemMetrics
        network.path: Qt.resolvedUrl("network.txt")
        cpu.path: Qt.resolvedUrl("cpu.txt")
        memory.path: Qt.resolvedUrl("memory.txt")
    }
    FileView { id: cpuFixture; path: Qt.resolvedUrl("cpu.txt") }
    // Keep synthetic counters advancing throughout the longer interactive checks.
    Timer {
        interval: 500; running: true; repeat: true
        property int busyTicks: 100
        onTriggered: {
            busyTicks += 200
            cpuFixture.setText("cpu " + busyTicks + " 0 0 " + (busyTicks * 2) + " 0 0 0 0\\n")
        }
    }
    Bar.SteamShortcuts { id: steamShortcuts }
    Modules.GameLauncher { id: gameLauncher; compositor: compositor }
    Component.onCompleted: steamShortcuts.refresh()
    Bar.HistoryGraph {
        id: coldGraph
        width: 380
        title: "Temperature"
        unit: "°C"
        history: [{ time: root.now - 121000, values: [-50] },
            { time: root.now - 1000, values: [-5] }, { time: root.now, values: [null] }]
        now: root.now
    }

    Bar.MetricSampler {
        id: network
        clock: root
        path: Qt.resolvedUrl("network.txt")
        kind: "network"
        interfaces: ["eth0"]
    }
    Window {
        visible: true
        width: 380; height: 180
        Bar.HistoryGraph {
            anchors.fill: parent
            title: "Network"
            labels: ["↓", "↑"]
            unit: "B/s"
            history: network.history
            now: root.now
        }
    }
    Bar.MonitorBrightness {
        id: brightness
        monitorName: "DP-1"
        active: true
    }
    Window {
        id: toggleWindow
        visible: true
        width: 200; height: 80
        Popouts.Toggle {
            id: keyboardToggle
            text: "Keyboard action"
            onToggled: ++root.toggles
        }
        Popouts.ActionButton {
            id: keyboardButton
            y: 40
            text: "Keyboard button"
            onClicked: ++root.buttonCalls
        }
        Bar.Widget { id: animatedWidget; width: 20; height: 20; shown: false }
        TestCase { id: toggleKeys; when: false }
    }
    QtObject {
        id: clipboardFixture
        property var entries: []
        property string activeEntry: ""
        property bool available: true
        property bool busy: false
        property string error: ""
        property var calls: []
        function request(action, entry) { calls.push([action, entry]); return 1 }
    }
    Bar.ClipboardHistory {
        id: clipboardAdapter
        locked: true
        property var confirmations: []
        onLoaded: request => confirmations.push(request)
    }
    Window {
        id: clipboardWindow
        width: 380; height: 454
        property var pastes: []
        Bar.StatusPopout {
            id: clipboardPages
            anchors.fill: parent
            currentPage: "notifications"
            compositor: ({})
            notificationService: ({items: [], count: 0, doNotDisturb: false})
            session: ({})
            player: null
            powerState: ({})
            monitorName: "fixture-no-screen"
            metrics: ({})
            clipboardHistory: clipboardFixture
            onPasteRequested: entry => clipboardWindow.pastes.push(entry)
        }
    }
    Window {
        id: networkWindow
        visible: true
        width: 380; height: 150
        Rectangle { anchors.fill: parent; color: "#16161e" }
        Bar.StatusPopout {
            id: networkPages
            anchors.fill: parent
            currentPage: "network"
            compositor: ({})
            notificationService: ({})
            session: ({})
            player: null
            powerState: ({})
            monitorName: "fixture-no-screen"
            metrics: ({now: root.now, network: {history: []}})
        }
        TestCase { id: networkKeys; when: false }
    }
    Popouts.Media {
        id: media
        width: 380; height: 420
        player: null
    }
    Popouts.Battery {
        id: battery
        width: 380; height: 420
        powerState: root
        session: session
        brightness: brightness
        batteryDevice: null
    }
    Popouts.Battery {
        id: unavailableBattery
        width: 380; height: 420
        powerState: root
        session: session
        brightness: unavailableBrightness
        batteryDevice: null
    }
    Popouts.Notifications {
        width: 380; height: 456
        compositor: compositor
        notificationService: root
    }
    Window {
        visible: true
        width: 380; height: 500
        Bar.StatusPopout {
            id: performance
            anchors.fill: parent
            currentPage: "performance"
            compositor: compositor
            notificationService: root
            session: session
            player: null
            powerState: root
            monitorName: "performance-only"
            metrics: ({ now: root.now,
                cpu: { history: [{ time: root.now, values: [25] }] },
                cpuTemperature: { label: "Package", current: 48 },
                memory: { current: { usedGiB: 9, totalGiB: 16 },
                    history: [{ time: root.now, values: [60] }] },
                gpus: [{ title: "GPU 0000:03:00.0",
                    usage: { history: [{ time: root.now, values: [40] }] },
                    temperature: { label: "Edge", current: 52 } }]
            })
        }
    }
    Window {
        id: focusWindow
        visible: true
        width: 380; height: 150
        Bar.StatusPopout {
            id: focusPopout
            anchors.fill: parent
            compositor: compositor
            notificationService: root
            clipboardHistory: clipboardFixture
            session: session
            player: fixturePlayer
            powerState: root
            monitorName: "fixture-no-screen"
            metrics: Object.assign({ network: { history: [] } }, performance.metrics)
        }
    }
    QtObject {
        id: fixturePlayer
        property bool canTogglePlaying: true
    }
    function descendants(item, predicate) {
        let result = predicate(item) ? [item] : []
        for (const child of item.children ?? [])
            result = result.concat(descendants(child, predicate))
        return result
    }
    function assertRevealed(item, label) {
        if (!item || !item.activeFocus) throw new Error(label + ": focus lost")
        for (let scroll = item.parent; scroll && scroll !== focusPopout; scroll = scroll.parent) {
            if (!(scroll instanceof Flickable)) continue
            const top = item.mapToItem(scroll, 0, 0).y
            if (item.height <= scroll.height && (top < -0.5 || top + item.height > scroll.height + 0.5))
                throw new Error(`${label}: focused control clipped: top=${top}, height=${item.height}, viewport=${scroll.height}`)
        }
    }
    Window {
        id: cardWindow
        visible: true
        width: 400; height: 424
        property int handoffs: 0
        property int companionCalls: 0
        Bar.CardStack {
            id: launcherStack
            anchors.fill: parent
            cards: [launcherCard, companionCard]
            Bar.LauncherCard {
                id: launcherCard
                accessibleName: "Launcher card"
                stack: launcherStack
                onHandoffRequested: ++cardWindow.handoffs
            }
            Bar.Card {
                id: companionCard
                accessibleName: "Companion card"
                index: 1
                stack: launcherStack
                implicitWidth: 400; implicitHeight: 424
                initialFocus: companionButton
                Popouts.ActionButton {
                    id: companionButton
                    text: "Companion"
                    x: 0; y: 60; width: 24; height: 70
                    enabled: companionCard.active
                    onClicked: ++cardWindow.companionCalls
                }
            }
        }
    }
    Window {
        id: backgroundWindow
        width: 434; height: 488
        property int activations: 0
        property int handoffs: 0
        property var trayItems: []
        property var watchedCard: null
        property int intermediateActivations: 0
        Connections {
            target: backgroundWindow.watchedCard
            function onActiveChanged() {
                if (backgroundWindow.watchedCard.active) ++backgroundWindow.intermediateActivations
            }
        }
        Bar.Launcher {
            id: backgroundLauncher
            compositor: layoutCompositor
            layoutsEnabled: false
            anchors.fill: parent
            engaged: true
            backgroundItems: backgroundWindow.trayItems
            onHandoffRequested: ++backgroundWindow.handoffs
        }
    }
    QtObject {
        id: layoutCompositor
        property int layoutWorkspaceId: 7
        property bool layoutAvailable: true
        property bool layoutPending: false
        property string layoutError: ""
        property string layoutUnavailable: ""
        property var layoutStatus: ({effective: "master", autofullscreen: false})
        property var calls: []
        function selectLayout(choice) { calls.push([layoutWorkspaceId, choice]) }
        function selectAutofullscreen(choice) { calls.push([layoutWorkspaceId, choice]) }
    }
    function checkLayoutCards() {
        backgroundWindow.trayItems = []
        const host = backgroundLauncher
        backgroundWindow.visible = true
        backgroundWindow.requestActivate()
        toggleKeys.tryCompare(backgroundWindow, "active", true)
        host.layoutsEnabled = true
        const stack = descendants(host, item => item.cards !== undefined)[0]
        const launcher = stack.cards[0]
        host.openLauncher()
        toggleKeys.wait(30)
        if (stack.cards.length !== 2 || host.layoutActive)
            throw new Error("Layout did not join launcher without tray apps")
        host.openLayout()
        toggleKeys.tryCompare(stack, "exchanging", false, 900)
        const layout = stack.cards[1]
        let toggle = root.findAccessible(layout, "Autofullscreen")
        if (!host.layoutActive || !toggle.activeFocus || layoutCompositor.calls.length)
            throw new Error("Layout entry lost focus or applied a layout")
        backgroundWindow.height = 150
        toggleKeys.wait(30)
        host.focusInitial()
        const scroll = descendants(layout, item => item instanceof Flickable)[0]
        const focusY = toggle.mapToItem(scroll, 0, 0).y
        if (!scroll.clip || scroll.contentHeight <= scroll.height || focusY < 0
                || focusY + toggle.height > scroll.height)
            throw new Error("Constrained layout did not reveal focused controls: " + focusY + "/" + scroll.height)
        backgroundWindow.height = 488
        toggleKeys.wait(30)
        layoutCompositor.layoutWorkspaceId = 9
        toggleKeys.keyClick(Qt.Key_Return)
        const master = root.findAccessible(layout, "Master layout")
        toggleKeys.mouseClick(master)
        if (JSON.stringify(layoutCompositor.calls) !== JSON.stringify([[9, true], [9, "master"]]))
            throw new Error("Layout controls did not target the current workspace")
        for (const state of ["layoutPending", "layoutAvailable"]) {
            layoutCompositor[state] = state === "layoutPending"
            host.focusInitial()
            if (toggle.enabled || master.enabled || !layout.selector.activeFocus)
                throw new Error("Unavailable/pending layout lacks an inert focus target")
            toggleKeys.mouseClick(master)
            layoutCompositor[state] = state !== "layoutPending"
        }
        if (layoutCompositor.calls.length !== 2) throw new Error("Unavailable layout acted")
        layoutCompositor.calls = []
        backgroundWindow.trayItems = [{id: "layout-tray", title: "App", icon: "", status: 0, hasMenu: false}]
        toggleKeys.wait(30)
        if (stack.cards.length !== 3 || stack.selectedCard !== 0 || host.layoutActive
                || stack.cards[1].index !== 1 || stack.cards[2].index !== 2)
            throw new Error("Three-card arrival failed declared order/reset")
        toggle = root.findAccessible(stack.cards[2], "Autofullscreen")
        const cards = Array.from(stack.cards)
        for (let front = 0; front < 3; ++front) {
            stack.selectCard(front)
            toggleKeys.tryCompare(stack, "exchanging", false, 900)
            const near = cards[(front + 1) % 3], far = cards[(front + 2) % 3]
            if (cards[front].x !== 26 || cards[front].y !== 56
                    || near.x !== 17 || near.y !== 32 || far.x !== 8 || far.y !== 8
                    || !(far.z < near.z && near.z < cards[front].z))
                throw new Error("Three-card rear exposure/order is incorrect")
            // Whole exposed strips promote without invoking controls.
            toggleKeys.mouseClick(far, 40, 8)
            toggleKeys.tryCompare(stack, "exchanging", false, 900)
            if (stack.selectedCard !== (front + 2) % 3 || layoutCompositor.calls.length)
                throw new Error("Rear strip did not promote inertly")
        }
        host.openLauncher()
        launcher.selector.forceActiveFocus()
        toggleKeys.keyClick(Qt.Key_Tab)
        toggleKeys.wait(25)
        backgroundWindow.watchedCard = cards[1]
        backgroundWindow.intermediateActivations = 0
        const before = cards.map(card => [card.x, card.y])
        toggleKeys.keyClick(Qt.Key_Tab)
        if (stack.queuedCard !== 2 || stack.motionInitialFocus !== backgroundWindow.activeFocusItem
                || cards.some((card, i) => card.x !== before[i][0] || card.y !== before[i][1]))
            throw new Error("Third-card request jumped the running sweep")
        toggleKeys.tryCompare(stack, "exchanging", false, 900)
        if (stack.frontCard !== 2 || !toggle.activeFocus || !host.layoutActive
                || backgroundWindow.intermediateActivations)
            throw new Error("Queued third-card request failed selected focus/activity")
        backgroundWindow.watchedCard = null
        // Layout uses the bounded shared focus chain, never arrow stack selection.
        toggleKeys.keyClick(Qt.Key_Right)
        if (stack.selectedCard !== 2 || stack.exchanging || toggle.activeFocus)
            throw new Error("Layout arrow did not move focus within its card")
        cards[2].selector.forceActiveFocus()
        toggleKeys.keyClick(Qt.Key_Tab)
        toggleKeys.tryCompare(stack, "exchanging", false, 900)
        if (stack.frontCard !== 0 || !launcher.initialFocus.activeFocus)
            throw new Error("Three-card Tab wrapping failed")
        for (const remove of ["tray", "layout"]) {
            host.openLauncher()
            stack.selectCard(1)
            toggleKeys.wait(25)
            stack.selectCard(2)
            toggleKeys.keyPress(Qt.Key_Return)
            if (remove === "tray") backgroundWindow.trayItems = []
            else host.layoutsEnabled = false
            toggleKeys.wait(30)
            toggleKeys.keyRelease(Qt.Key_Return)
            toggleKeys.wait(160)
            if (stack.cards.length !== 2 || stack.exchanging || stack.queuedCard !== -1
                    || stack.selectedCard !== 0 || !launcher.initialFocus.activeFocus)
                throw new Error("Optional removal kept stale queued motion/focus")
            backgroundWindow.trayItems = [{id: "layout-tray", title: "App", icon: "", status: 0, hasMenu: false}]
            host.layoutsEnabled = true
            toggleKeys.wait(30)
        }
        host.openLayout()
        toggleKeys.wait(25)
        host.openLauncher()
        if (stack.exchanging || stack.selectedCard !== 0 || !launcher.initialFocus.activeFocus
                || layoutCompositor.calls.length)
            throw new Error("Explicit Launcher entry did not cancel Layout exchange")
        for (const arriving of ["tray", "layout"]) {
            host.layoutsEnabled = arriving === "tray"
            backgroundWindow.trayItems = arriving === "tray" ? []
                : [{id: "layout-tray", title: "App", icon: "", status: 0, hasMenu: false}]
            toggleKeys.wait(30)
            host.openLauncher()
            stack.selectCard(1)
            toggleKeys.wait(25)
            toggleKeys.keyPress(Qt.Key_Space)
            host.layoutsEnabled = true
            backgroundWindow.trayItems = [{id: "layout-tray", title: "App", icon: "", status: 0, hasMenu: false}]
            toggleKeys.wait(30)
            toggleKeys.keyRelease(Qt.Key_Space)
            toggleKeys.wait(140)
            if (stack.cards.length !== 3 || stack.exchanging || stack.selectedCard !== 0
                    || !launcher.initialFocus.activeFocus || layoutCompositor.calls.length)
                throw new Error("Optional arrival retained stale motion or activation")
        }
        host.layoutsEnabled = false
        backgroundWindow.trayItems = []
        backgroundWindow.visible = false
    }
    function checkBackgroundCards() {
        backgroundWindow.visible = true
        backgroundWindow.requestActivate()
        toggleKeys.tryCompare(backgroundWindow, "active", true)
        const host = backgroundLauncher
        const stack = descendants(host, item => item.cards !== undefined)[0]
        const launcher = stack.cards[0]
        host.openLauncher()
        if (stack.cards.length !== 1 || host.implicitWidth !== 400 || host.implicitHeight !== 424
                || launcher.x !== 0 || launcher.y !== 0 || !launcher.initialFocus.activeFocus)
            throw new Error("Empty tray left a rear card or stack allowance")
        const first = {id: "first", title: "First", icon: "", status: 0, hasMenu: false,
            activate: () => ++backgroundWindow.activations}
        const second = {id: "second", title: "Second", icon: "", status: 0, hasMenu: true, menu: null}
        backgroundWindow.trayItems = [first, second]
        toggleKeys.wait(30)
        if (stack.cards.length !== 2 || host.implicitWidth !== 434 || host.implicitHeight !== 488)
            throw new Error("First tray arrival failed optional-card creation")
        const rear = stack.cards[1]
        const apps = descendants(rear, item => item.selectedItem !== undefined)[0]
        toggleKeys.mouseClick(rear, 8, 80)
        toggleKeys.tryCompare(stack, "exchanging", false, 900)
        if (stack.selectedCard !== 1 || backgroundWindow.activations || backgroundWindow.handoffs
                || !apps.initialFocus.activeFocus)
            throw new Error("Rear promotion activated an app or lost background focus")
        host.focusInitial()
        if (stack.selectedCard !== 1 || !apps.initialFocus.activeFocus)
            throw new Error("Ordinary focus restoration reset the selected card")
        apps.selectApp(1)
        backgroundWindow.trayItems = [second, first]
        toggleKeys.wait(30)
        if (apps.selectedItem !== second || apps.initialFocus.currentIndex !== 0)
            throw new Error("Tray reorder lost selected app identity")
        apps.openItem(second)
        host.openLauncher()
        host.openLauncher()
        toggleKeys.wait(20)
        if (stack.selectedCard !== 0 || stack.exchanging || apps.activeItem || apps.menuPath.length
                || !launcher.initialFocus.activeFocus)
            throw new Error("Repeated explicit launcher open failed menu/focus reset")
        stack.selectCard(1)
        toggleKeys.wait(30)
        host.openLauncher()
        if (stack.exchanging || stack.frontCard !== 0 || !launcher.initialFocus.activeFocus)
            throw new Error("Explicit open failed during exchange")
        for (const duringMotion of [false, true]) {
            stack.selectCard(1)
            if (!duringMotion) toggleKeys.tryCompare(stack, "exchanging", false, 900)
            if (duringMotion) stack.motionInitialFocus.forceActiveFocus()
            toggleKeys.keyPress(Qt.Key_Return)
            backgroundWindow.trayItems = []
            toggleKeys.wait(30)
            toggleKeys.keyRelease(Qt.Key_Return)
            toggleKeys.wait(140)
            if (stack.cards.length !== 1 || stack.selectedCard !== 0 || stack.frontCard !== 0
                    || stack.exchanging || !launcher.initialFocus.activeFocus
                    || backgroundWindow.activations || backgroundWindow.handoffs)
                throw new Error("Last tray removal left stale motion, focus or activation")
            backgroundWindow.trayItems = [first, second]
            toggleKeys.wait(30)
        }
        stack.selectCard(1)
        toggleKeys.tryCompare(stack, "exchanging", false, 900)
        const currentApps = descendants(stack.cards[1], item => item.selectedItem !== undefined)[0]
        currentApps.openItem(second)
        toggleKeys.wait(20)
        host.focusInitial()
        if (stack.selectedCard !== 1 || !currentApps.initialFocus.activeFocus)
            throw new Error("Ordinary focus restoration lost the active tray menu")
        backgroundWindow.trayItems = [second, first]
        toggleKeys.wait(20)
        if (currentApps.activeItem !== second)
            throw new Error("Nonempty tray reorder closed a valid active menu")
        backgroundWindow.trayItems = [first]
        toggleKeys.wait(30)
        if (currentApps.activeItem || currentApps.menuPath.length || !currentApps.initialFocus.activeFocus)
            throw new Error("Removed menu app failed to restore the app list")
        currentApps.openItem(first)
        if (backgroundWindow.activations !== 1 || backgroundWindow.handoffs !== 1)
            throw new Error("Selected background app lost existing activation/handoff")
        backgroundWindow.visible = false
    }
    function checkSharedCards() {
        cardWindow.requestActivate()
        toggleKeys.tryCompare(cardWindow, "active", true)
        launcherStack.cards = [launcherCard]
        toggleKeys.wait(20)
        if (launcherCard.x !== 0 || launcherCard.y !== 0 || launcherCard.width !== 400
                || launcherCard.height !== 424 || launcherCard.radius !== 12
                || launcherCard.border.width !== 0
                || launcherCard.color.toString() !== Theme.Palette.backgroundDark.toString())
            throw new Error("Single launcher card changed its geometry or surface")
        launcherCard.focusInitial()
        if (!launcherCard.initialFocus.activeFocus) throw new Error("Launcher focus entry failed")
        launcherStack.cards = [launcherCard, companionCard]
        toggleKeys.wait(20)
        if (launcherCard.width !== 366 || launcherCard.height !== 360
                || launcherCard.x !== 26 || launcherCard.y !== 56 || companionCard.active)
            throw new Error("Launcher did not compose through shared stack geometry")
        // The exposed rear body lies over a real control, but promotes only.
        toggleKeys.mouseClick(companionCard, 8, 80)
        toggleKeys.tryCompare(launcherStack, "exchanging", false, 900)
        if (launcherStack.selectedCard !== 1 || cardWindow.companionCalls !== 0)
            throw new Error("Rear body click failed selection-only routing")
        toggleKeys.mouseClick(companionButton, 8, 20)
        if (cardWindow.companionCalls !== 1)
            throw new Error("Selected card control lost normal pointer input")
        toggleKeys.mouseClick(companionCard, 40, 20)
        if (launcherStack.selectedCard !== 1 || launcherStack.exchanging)
            throw new Error("Front title/body click cycled the stack")
        launcherStack.selectCard(1)
        toggleKeys.tryCompare(launcherStack, "exchanging", false, 900)
        if (launcherCard.active || !companionCard.active || !companionButton.activeFocus)
            throw new Error("Shared stack selection did not transfer focus/activity")
        launcherCard.launch({command: ["fixture-card"]})
        if (cardWindow.handoffs !== 0) throw new Error("Rear launcher dispatched a handoff")
        launcherStack.selectCard(0)
        toggleKeys.tryCompare(launcherStack, "exchanging", false, 900)
        launcherCard.launch({command: ["fixture-card"]})
        if (cardWindow.handoffs !== 1) throw new Error("Selected launcher lost handoff")
        launcherStack.enabled = false
        if (launcherCard.active || companionCard.active) throw new Error("Disabled stack remained active")
        launcherStack.enabled = true
        for (const size of [[400, 424], [170, 90]]) {
            cardWindow.width = size[0]; cardWindow.height = size[1]
            launcherStack.cards = [launcherCard]
            toggleKeys.wait(20)
            if (launcherCard.width !== size[0] || launcherCard.height !== size[1])
                throw new Error("Single-card constraints added an inset")
        }
        cardWindow.visible = false
    }
    function checkPowerCards() {
        focusWindow.requestActivate()
        toggleKeys.tryCompare(focusWindow, "active", true)
        focusPopout.currentPage = "battery"
        toggleKeys.wait(180)
        const stack = focusPopout.currentItem
        const power = stack.cards[0]
        const perf = stack.cards[1]
        const body = descendants(power, item => item.brightness !== undefined)[0]
        const graphPage = descendants(perf, item => item.metrics !== undefined)[0]
        const lock = root.findAccessible(body, "Lock")
        const actions = root.sessionAction
        if (stack.cards.length !== 2 || !power.active || perf.active
                || !body.brightness.active || !body.enabled || graphPage.enabled)
            throw new Error(`Power entry: count=${stack.cards.length}, power=${power.active}, performance=${perf.active}, brightness=${body.brightness.active}, body=${body.enabled}, graph=${graphPage.enabled}`)
        focusPopout.focusInitial()
        toggleKeys.wait(20)
        assertRevealed(lock, "Constrained Power initial")
        toggleKeys.keyClick(Qt.Key_Tab)
        if (!stack.exchanging || body.enabled || graphPage.enabled || body.brightness.active)
            throw new Error("Power exchange retained interactive/recurring work")
        toggleKeys.wait(240)
        if (!perf.active || !graphPage.enabled || !graphPage.activeFocus)
            throw new Error("Performance exchange did not enter the graph page")
        toggleKeys.keyClick(Qt.Key_End)
        if (graphPage.contentY <= 0) throw new Error("Constrained graphs did not scroll")
        focusPopout.focusInitial()
        if (stack.selectedCard !== 1) throw new Error("Focus restoration reset Power selection")
        // Whole rear surface consumes selection without firing the Lock beneath it.
        toggleKeys.mouseClick(power, 8, 80)
        toggleKeys.wait(240)
        if (!power.active || root.sessionAction !== actions || !body.brightness.active)
            throw new Error("Rear Power surface activated content or lost brightness activity")
        const slider = descendants(body, item => item.from === 0 && item.to === 100)[0]
        toggleKeys.tryCompare(slider, "visible", true)
        slider.value = slider.to
        slider.forceActiveFocus()
        toggleKeys.keyClick(Qt.Key_Right)
        if (stack.selectedCard !== 0) throw new Error("Brightness endpoint escaped to stack")
        focusPopout.openPowerPage("performance")
        toggleKeys.wait(240)
        if (!perf.active || body.brightness.active) throw new Error("Explicit Performance entry failed")
        focusPopout.shown = false
        if (body.brightness.active || power.active || perf.active)
            throw new Error("Closing Power host retained activity")
        focusPopout.currentPage = "battery"
        focusPopout.shown = true
        toggleKeys.wait(180)
        if (!power.active) throw new Error("Ordinary Power reopen retained rear selection")
        const touch = toggleKeys.touchEvent(focusWindow)
        touch.press(0, perf, 8, 12).commit()
        touch.release(0, perf, 8, 12).commit()
        toggleKeys.wait(240)
        if (!perf.active || root.sessionAction !== actions)
            throw new Error("Touch promotion failed or fired a session action")
        focusPopout.currentPage = "media"
        toggleKeys.wait(20)
        if (power.active || perf.active)
            throw new Error("Leaving Power retained card work")
    }
    Component {
        id: doomedBluetoothDevice
        QtObject {
            property bool pairing: true
            property bool paired: false
        }
    }
    function checkAudioCards() {
        focusWindow.requestActivate()
        toggleKeys.tryCompare(focusWindow, "active", true)
        focusPopout.currentPage = "audio"
        toggleKeys.wait(180)
        const stack = focusPopout.currentItem
        const audio = stack.cards[0]
        const bluetooth = stack.cards[1]
        let body = descendants(audio, item => item.sinks !== undefined)[0]
        const bt = descendants(bluetooth, item => item.pairingDevice !== undefined)[0]
        const adapter = Fixtures.Bluetooth.defaultAdapter
        const device = Fixtures.Bluetooth.testDevice
        if (stack.cards.length !== 2 || !audio.active || bt.enabled
                || Fixtures.Bluetooth.calls.length || adapter.discovering)
            throw new Error("Audio construction acted or lost initial selection")
        focusPopout.focusInitial()
        assertRevealed(body.initialFocus, "Audio entry")
        // Endpoint arrows belong to the real volume slider even when ignored.
        let slider = descendants(body, item => item.from === 0 && item.to === 1)[0]
        for (const [value, key] of [[0, Qt.Key_Left], [1, Qt.Key_Right]]) {
            slider.value = value
            slider.forceActiveFocus()
            toggleKeys.keyClick(key)
            if (stack.selectedCard !== 0) throw new Error("Volume endpoint escaped to stack")
        }
        focusPopout.openAudioPage("bluetooth")
        focusPopout.focusInitial()
        toggleKeys.wait(240)
        if (!bluetooth.active || body.enabled || !bt.initialFocus.activeFocus)
            throw new Error("Dedicated Bluetooth entry lost focus/activity")
        focusPopout.focusInitial()
        if (stack.selectedCard !== 1) throw new Error("Focus restoration reset Bluetooth selection")
        const discover = descendants(bt, item => item.text === "Discover devices")[0]
        discover.click()
        if (!adapter.discovering) throw new Error("Discovery did not use existing adapter")
        bt.activate(device)
        if (bt.pairingDevice !== device || Fixtures.Bluetooth.calls.join() !== "pair")
            throw new Error("Pairing did not start")
        // Rear promotion consumes the click, preserving discovery and pair intent.
        toggleKeys.mouseClick(audio, 8, 20)
        toggleKeys.wait(240)
        const sink = Fixtures.Pipewire.defaultAudioSink
        const muted = sink.audio.muted
        if (!audio.active || !adapter.discovering || bt.pairingDevice !== device)
            throw new Error("Rear promotion lost explicit Bluetooth state")
        bt.activate(device); bt.forget(device)
        device.pairing = false
        device.paired = true
        toggleKeys.wait(20)
        if (Fixtures.Bluetooth.calls.join() !== "pair,connect" || bt.pairingDevice
                || stack.selectedCard !== 0 || !body.initialFocus.activeFocus || sink.audio.muted !== muted)
            throw new Error("Hidden pairing completion acted on focus or wrong control")
        focusPopout.openAudioPage("bluetooth")
        toggleKeys.wait(240)
        device.connected = true
        bt.activate(device)
        device.connected = false
        bt.activate(device)
        bt.forget(device)
        if (Fixtures.Bluetooth.calls.join() !== "pair,connect,disconnect,connect,forget")
            throw new Error("Existing device actions changed")
        const calls = Fixtures.Bluetooth.calls.length
        device.state = Fixtures.BluetoothDeviceState.Connecting
        bt.activate(device); bt.forget(device)
        if (Fixtures.Bluetooth.calls.length !== calls) throw new Error("Busy device accepted action")
        device.state = 0
        // Retained owner survives dismissal and page replacement without taking focus.
        device.paired = false
        bt.activate(device)
        focusPopout.shown = false
        focusPopout.currentPage = "media"
        device.paired = true
        toggleKeys.wait(180)
        if (Fixtures.Bluetooth.calls.slice(-2).join() !== "pair,connect" || bt.pairingDevice)
            throw new Error("Dismissal lost pair-to-connect ownership")
        focusPopout.currentPage = "bluetooth"
        focusPopout.shown = true
        toggleKeys.wait(260)
        if (descendants(bluetooth, item => item.pairingDevice !== undefined)[0] !== bt)
            throw new Error("Bluetooth operation owner was recreated")
        for (const loss of ["cancel", "device", "adapter", "radio"]) {
            device.paired = false
            device.pairing = false
            bt.activate(device)
            const before = Fixtures.Bluetooth.calls.length
            if (loss === "cancel") device.pairing = false
            else if (loss === "device") adapter.devices = {values: []}
            else if (loss === "adapter") Fixtures.Bluetooth.defaultAdapter = null
            else adapter.enabled = false
            toggleKeys.wait(20)
            if (bt.pairingDevice) throw new Error("Stale pairing retained after " + loss)
            device.paired = true
            toggleKeys.wait(20)
            bt.activate(device); bt.forget(device)
            if (Fixtures.Bluetooth.calls.length !== before + (loss === "cancel" ? 2 : 0))
                throw new Error("Unavailable/stale pairing acted after " + loss)
            Fixtures.Bluetooth.defaultAdapter = adapter
            adapter.devices = {values: [device]}
            adapter.enabled = true
            device.pairing = false
        }
        const doomed = doomedBluetoothDevice.createObject(root)
        bt.pairingDevice = doomed
        doomed.destroy()
        toggleKeys.wait(20)
        if (bt.pairingDevice) throw new Error("Destroyed device retained a pending callback owner")
        Fixtures.Bluetooth.defaultAdapter = null
        focusPopout.focusInitial()
        if (!bluetooth.selector.activeFocus) throw new Error("Unavailable Bluetooth has no focus target")
        Fixtures.Bluetooth.defaultAdapter = adapter
        focusPopout.currentPage = "audio"
        toggleKeys.wait(260)
        body = descendants(audio, item => item.sinks !== undefined)[0]
        slider = descendants(body, item => item.from === 0 && item.to === 1)[0]
        Fixtures.Pipewire.defaultAudioSink = null
        focusPopout.focusInitial()
        if (body.initialFocus.enabled || !audio.selector.activeFocus)
            throw new Error("Unavailable audio did not guard mute/focus")
        const volume = sink.audio.volume
        slider.moved()
        body.initialFocus.toggled()
        if (sink.audio.volume !== volume || sink.audio.muted !== muted)
            throw new Error("Unavailable audio changed the old sink")
        Fixtures.Pipewire.defaultAudioSink = sink
        adapter.discovering = false
    }
    function checkPopoutFocus() {
        focusWindow.requestActivate()
        toggleKeys.tryCompare(focusWindow, "active", true)
        focusPopout.currentPage = "media"
        toggleKeys.wait(30)
        focusPopout.focusInitial()
        toggleKeys.wait(20)
        const play = root.findAccessible(focusPopout, "Play")
        assertRevealed(play, "Media initial")
        const surface = focusPopout.currentItem.cards[0]
        if (surface.x !== 0 || surface.y !== 0 || surface.width !== focusPopout.width
                || surface.height !== focusPopout.height || surface.radius !== 12
                || surface.border.width !== 0
                || surface.color.toString() !== Theme.Palette.backgroundDark.toString())
            throw new Error("Single status page acquired extra surface geometry")
        focusWindow.height = 100
        toggleKeys.wait(20)
        assertRevealed(play, "Media resized")
        focusWindow.height = 150
        toggleKeys.wait(20)
        // Manual-offset persistence; real wheel/touch gestures remain session checks.
        const mediaScroll = descendants(focusPopout, item => item instanceof Flickable)[0]
        mediaScroll.contentY = 0
        toggleKeys.wait(40)
        if (mediaScroll.contentY !== 0) throw new Error("Focus reveal fights manual scrolling")

        focusWindow.height = 104
        focusPopout.currentPage = "audio"
        toggleKeys.wait(30)
        const audio = descendants(focusPopout, item => item instanceof Flickable)[0]
        const rows = descendants(audio, item => item.label !== undefined && item.activeFocusOnTab)
        rows[0].forceActiveFocus()
        toggleKeys.wait(10)
        assertRevealed(rows[0], "Audio first")
        for (const [key, index] of [[Qt.Key_Down, 1], [Qt.Key_Left, 0],
                [Qt.Key_Right, 1], [Qt.Key_Up, 0]]) {
            const before = audio.contentY
            toggleKeys.keyClick(key)
            toggleKeys.wait(10)
            assertRevealed(rows[index], "Audio boundary " + key)
            if (index === 1 ? audio.contentY <= before : audio.contentY >= before)
                throw new Error("Audio did not cross the scroll boundary in the expected direction")
        }

        // Keep the notification viewport at 150px after the two-card allowance.
        focusWindow.height = 150 + 64
        root.items = Array.from({length: 3}, (_, index) => ({
            summary: "Notification " + index, appName: "Fixture", appIcon: "", body: "",
            urgency: 1, actions: [{text: "Fixture action", invoke: function() { ++root.buttonCalls }}], dismiss: function() {} }))
        root.count = root.items.length
        focusPopout.currentPage = "notifications"
        toggleKeys.wait(30)
        const list = descendants(focusPopout, item => item instanceof ListView)[0]
        list.cacheBuffer = list.contentHeight
        toggleKeys.wait(20)
        const buttons = descendants(list.contentItem, item => item.Accessible?.name === "Dismiss")
        const first = buttons[0]
        const last = buttons[buttons.length - 1]
        first.forceActiveFocus()
        toggleKeys.wait(10)
        assertRevealed(first, "Notifications first")
        const actionCount = root.buttonCalls
        toggleKeys.keyClick(Qt.Key_Right)
        if (focusWindow.activeFocusItem.Accessible.name !== "Fixture action" || root.buttonCalls !== actionCount)
            throw new Error("Notification action is not reachable without activation")
        toggleKeys.keyClick(Qt.Key_Space)
        if (root.buttonCalls !== actionCount + 1) throw new Error("Keyboard notification action failed")
        first.forceActiveFocus()
        const before = list.contentY
        last.forceActiveFocus()
        toggleKeys.wait(10)
        assertRevealed(last, "Notifications last")
        const down = list.contentY
        first.forceActiveFocus()
        toggleKeys.wait(10)
        assertRevealed(first, "Notifications upward")
        if (!(down > before && list.contentY < down))
            throw new Error("Nested ListView did not scroll in both directions")

        // Queue reveal, replace its page, then reopen without taking external focus.
        focusPopout.currentPage = "media"
        toggleKeys.wait(30)
        focusPopout.focusInitial()
        focusPopout.currentPage = "notifications"
        focusPopout.shown = false
        toggleWindow.requestActivate()
        keyboardToggle.forceActiveFocus()
        toggleKeys.wait(170)
        focusPopout.currentPage = "media"
        focusPopout.shown = true
        toggleKeys.wait(30)
        if (!keyboardToggle.activeFocus) throw new Error("Page replacement or reopen stole external focus")
        focusWindow.requestActivate()
        toggleKeys.tryCompare(focusWindow, "active", true)
        focusPopout.focusInitial()
        toggleKeys.wait(20)
        assertRevealed(root.findAccessible(focusPopout, "Play"), "Media reopened")
        root.items = []
        root.count = 0
    }
    function networkBody() { return descendants(networkPages.cardFor("network"), item => item.wifiDevice !== undefined)[0] }
    function selectCardTarget(target) { target.parent.stack.selectCard(target.parent.index) }
    function checkNetworkCards(selected, other, page) {
        const front = selected.parent
        const rear = other.parent
        const body = descendants(front, item => item instanceof Flickable)[0]
        const rearDepth = page.rearOffset(rear.index, front.index)
        if (front.x - rear.x !== 18 * (1 - rearDepth) || front.y - rear.y !== 48 * (1 - rearDepth) || front.z <= rear.z
                || front.color.toString() !== rear.color.toString() || front.opacity !== 1 || rear.opacity !== 1)
            throw new Error("Cards lost their opaque lower/right stack")
        for (const card of [front, rear]) {
            if (card.x < 0 || card.y < 0 || card.x + card.width > page.width
                    || card.y + card.height > page.height || !card.clip)
                throw new Error("Resting card exceeds constrained host")
        }
        if (!selected.Accessible.checkable || selected.Accessible.checked !== selected.checked
                || other.Accessible.checked !== other.checked)
            throw new Error("Shared card selection lost accessible state")
        if (!selected.activeFocus || !selected.checked || other.checked
                || !body.enabled
                || front.border.width !== 0 || rear.border.width !== 0
                || descendants(rear, item => item instanceof Flickable)[0].enabled)
            throw new Error("Card input, selection or focus ownership is incorrect")
        if (body.height <= 0 || !body.clip)
            throw new Error("Card must retain its constrained scroll viewport")
    }
    function settleCards(page) {
        networkKeys.tryCompare(page, "exchanging", false, 900)
    }
    function checkSsh(page, first, second) {
        const third = root.findAccessible(networkPages, "SSH card")
        if (!third || page.cards.length !== 3) throw new Error("SSH is not the third network card")
        networkWindow.height = 550
        first.forceActiveFocus()
        networkKeys.keyClick(Qt.Key_Tab)
        settleCards(page)
        networkKeys.keyClick(Qt.Key_Tab)
        settleCards(page)
        if (!third.checked || !third.activeFocus || root.networkBody().wifiDevice.scannerEnabled)
            throw new Error("Keyboard entry did not select SSH and stop background Wi-Fi scanning")
        const ssh = descendants(third.parent, item => typeof item.openForm === "function")[0]
        networkKeys.tryCompare(ssh, "busy", false)
        networkKeys.tryCompare(ssh, "available", true)
        root.findAccessible(ssh, "Import SSH key").click()
        const primaryImport = root.findAccessible(ssh, "Import SSH key")
        if (!primaryImport.primary || primaryImport.height !== 34
                || primaryImport.background.color.toString() !== Theme.Palette.primary.toString())
            throw new Error("SSH Import lost its primary action hierarchy")
        if (root.findAccessible(ssh, "Refresh SSH keys").text !== "↻")
            throw new Error("SSH Refresh must use its reference icon")
        if (!descendants(ssh, item => item instanceof Text && item.visible && item.text === "Import key").length
                || !descendants(ssh, item => item instanceof Text && item.visible && item.text === "Private key text").length)
            throw new Error("SSH import lost its visible heading or field label")
        const path = root.findAccessible(ssh, "SSH key path")
        const phrase = root.findAccessible(ssh, "SSH key passphrase")
        const fileMode = root.findAccessible(ssh, "Import SSH key from file")
        const privateInput = root.findAccessible(ssh, "Pasted SSH private key")
        networkKeys.tryCompare(privateInput, "activeFocus", true)
        if (fileMode.checked || path.visible || !privateInput.visible) throw new Error("Import is not paste-default")
        privateInput.text = "synthetic private key\nsecond line"
        phrase.text = "fixture secret"
        fileMode.checked = true
        if (privateInput.text || phrase.text) throw new Error("Switching SSH input retained secrets")
        path.text = "/synthetic/private-key"
        phrase.text = "fixture secret"
        fileMode.checked = false
        if (path.text || phrase.text) throw new Error("Returning to paste retained file secrets")
        fileMode.checked = true
        path.text = "/synthetic/private-key"
        phrase.text = "fixture secret"
        if (phrase.echoMode !== TextInput.Password) throw new Error("SSH passphrase is visible")
        page.selectCard(0)
        settleCards(page)
        if (path.text || privateInput.text || phrase.text || ssh.form || ssh.active)
            throw new Error("Leaving SSH retained private form state")
        page.selectCard(2)
        settleCards(page)
        networkKeys.tryCompare(ssh, "busy", false)
        root.findAccessible(ssh, "Import SSH key").click()
        privateInput.text = "synthetic private key\nsecond line"
        phrase.text = "fixture secret"
        root.findAccessible(ssh, "Cancel SSH key action").click()
        if (privateInput.text || phrase.text || ssh.form) throw new Error("Cancel retained pasted SSH input")
        root.findAccessible(ssh, "Import SSH key").click()
        networkKeys.tryCompare(privateInput, "activeFocus", true)
        privateInput.text = "synthetic private key\nsecond line"
        phrase.text = "fixture secret"
        networkKeys.keyClick(Qt.Key_Escape)
        if (privateInput.text || phrase.text || ssh.form) throw new Error("Escape retained SSH input")
        root.findAccessible(ssh, "Import SSH key").click()
        privateInput.text = "synthetic private key\nsecond line"
        phrase.text = "fixture secret"
        networkWindow.height = 350
        networkKeys.wait(30)
        privateInput.forceActiveFocus()
        networkKeys.keyClick(Qt.Key_Tab)
        if (!phrase.activeFocus || page.selectedCard !== 2) throw new Error("Paste Tab did not reach passphrase")
        const phraseTop = phrase.mapToItem(ssh, 0, 0).y
        if (phraseTop < 0 || phraseTop + phrase.height > ssh.height + 1)
            throw new Error("SSH keyboard focus was clipped on a small viewport")
        networkKeys.keyClick(Qt.Key_Return)
        if (privateInput.text || phrase.text || ssh.form) throw new Error("Submit retained pasted SSH input")
        networkKeys.tryCompare(ssh, "busy", false)
        networkKeys.tryCompare(ssh, "message", "Pasted import received")
        if (ssh.pending || ssh.publicKey.includes("private")) throw new Error("Private input escaped to public state")
        const disk = {public: "ssh-ed25519 disk-public", paths: ["/synthetic/selected-key"], importPath: "/synthetic/selected-key",
            loaded: false, temporary: false, type: "ssh-ed25519", fingerprint: "SHA256:disk"}
        ssh.entries = [ssh.entries[0], disk, Object.assign({}, disk, {public: "ssh-ed25519 public-only", paths: ["/missing/private"], importPath: "", fingerprint: "SHA256:public-only"})]
        let load = root.findAccessible(ssh, "Load SSH key SHA256:disk")
        if (!load.visible || root.findAccessible(ssh, "Load SSH key SHA256:public-only").visible)
            throw new Error("Load did not guard public-only inventory")
        ssh.available = false
        ssh.request("import")
        if (ssh.busy || ssh.pending) throw new Error("Unavailable keyboard request was accepted")
        if (load.enabled) throw new Error("Unavailable agent allows Load")
        ssh.available = true
        ssh.busy = true
        if (load.enabled) throw new Error("Busy agent allows Load")
        ssh.busy = false
        load.click()
        networkKeys.tryCompare(phrase, "activeFocus", true)
        if (!fileMode.checked || path.text !== disk.importPath || privateInput.text || ssh.expectedFingerprint !== disk.fingerprint)
            throw new Error("Selected-file Load targeted the wrong path/input")
        path.text = "/synthetic/intentional-edit"
        if (ssh.expectedFingerprint) throw new Error("Path edit retained selected identity")
        ssh.openForm("import", disk.importPath, disk.fingerprint)
        fileMode.checked = false
        if (ssh.expectedFingerprint) throw new Error("Source edit retained selected identity")
        root.findAccessible(ssh, "Cancel SSH key action").click()
        load = root.findAccessible(ssh, "Load SSH key SHA256:disk")
        load.click()
        networkKeys.tryCompare(phrase, "activeFocus", true)
        root.findAccessible(ssh, "Cancel SSH key action").click()
        if (ssh.expectedFingerprint) throw new Error("Cancel retained selected identity")
        root.findAccessible(ssh, "Load SSH key SHA256:disk").click()
        networkKeys.tryCompare(phrase, "activeFocus", true)
        phrase.text = "fixture secret"
        networkKeys.keyClick(Qt.Key_Return)
        if (path.text || phrase.text || ssh.form || ssh.expectedFingerprint) throw new Error("File submit retained secrets")
        networkKeys.tryCompare(ssh, "busy", false)
        networkKeys.tryCompare(ssh, "message", "Selected file import received")
        const publicButton = root.findAccessible(ssh, "Show public SSH key SHA256:fixture")
        let identity = publicButton.parent.parent.parent
        if (identity.color.toString() === publicButton.background.color.toString() || identity.radius !== 9
                || identity.width > ssh.width || identity.height <= publicButton.height)
            throw new Error("SSH identity is not a constrained individual card")
        publicButton.forceActiveFocus()
        networkKeys.keyClick(Qt.Key_Return)
        if (ssh.publicKey !== "ssh-ed25519 fixture-public") throw new Error("Keyboard public-key display failed")
        const publicText = descendants(identity, item => item instanceof Text && item.text === "ssh-ed25519 fixture-public")[0]
        if (!publicText || !publicText.visible) throw new Error("Public key escaped its identity")
        if (publicText.parent.parent.color.toString() !== Theme.Palette.backgroundDark.toString()
                || publicText.parent.parent.radius !== 8)
            throw new Error("Public key disclosure lost its inset surface")

        const copy = root.findAccessible(identity, "Copy public SSH key SHA256:fixture")
        for (let step = 0; step < 4 && !copy.activeFocus; step++) networkKeys.keyClick(Qt.Key_Down)
        if (!copy.activeFocus || page.selectedCard !== 2) throw new Error("Down did not reach inline Copy")
        networkKeys.wait(30)
        const copyTop = copy.mapToItem(ssh, 0, 0).y
        if (identity.height <= ssh.height || copyTop < 0 || copyTop + copy.height > ssh.height + 1)
            throw new Error("Long public-key Copy focus is clipped: y=" + copyTop + " height=" + copy.height + " viewport=" + ssh.height + " identity=" + identity.height + " contentY=" + ssh.contentY + " contentHeight=" + ssh.contentHeight)
        networkKeys.keyClick(Qt.Key_Return)
        ssh.publicKey = "ssh-ed25519 different-public"
        networkKeys.tryCompare(ssh, "message", "Public key copied")
        publicButton.click()
        publicButton.click()
        if (publicText.visible || copy.visible) throw new Error("Public key disclosure did not collapse")
        ssh.entries = []
        if (!descendants(ssh, item => item instanceof Text && item.visible && item.text.startsWith("No identities discovered." )).length)
            throw new Error("Missing empty inventory guidance")
        ssh.error = "Synthetic agent error"
        if (!descendants(ssh, item => item instanceof Text && item.visible && item.text === ssh.error).length)
            throw new Error("Agent error hidden")
        ssh.error = ""
        root.findAccessible(ssh, "Generate SSH key").click()
        phrase.text = "fixture secret"
        root.findAccessible(ssh, "Confirm SSH passphrase").text = "fixture secret"
        root.findAccessible(ssh, "Confirm SSH key action").click()
        if (phrase.text || path.text || ssh.form) throw new Error("Submitting SSH retained UI secrets")
        networkKeys.tryCompare(ssh, "busy", true)
        networkPages.shown = false
        networkKeys.tryCompare(ssh, "busy", false)
        if (ssh.pending || phrase.text || ssh.form) throw new Error("Dismissed SSH kept pending/private input")
        networkPages.shown = true
        networkKeys.tryCompare(ssh, "active", true)
        networkKeys.tryCompare(ssh, "busy", false)
        networkKeys.tryCompare(ssh, "available", true)
        if (ssh.entries.length !== 1) throw new Error("Reopened SSH did not refresh public inventory")
        root.findAccessible(ssh, "Import SSH key").click()
        privateInput.text = "synthetic private key\nsecond line"
        phrase.text = "fixture secret"
        networkPages.currentPage = "audio"
        networkKeys.wait(30)
        if (privateInput.text || phrase.text || ssh.form || ssh.active) throw new Error("Page change retained SSH secret fields")
        networkPages.currentPage = "network"
        networkKeys.tryCompare(networkPages, "enabled", true)
        networkKeys.wait(220)
        page.selectCard(0)
        settleCards(page)
        networkWindow.requestActivate()
        networkKeys.tryCompare(networkWindow, "active", true)
        first.forceActiveFocus()
        networkKeys.tryCompare(first, "activeFocus", true)
        networkWindow.height = 150
    }
    function checkCardMotion(page, first, second) {
        const wifi = descendants(first.parent, item => item instanceof Flickable)[0]
        const tailscale = descendants(second.parent, item => item instanceof Flickable)[0]
        first.forceActiveFocus()
        networkKeys.keyPress(Qt.Key_Space)
        const toggle = root.findVisible(first.parent, item => item.text === "Wi-Fi" && item.checked !== undefined)
        toggle.forceActiveFocus()
        networkKeys.keyRelease(Qt.Key_Space)
        if (page.selectedCard !== 0 || page.exchanging)
            throw new Error("Focus interruption activated a stale selection key")
        first.forceActiveFocus()
        networkKeys.keyClick(Qt.Key_Tab)
        settleCards(page)
        if (!second.activeFocus || page.selectedCard !== 1) throw new Error("Tab did not select the next card")
        networkKeys.keyClick(Qt.Key_Backtab)
        settleCards(page)
        // Mere hover and keyboard focus must not select a card.
        networkKeys.mouseMove(second, 40, 20)
        second.forceActiveFocus()
        networkKeys.wait(30)
        if (page.selectedCard !== 0 || page.exchanging)
            throw new Error("Hover/focus selected the alternate card")
        // Real click and early reversal, with both bodies inert and focus stationary.
        networkKeys.mouseClick(second, 40, 20)
        networkKeys.wait(30)
        const outgoing = first.parent
        if (!page.exchanging || outgoing.x >= 26 || outgoing.z !== 2
                || wifi.enabled || tailscale.enabled || first.activeFocus || second.activeFocus)
            throw new Error("Early sweep did not move the front or remove body/title focus")
        const stationary = networkWindow.activeFocusItem
        function checkHostFocus() {
            // Repeated topbar activation reaches this actual caller while cards are moving.
            networkPages.focusInitial()
            const focus = networkWindow.activeFocusItem
            const point = focus.mapToItem(page, 0, 0)
            if (focus !== stationary || page.initialFocus !== stationary || !focus.activeFocus
                    || !focus.visible || !focus.enabled
                    || point.x < 0 || point.y < 0 || point.x + focus.width > page.width
                    || point.y + focus.height > page.height)
                throw new Error("Host focus re-entry left the visible stationary motion target")
        }
        checkHostFocus()
        networkKeys.mouseClick(second, 40, 20)
        if (second.activeFocus) throw new Error("Repeated selection focused a moving title")
        const x = outgoing.x, y = outgoing.y
        page.selectCard(0)
        if (outgoing.x !== x || outgoing.y !== y) throw new Error("Early reversal teleported")
        checkHostFocus()
        settleCards(page)
        checkNetworkCards(first, second, page)
        // Native keyboard activation and exact off-host handoff through actual bindings.
        second.forceActiveFocus()
        networkKeys.keyClick(Qt.Key_Return)
        const animation = Array.from(page.data).find(item => item.property === "progress")
        networkKeys.wait(40)
        animation.pause()
        page.progress = 0.5
        if (outgoing.x + outgoing.width >= 0 || outgoing.z !== 1 || second.parent.z !== 2)
            throw new Error("Stacking changed without clearing the clipped host")
        checkHostFocus()
        page.selectCard(0)
        checkHostFocus() // Requested Networking title is completely clipped at this reversal.
        settleCards(page)
        checkNetworkCards(first, second, page)
        // Late reversal and repeated requests settle on the latest intent.
        second.forceActiveFocus()
        networkKeys.keyClick(Qt.Key_Space)
        networkKeys.wait(150)
        if (!page.exchanging || outgoing.z !== 1) throw new Error("Late sweep did not tuck behind")
        const lateX = outgoing.x
        page.selectCard(0)
        if (outgoing.x !== lateX) throw new Error("Late reversal teleported")
        networkKeys.wait(30)
        page.selectCard(1)
        settleCards(page)
        checkNetworkCards(second, first, page)
        // The exposed rear title also accepts real touch; Enter on the stationary target reverses.
        const touch = networkKeys.touchEvent(networkWindow)
        touch.press(0, first, 40, 20).commit()
        touch.release(0, first, 40, 20).commit()
        networkKeys.wait(20)
        networkKeys.keyPress(Qt.Key_Enter)
        if (page.selectedCard !== 0) throw new Error("Motion reversal acted on key press")
        networkKeys.keyRelease(Qt.Key_Enter)
        if (page.selectedCard !== 1) throw new Error("Motion reversal did not act on release")
        settleCards(page)
        selectCardTarget(first)
        settleCards(page)
        first.forceActiveFocus()
        checkNetworkCards(first, second, page)
        // A half-exchanged retained page stops moving/scanning immediately when dismissed.
        selectCardTarget(second)
        networkKeys.wait(20)
        networkPages.shown = false
        if (page.exchanging || root.networkBody().wifiDevice.scannerEnabled || tailscale.active)
            throw new Error("Hidden/closing card kept animation, scanning or polling")
        networkPages.shown = true
        networkKeys.wait(30)
        selectCardTarget(first)
        settleCards(page)
        first.forceActiveFocus()
    }
    FileView { id: cardDarkPalette; path: Qt.resolvedUrl("palette-dark.json"); blockAllReads: true }
    FileView { id: cardLightPalette; path: Qt.resolvedUrl("palette-light.json"); blockAllReads: true }
    function checkCardThemes(page, first, second) {
        for (const palette of [cardDarkPalette, cardLightPalette]) {
            Theme.Palette.file.setText(palette.text())
            if (!Theme.Palette.refresh()) throw new Error("Card theme refresh failed")
            networkKeys.wait(220)
            for (const [selected, other] of [[first, second], [second, first]]) {
                selectCardTarget(selected)
                settleCards(page)
                selected.forceActiveFocus()
                for (const width of [380, 320]) {
                    networkWindow.width = width
                    networkKeys.wait(20)
                    const naturalHeight = page.implicitHeight
                    for (const height of [550, 360, 150]) {
                        networkWindow.height = height
                        networkKeys.wait(20)
                        checkNetworkCards(selected, other, page)
                        if (page.implicitHeight !== naturalHeight)
                            throw new Error("Constrained card height fed back into natural measurement")
                        if (descendants(first.parent, item => item.text === "Networking")[0].color.toString() !== Theme.Palette.primary.toString()
                                || descendants(second.parent, item => item.text === "Tailscale")[0].color.toString() !== Theme.Palette.secondary.toString())
                            throw new Error("Card titles did not follow theme roles")
                        const image = networkKeys.grabImage(page)
                        for (const [card, dy] of [[selected.parent, 48], [other.parent, 46]]) {
                            if (image.pixel(card.x + 3, card.y + dy).toString() !== Theme.Palette.backgroundDark.toString())
                                throw new Error("Rendered card surface did not follow backgroundDark")
                        }
                    }
                }
            }
        }
        networkWindow.height = 150
        Theme.Palette.file.setText(cardDarkPalette.text())
        if (!Theme.Palette.refresh()) throw new Error("Card theme restore failed")
        selectCardTarget(first)
        settleCards(page)
        first.forceActiveFocus()
    }
    property bool traceNetworkFocus: false
    property var networkFocusEvents: []
    Connections {
        target: networkWindow
        function onActiveFocusItemChanged() {
            if (!root.traceNetworkFocus) return
            root.networkFocusEvents.push("signal:" + networkWindow.activeFocusItem?.Accessible.name)
            Qt.callLater(() => root.networkFocusEvents.push("later:" + networkWindow.activeFocusItem?.Accessible.name))
        }
    }
    function refreshSnapshot(page) {
        return {y: page.contentY, width: page.width, height: page.height,
            contentHeight: page.contentHeight, label: page.data.label, error: page.error,
            focus: networkWindow.activeFocusItem?.Accessible.name,
            focusEvents: root.networkFocusEvents.slice()}
    }
    FileView { id: tailscaleSelection; path: Qt.resolvedUrl("exit-node") }
    function checkTailscaleConnection() {
        networkWindow.requestActivate()
        networkKeys.tryCompare(networkWindow, "active", true)
        selectCardTarget(root.findAccessible(networkPages, "Tailscale card"))
        settleCards(networkPages.currentItem)
        const picker = root.findAccessible(networkPages, "Exit node")
        const page = picker.parent.parent.parent
        tailscaleSelection.setText("city")
        page.refresh()
        networkKeys.tryCompare(picker, "text", "Australia · Sydney")
        networkKeys.tryCompare(picker, "enabled", true)
        const connection = root.findAccessible(page, "Tailscale connection")
        if (!connection || !connection.checked || !connection.Accessible.checked || !connection.Accessible.checkable
                || connection.focusPolicy !== Qt.StrongFocus)
            throw new Error("Connection switch is missing confirmed state or keyboard/accessibility support")
        for (const width of [380, 280, 200]) {
            networkWindow.width = width
            networkKeys.wait(20)
            const title = root.findAccessible(page, "Connected")
            const titleEnd = title.mapToItem(page, title.width, 0).x
            const switchStart = connection.mapToItem(page, 0, 0).x
            if (titleEnd > switchStart || switchStart + connection.width > page.width
                    || connection.width < 44 || connection.height < 44)
                throw new Error("Status and connection touch target overlap or overflow")
        }
        networkWindow.width = 280
        const settled = page.data
        const device = root.findAccessible(page, "Home gateway, online, 100.64.0.2")
        const title = root.findAccessible(page, "Connected")
        if (!device || !descendants(page, item => item.Accessible.name === "<b>Fixture laptop</b>, online, 100.64.0.3").length)
            throw new Error("Device identity fixture lost the distinct equal-name remote")
        if (descendants(page, item => item.Accessible.name === "Local duplicate, online, 100.64.0.4").length)
            throw new Error("Devices rendered Self.ID")
        tailscaleMode.setText("status-slow")
        root.traceNetworkFocus = true
        connection.forceActiveFocus()
        networkKeys.waitForRendering(page)
        // Apply the host's actual reveal after the preceding width/layout changes.
        networkPages.revealFocus()
        const before = root.refreshSnapshot(page)
        const scroll = page.contentY
        // Observe the existing automatic timer through a deliberately slow synthetic read.
        networkKeys.tryCompare(page, "busy", true, 6000)
        if (!connection.enabled || !picker.enabled)
            throw new Error("Background read disabled mutation controls for presentation")
        if (title.text !== "Connected")
            throw new Error("Background read replaced the settled headline")
        networkKeys.tryCompare(page, "busy", false)
        const after = root.refreshSnapshot(page)
        root.traceNetworkFocus = false
        console.log("TAILSCALE_REFRESH", JSON.stringify({before, after}))
        if (page.data !== settled || root.findAccessible(page, device.Accessible.name) !== device
                || !connection.activeFocus || after.focusEvents.length !== before.focusEvents.length
                || Math.abs(page.contentY - scroll) > 1)
            throw new Error(`Unchanged automatic read: model=${page.data === settled}, delegate=${root.findAccessible(page, device.Accessible.name) === device}, focus=${connection.activeFocus}, scroll=${page.contentY}/${scroll}`)
        tailscaleMode.setText("")
        for (const input of [Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter, "mouse", "touch", "touch"]) {
            connection.forceActiveFocus()
            networkKeys.wait(30) // Let the actual popout reveal the target before pointer/touch delivery.
            const wasChecked = connection.checked
            if (input === Qt.Key_Space) {
                tailscaleMode.setText("status-slow")
                page.refresh()
                networkKeys.tryCompare(page, "busy", true)
            }
            if (typeof input === "number") networkKeys.keyClick(input)
            else if (input === "mouse") networkKeys.mouseClick(connection, connection.width - 17, connection.height / 2)
            else {
                const touch = networkKeys.touchEvent(networkWindow)
                touch.press(0, connection, connection.width - 17, connection.height / 2).commit()
                touch.release(0, connection, connection.width - 17, connection.height / 2).commit()
            }
            if (input === Qt.Key_Space) {
                if (page.request.kind !== "status" || page.request.next?.kind !== "connection")
                    throw new Error("Read-time native click was lost or overlapped the status process")
                networkKeys.tryVerify(() => page.request?.kind === "connection")
                tailscaleMode.setText("")
            } else networkKeys.tryCompare(page, "busy", true)
            networkKeys.tryCompare(title, "text", "Changing connection…")
            if (connection.checked !== wasChecked || connection.enabled || picker.enabled)
                throw new Error("Connection must retain confirmed state and serialize input while busy")
            page.toggleConnection()
            page.selectExit("")
            networkKeys.tryCompare(page, "busy", false)
            networkKeys.tryCompare(page, "confirming", "")
            networkKeys.tryCompare(connection, "enabled", true)
            networkKeys.tryCompare(title, "text", page.data.label)
            if (connection.checked === wasChecked || connection.Accessible.checked !== connection.checked || page.error)
                throw new Error("Connection input did not confirm a state change: " + input + " / " + page.error)
            if (connection.checked && (page.data.selected !== "fixture-sydney-best"
                    || picker.text !== "Australia · Sydney"))
                throw new Error("Reconnection lost the saved exit-node preference")
        }
    }
    FileView { id: tailscaleRelease; path: Qt.resolvedUrl("tailscale-release") }
    // Each mode must reach disk before the next fake CLI process reads it.
    FileView { id: tailscaleMode; path: Qt.resolvedUrl("tailscale-mode"); blockWrites: true }
    function checkTailscaleLifetime() {
        const connection = root.findAccessible(networkPages, "Tailscale connection")
        const picker = root.findAccessible(networkPages, "Exit node")
        const page = picker.parent.parent.parent
        tailscaleMode.setText("success")
        networkKeys.tryCompare(connection, "enabled", true)
        connection.click()
        networkKeys.wait(50)
        const pending = page.request
        const cards = networkPages.currentItem
        cards.selectCard(0)
        networkKeys.wait(60)
        if (page.request !== pending || !page.busy || page.active)
            throw new Error("Card selection lost an in-flight mutation or kept rear polling active")
        cards.selectCard(1)
        settleCards(cards)
        networkPages.shown = false
        // Wait for the real close animation; the fake command awaits release below.
        networkKeys.tryCompare(networkPages, "visible", false, 1000)
        if (networkPages.visible || page.active || !page.busy || page.request !== pending)
            throw new Error(`Closing StatusPopout pending page: visible=${networkPages.visible}, active=${page.active}, busy=${page.busy}, retained=${page.request === pending}, progress=${cards.progress}`)
        networkPages.shown = true
        networkKeys.wait(30)
        if (root.findAccessible(networkPages, "Tailscale connection") !== connection
                || page.request !== pending || connection.enabled)
            throw new Error("Reopening StatusPopout replaced the request owner or allowed a duplicate mutation")
        page.toggleConnection()
        tailscaleRelease.setText("go")
        networkKeys.tryCompare(page, "busy", false)
        networkKeys.tryCompare(page, "confirming", "")
        if (page.data.state !== "Stopped" || page.error)
            throw new Error("Connection completion was lost through actual popout close/reopen")
        tailscaleMode.setText("")
        connection.click()
        networkKeys.tryCompare(connection, "checked", true)
        networkKeys.tryCompare(connection, "enabled", true)

        tailscaleMode.setText("failure")
        connection.click()
        networkKeys.wait(50)
        networkPages.shown = false
        networkKeys.wait(1100) // Command fails while hidden; its error and pending confirmation must survive.
        if (page.busy || !page.confirming || !page.error.includes("request failed") || page.active)
            throw new Error("Hidden StatusPopout lost connection failure/confirmation ownership")
        networkPages.shown = true
        networkKeys.tryCompare(page, "busy", false)
        networkKeys.tryCompare(page, "confirming", "")
        if (!page.error.includes("request failed") || !connection.checked)
            throw new Error("Reopened StatusPopout lost the failed connection feedback")

        tailscaleMode.setText("profile")
        connection.click()
        networkKeys.wait(50)
        networkPages.shown = false
        networkPages.currentPage = "media"
        networkKeys.wait(1100)
        if (page.busy || !page.confirming || page.active)
            throw new Error("Changing status pages discarded the hidden mutation owner")
        networkPages.shown = true
        networkKeys.wait(30)
        if (page.active || !page.confirming)
            throw new Error("Another status page restarted hidden Tailscale polling/confirmation")
        networkPages.currentPage = "network"
        networkKeys.tryCompare(page, "busy", false)
        networkKeys.tryCompare(page, "confirming", "")
        if (root.findAccessible(networkPages, "Tailscale connection") !== connection
                || !page.error.includes("profile changed") || page.data.self !== "fixture-other")
            throw new Error("Profile-change confirmation was lost across popout and page replacement")
        const networking = root.findAccessible(networkPages, "Networking card")
        selectCardTarget(networking)
        settleCards(networkPages.currentItem)
        const networkPage = descendants(networking.parent, item => item.wifiDevice !== undefined)[0]
        if (!root.networkBody().wifiDevice.scannerEnabled || page.active)
            throw new Error("Retained Network did not restore ordinary tab activity")
        networkPages.shown = false
        networkKeys.tryCompare(networkPages, "visible", false)
        if (root.networkBody().wifiDevice.scannerEnabled || page.active)
            throw new Error(`Retained Network left background scanning/polling active while hidden: networkVisible=${networkPage.visible}, scanning=${root.networkBody().wifiDevice.scannerEnabled}, tailscaleActive=${page.active}`)
        networkPages.shown = true
        networkKeys.wait(30)
        if (!root.networkBody().wifiDevice.scannerEnabled || page.active)
            throw new Error("Retained Network did not resume scanning on reopening its Networking tab")
    }
    function checkRetainedNetworkFocus() {
        networkWindow.requestActivate()
        networkKeys.tryCompare(networkWindow, "active", true)
        networkPages.currentPage = "network"
        const networking = root.findAccessible(networkPages, "Networking card")
        const page = descendants(networking.parent, item => item.wifiDevice !== undefined)[0]
        const password = root.findAccessible(page, "Wi-Fi password")
        page.connectNetwork(delayedWifi)
        networkPages.currentPage = "audio"
        networkPages.focusInitial()
        const mute = root.findVisible(networkPages, item => item.text === "Output muted")
        networkKeys.tryCompare(mute, "activeFocus", true)
        delayedWifi.connectionFailed(Fixtures.ConnectionFailReason.NoSecrets)
        networkKeys.wait(30)
        if (!mute.activeFocus || password.activeFocus || page.passwordNetwork !== delayedWifi)
            throw new Error("Hidden retained Network stole Audio focus or lost delayed auth feedback")
        networkPages.currentPage = "network"
        networkKeys.wait(20)
        if (!password.visible || page.passwordNetwork !== delayedWifi)
            throw new Error("Returning to Network lost the pending password prompt")
        page.closePassword()

        // Still focus a visible prompt; then cover hiding after queuing that same deferred callback.
        page.connectNetwork(delayedWifi)
        delayedWifi.connectionFailed(Fixtures.ConnectionFailReason.NoSecrets)
        networkKeys.tryCompare(password, "activeFocus", true)
        page.closePassword()
        page.connectNetwork(delayedWifi)
        delayedWifi.connectionFailed(Fixtures.ConnectionFailReason.NoSecrets)
        networkPages.currentPage = "audio"
        networkPages.focusInitial()
        const nextMute = root.findVisible(networkPages, item => item.text === "Output muted")
        networkKeys.tryCompare(nextMute, "activeFocus", true)
        networkKeys.wait(30)
        if (!nextMute.activeFocus || password.activeFocus || page.passwordNetwork !== delayedWifi)
            throw new Error("Deferred auth focus ignored a page change before callback delivery")
    }
    Timer {
        interval: 400
        running: true
        onTriggered: {
            try {
            root.checkClipboard()
            if (root.clipboardOnly) {
                console.log("CLIPBOARD_CHECK_PASSED")
                Qt.quit()
                return
            }
            // Sample within the rate model's three-second window, before deliberate motion waits.
            root.tick()
            networkWindow.requestActivate()
            networkKeys.tryCompare(networkWindow, "active", true)
            const firstTab = root.findAccessible(networkPages, "Networking card")
            const secondTab = root.findAccessible(networkPages, "Tailscale card")
            networkPages.focusInitial()
            if (!firstTab.activeFocus || !firstTab.checked || secondTab.checked)
                throw new Error("Network initial tab/focus is incorrect")
            const networkPage = networkPages.currentItem
            root.checkSsh(networkPage, firstTab, secondTab)
            if (root.sshOnly) { console.log("SSH_UI_CHECK_PASSED"); Qt.quit(); return }
            const password = root.findAccessible(root.networkBody(), "Wi-Fi password")
            root.networkBody().passwordNetwork = {name: "Fixture Wi-Fi"}
            password.text = "fixture secret"
            networkPages.focusInitial()
            if (!password.activeFocus) throw new Error("Host initial focus lost password precedence")
            if (!password.visible || networkPage.available)
                throw new Error("Password prompt must own stack navigation")
            networkKeys.keyClick(Qt.Key_Tab)
            networkKeys.keyClick(Qt.Key_Backtab)
            selectCardTarget(firstTab)
            selectCardTarget(secondTab)
            if (networkPage.selectedCard !== 0 || networkPage.exchanging
                    || firstTab.parent.active || secondTab.parent.active || root.networkBody().wifiDevice.scannerEnabled)
                throw new Error(`Password overlay did not suppress card input/scanning: selected=${networkPage.selectedCard}, exchanging=${networkPage.exchanging}, first=${firstTab.parent.active}, second=${secondTab.parent.active}, scanning=${root.networkBody().wifiDevice.scannerEnabled}`)
            root.networkBody().closePassword()
            if (password.text || root.networkBody().passwordNetwork)
                throw new Error("Password dismissal retained a secret or pending network")
            root.checkCardMotion(networkPage, firstTab, secondTab)
            root.checkCardThemes(networkPage, firstTab, secondTab)
            for (const width of [380, 320, 280, 200]) {
                networkWindow.width = width
                networkKeys.wait(20)
                root.checkNetworkCards(firstTab, secondTab, networkPage)
            }
            networkWindow.width = 280
            networkKeys.wait(20)
            const wifiPage = descendants(networkPage, item => item instanceof Flickable && !(item instanceof ListView))[0]
            if (wifiPage.contentHeight <= wifiPage.height) throw new Error("Long Wi-Fi card lost scrolling")
            wifiPage.contentY = 50
            root.networkBody().errorMessage = "Retained fixture error"
            secondTab.forceActiveFocus()
            networkKeys.keyClick(Qt.Key_Enter)
            root.settleCards(networkPage)
            if (!secondTab.checked || !secondTab.activeFocus)
                throw new Error("Enter did not select/focus Tailscale card")
            networkKeys.wait(20)
            root.checkNetworkCards(secondTab, firstTab, networkPage)
            if (!networkPage || root.networkBody().wifiDevice.scannerEnabled)
                throw new Error("Tailscale tab left synthetic Wi-Fi scanning active")
            const picker = root.findAccessible(networkPages, "Exit node")
            networkKeys.tryCompare(picker, "enabled", true)
            const page = picker.parent.parent.parent
            networkKeys.tryVerify(() => page.data.peers.length === 3)
            const statusLabel = root.findAccessible(page, "Connected")
            if (!statusLabel || statusLabel.textFormat !== Text.PlainText
                    || root.findAccessible(page, page.data.selfName + " · " + page.data.label))
                throw new Error("Status title must retain connection feedback without the local hostname")
            if (picker.text !== "None") throw new Error("Initial exit-node choice is not None")
            picker.click()
            const closureMenu = Array.from(picker.data).find(child => child.title !== undefined && child.count !== undefined)
            networkKeys.tryCompare(closureMenu, "visible", true)
            closureMenu.currentIndex = 4
            networkKeys.keyClick(Qt.Key_Right)
            const closureCountry = closureMenu.menuAt(4)
            networkKeys.tryCompare(closureCountry, "visible", true)
            networkPage.selectCard(0)
            networkKeys.tryCompare(closureCountry, "visible", false)
            networkKeys.tryCompare(closureMenu, "visible", false)
            root.settleCards(networkPage)
            selectCardTarget(secondTab)
            root.settleCards(networkPage)
            picker.forceActiveFocus()
            networkKeys.keyClick(Qt.Key_Space)
            const menu = Array.from(picker.data).find(child => child.title !== undefined && child.count !== undefined)
            networkKeys.tryCompare(menu, "visible", true)
            networkKeys.tryCompare(menu, "count", 6)
            if (menu.itemAt(1).text !== "Home gateway" || menu.itemAt(2).text !== "Remote gateway")
                throw new Error("Tailnet exit devices must precede countries")
            menu.currentIndex = 0
            networkKeys.keyClick(Qt.Key_Down)
            networkKeys.tryVerify(() => menu.itemAt(1).highlighted)
            if (page.data.selected !== "") throw new Error("Navigation changed routing")
            networkKeys.keyClick(Qt.Key_Up)
            networkKeys.tryVerify(() => menu.itemAt(0).highlighted)
            menu.currentIndex = 4
            networkKeys.keyClick(Qt.Key_Right)
            const country = menu.menuAt(4)
            networkKeys.tryCompare(country, "visible", true)
            if (country.title !== "Australia" || country.itemAt(0).text !== "Melbourne"
                    || country.itemAt(1).text !== "Sydney")
                throw new Error("Country/city grouping is incorrect")
            country.currentIndex = 0
            networkKeys.keyClick(Qt.Key_Down)
            networkKeys.tryVerify(() => country.itemAt(1).highlighted)
            networkKeys.keyClick(Qt.Key_Return)
            networkKeys.tryCompare(menu, "visible", false)
            networkKeys.tryCompare(picker, "enabled", true)
            // An enabled picker also permits a read with a queued mutation.
            networkKeys.tryCompare(page, "busy", false)
            networkKeys.tryCompare(page, "confirming", "")
            if (page.data.selected !== "fixture-sydney-best" || picker.text !== "Australia · Sydney")
                throw new Error(`City selection did not confirm its highest-priority exit node: selected=${page.data.selected}, picker=${picker.text}, error=${page.error}, busy=${page.busy}`)
            picker.forceActiveFocus()
            networkKeys.keyClick(Qt.Key_Space)
            networkKeys.tryCompare(menu, "visible", true)
            menu.currentIndex = 0
            networkKeys.keyClick(Qt.Key_Down)
            networkKeys.keyClick(Qt.Key_Return)
            networkKeys.tryCompare(menu, "visible", false)
            networkKeys.tryCompare(picker, "enabled", true)
            // An enabled picker also permits a read with a queued mutation.
            networkKeys.tryCompare(page, "busy", false)
            networkKeys.tryCompare(page, "confirming", "")
            if (page.data.connected || page.data.selected !== "fixture-exit")
                throw new Error("Expected confirmed Running/offline selected-node fixture")
            picker.forceActiveFocus()
            networkKeys.keyClick(Qt.Key_Down)
            networkKeys.wait(20)
            if (descendants(page, item => item.text === "Refresh Tailscale").length
                    || networkWindow.activeFocusItem === picker)
                throw new Error("Removed refresh control left a dead focus target")
            page.selectExit("fixture-alt")
            if (page.busy || picker.text !== "Home gateway")
                throw new Error("Offline new-node choice dispatched or left an unconfirmed selection")
            picker.forceActiveFocus()
            networkKeys.keyClick(Qt.Key_Space)
            networkKeys.tryCompare(menu, "visible", true)
            if (!menu.itemAt(0).enabled || menu.itemAt(2).enabled || menu.itemAt(4).enabled)
                throw new Error("Offline menu must permit only None")
            menu.currentIndex = 0
            networkKeys.keyClick(Qt.Key_Return)
            networkKeys.tryCompare(menu, "visible", false)
            networkKeys.tryCompare(page, "busy", false)
            networkKeys.tryCompare(page, "confirming", "")
            if (picker.text !== "None" || picker.enabled || page.data.connected || page.error)
                throw new Error("Offline clear did not confirm None or guard subsequent choices")
            firstTab.forceActiveFocus()
            networkKeys.keyClick(Qt.Key_Space)
            root.settleCards(networkPage)
            if (!firstTab.checked || !firstTab.activeFocus || picker.enabled || !root.networkBody().wifiDevice.scannerEnabled)
                throw new Error(`Space did not restore Networking card: selected=${networkPage.selectedCard}, front=${networkPage.frontCard}, checked=${firstTab.checked}, focus=${firstTab.activeFocus}, pickerEnabled=${picker.enabled}, scanning=${root.networkBody().wifiDevice.scannerEnabled}, activeFocus=${networkWindow.activeFocusItem}`)
            root.checkNetworkCards(firstTab, secondTab, networkPage)
            if (wifiPage.contentY !== 50 || root.networkBody().errorMessage !== "Retained fixture error"
                    || page.active || page.data.selected !== "")
                throw new Error("Card exchange reset page state or left Tailscale active")
            root.networkBody().errorMessage = ""
            networkWindow.width = 380
            if (handheldOverlay.status !== Component.Ready)
                throw new Error("Packaged handheld overlay did not compile")
            gameLauncher.launchSteamGamescope()
            for (const name of ["Previous track", "Play", "Next track"])
                if (!root.findAccessible(media, name))
                    throw new Error("Missing named media action: " + name)
            animatedWidget.shown = true
            toggleKeys.tryCompare(animatedWidget, "reveal", 1, 400)
            animatedWidget.shown = false
            if (!animatedWidget.visible || animatedWidget.enabled)
                throw new Error("Closing widget must remain drawn without accepting input")
            toggleKeys.tryCompare(animatedWidget, "visible", false, 400)
            animatedWidget.shown = true
            toggleKeys.tryCompare(animatedWidget, "reveal", 1, 400)
            animatedWidget.animateClose = false
            animatedWidget.shown = false
            if (animatedWidget.visible || animatedWidget.reveal !== 0)
                throw new Error("Instant dismissal must hide the widget immediately")
            toggleWindow.requestActivate()
            toggleKeys.tryCompare(toggleWindow, "active", true)
            keyboardToggle.forceActiveFocus()
            for (const key of [Qt.Key_Return, Qt.Key_Enter]) {
                const previous = keyboardToggle.checked
                const actions = root.toggles
                toggleKeys.keyClick(key)
                if (keyboardToggle.checked === previous || root.toggles !== actions + 1)
                    throw new Error(`Keyboard switch key ${key}: checked=${keyboardToggle.checked}, actions=${root.toggles - actions}, focused=${keyboardToggle.activeFocus}`)
            }
            keyboardButton.forceActiveFocus()
            for (const key of [Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space]) {
                const before = root.buttonCalls
                toggleKeys.keyClick(key)
                if (root.buttonCalls !== before + 1)
                    throw new Error("Shared action button keyboard activation failed")
            }
            if (JSON.stringify(steamShortcuts.commands) !== '[["demo"]]')
                throw new Error("Steam shortcut process result was not published")
            steamShortcuts.refresh()
            const actionNames = ["Lock", "Sleep", "Reboot", "Shutdown"]
            for (const name of actionNames) {
                const button = root.findAccessible(battery, name)
                if (!button) throw new Error("Missing power action: " + name)
                if (button.focusPolicy !== Qt.StrongFocus)
                    throw new Error("Power action is not keyboard focusable: " + name)
                button.click()
                if (root.sessionAction !== name.toLowerCase())
                    throw new Error("Incorrect power action: " + name)
            }
            const lock = root.findAccessible(battery, "Lock")
            if (battery.initialFocus !== lock)
                throw new Error("Power panel initial focus must be Lock")
            if (root.findVisible(unavailableBattery,
                    item => typeof item.text === "string" && item.text.startsWith("Display")))
                throw new Error("Unavailable brightness heading remained visible")
            if (root.findVisible(unavailableBattery,
                    item => typeof item.text === "string" && item.text.startsWith("Brightness")))
                throw new Error("Unavailable brightness status remained visible")
            if (root.findVisible(unavailableBattery,
                    item => item.from === 0 && item.to === 100))
                throw new Error("Unavailable brightness slider remained visible")
            if (root.findVisible(battery,
                    item => item.height === 98 && item.radius === 10))
                throw new Error("Battery card remained visible without a laptop battery")
            if (root.findVisible(battery,
                    item => typeof item.text === "string" && item.text.startsWith("Power rate")))
                throw new Error("Battery rate remained visible without a laptop battery")
            if (!brightness.available || brightness.value !== 37)
                throw new Error("Initial brightness failed")
            brightness.setBrightness(55)
            brightness.setBrightness(76)
            brightness.active = false
            measuredBattery.percentage = 0.20
            measuredBattery.percentage = 0.10
            measuredBattery.percentage = 0.05
            measuredBattery.percentage = 0.03
            chargingBattery.percentage = 0.02
            cancelSleep.start()
            root.performanceHeightBefore = descendants(performance, item => item.metrics !== undefined && item instanceof Flickable)[0].implicitHeight
            performance.metrics = { now: root.now, cpu: { history: [] },
                cpuTemperature: null, memory: { current: null, history: [] }, gpus: [] }
            finish.start()
            } catch (error) { console.error(error + "\\n" + error.stack); Qt.exit(1) }
        }
    }
    Timer {
        id: cancelSleep
        interval: 100
        onTriggered: chargingBattery.state = UPowerDeviceState.Charging
    }

    function checkClipboard() {
        clipboardWindow.visible = true
        clipboardWindow.requestActivate()
        toggleKeys.tryCompare(clipboardWindow, "active", true)
        clipboardPages.openPage("notifications")
        const stack = clipboardPages.currentItem
        if (stack.cards.length !== 2 || stack.selectedCard !== 0
                || stack.cards.map(card => card.accessibleName).join(",") !== "Notifications card,Clipboard card")
            throw new Error("Notifications must initially front Clipboard")
        clipboardPages.focusInitial()
        toggleKeys.keyClick(Qt.Key_Tab)
        toggleKeys.tryCompare(stack, "selectedCard", 1)
        toggleKeys.tryCompare(stack, "exchanging", false)
        const page = descendants(clipboardPages, item => item.history === clipboardFixture)[0]
        if (!page || !root.findVisible(page, item => item.text === "No clipboard history"))
            throw new Error("Clipboard empty state missing")
        const expiry = root.findAccessible(page, "Clipboard history age limit")
        if (!expiry || expiry.currentIndex !== 0 || expiry.count !== 5)
            throw new Error("Clipboard age choices/Off default missing")
        expiry.currentIndex = 2
        expiry.activated(2)
        Config.Settings.clipboardFile.waitForJob()
        toggleKeys.tryCompare(Config.Settings, "clipboardExpiry", 1800)
        Config.Settings.setClipboardExpiry(1)
        toggleKeys.compare(Config.Settings.clipboardExpiry, 1800, "Invalid preference changed age limit")
        clipboardFixture.entries = Array.from({length: 12}, (_, i) => ({id: "epoch:" + i,
            preview: i === 0 ? "<b>literal</b> & fixture" : "Entry " + i,
            image: i >= 1 && i <= 4,
            thumbnail: i === 1 ? Qt.resolvedUrl("clipboard-image.png").toString()
                : i === 2 ? Qt.resolvedUrl("clipboard-broken.png").toString()
                : i === 3 ? Qt.resolvedUrl("clipboard-removed.png").toString() : ""}))
        clipboardFixture.activeEntry = "epoch:0"
        toggleKeys.wait(30)
        const rows = descendants(page, item => item.modelData?.id !== undefined)
        if (rows.length !== 12 || rows.filter(item => item.border.width === 2).length !== 1)
            throw new Error("Clipboard active-selection border missing")
        const load = root.findAccessible(page, "Load clipboard entry: <b>literal</b> & fixture")
        if (!load || !root.findVisible(load.contentItem,
                item => item.text === "<b>literal</b> & fixture" && item.textFormat === Text.PlainText))
            throw new Error("Clipboard preview accepted markup")
        const image = descendants(rows[1], item => item instanceof Image
            && String(item.source) === Qt.resolvedUrl("clipboard-image.png").toString())[0]
        if (!image) throw new Error("Clipboard PNG source did not reach its entry thumbnail")
        toggleKeys.tryCompare(image, "status", Image.Ready)
        toggleKeys.wait(30) // Allow native image geometry to settle after asynchronous decode.
        if (!image.visible || image.cache || !image.asynchronous
                || image.sourceSize.width > 64 || image.sourceSize.height > 48
                || image.paintedWidth > 64 || image.paintedHeight > 48
                || image.paintedHeight <= 0 || Math.abs(image.paintedWidth - 2 * image.paintedHeight) > 0.1) {
            const ancestry = []
            for (let item = image; item && ancestry.length < 16; item = item.parent)
                ancestry.push({object: String(item), visible: item.visible, enabled: item.enabled})
            throw new Error("Clipboard PNG lost bounded aspect-preserving rendering: " + JSON.stringify({
                visible: image.visible, cache: image.cache, asynchronous: image.asynchronous,
                status: image.status, imageFlag: rows[1].modelData.image, rowId: rows[1].modelData.id,
                selectedCard: stack.selectedCard, frontCard: stack.frontCard, pageVisible: page.visible,
                sourceWidth: image.sourceSize.width, sourceHeight: image.sourceSize.height,
                paintedWidth: image.paintedWidth, paintedHeight: image.paintedHeight, ancestry: ancestry}))
        }
        for (const index of [2, 3, 4]) {
            const failed = descendants(rows[index], item => item instanceof Image)[0]
            toggleKeys.tryCompare(failed, "status", index === 4 ? Image.Null : Image.Error)
            if (failed.visible || !root.findVisible(rows[index],
                    item => item.text === "PNG image · preview unavailable"))
                throw new Error("Invalid, removed or unavailable PNG lost its fallback")
        }
        const imageLoad = root.findAccessible(rows[1], "Load clipboard entry: PNG image")
        imageLoad.forceActiveFocus()
        toggleKeys.keyPress(Qt.Key_Return)
        if (clipboardFixture.calls.length) throw new Error("PNG load ran before release")
        toggleKeys.keyRelease(Qt.Key_Return)
        root.findAccessible(rows[1], "Paste clipboard entry: PNG image").click()
        root.findAccessible(rows[1], "Remove clipboard entry: PNG image").click()
        if (JSON.stringify(clipboardFixture.calls) !== JSON.stringify([["load", "epoch:1"], ["remove", "epoch:1"]])
                || JSON.stringify(clipboardWindow.pastes) !== JSON.stringify(["epoch:1"]))
            throw new Error("PNG entry controls lost stable identity")
        clipboardFixture.calls = []
        clipboardWindow.pastes = []
        load.forceActiveFocus()
        toggleKeys.keyPress(Qt.Key_Return)
        if (clipboardFixture.calls.length) throw new Error("Clipboard load ran before release")
        toggleKeys.keyRelease(Qt.Key_Return)
        const paste = root.findAccessible(page, "Paste clipboard entry: <b>literal</b> & fixture")
        paste.click()
        const remove = root.findAccessible(page, "Remove clipboard entry: <b>literal</b> & fixture")
        remove.click()
        if (JSON.stringify(clipboardFixture.calls) !== JSON.stringify([["load", "epoch:0"], ["remove", "epoch:0"]])
                || JSON.stringify(clipboardWindow.pastes) !== JSON.stringify(["epoch:0"]))
            throw new Error("Clipboard row actions bubbled or used an unstable identity")
        const scroll = descendants(page, item => item instanceof Flickable)[0]
        if (!scroll || scroll.contentHeight <= scroll.height)
            throw new Error("Clipboard history does not scroll inside its card")
        const last = root.findAccessible(page, "Remove clipboard entry: Entry 11")
        last.forceActiveFocus()
        clipboardPages.revealFocus()
        toggleKeys.wait(30)
        if (scroll.contentY <= scroll.originY) throw new Error("Focused clipboard action was not revealed")
        clipboardFixture.activeEntry = ""
        toggleKeys.wait(20)
        if (rows.some(item => item.border.width)) throw new Error("Unknown clipboard kept a stale accent")
        clipboardFixture.error = "Fixture operation failed"
        toggleKeys.wait(20)
        if (!root.findVisible(page, item => item.text === clipboardFixture.error))
            throw new Error("Clipboard operation failure is hidden")
        clipboardFixture.entries = []
        toggleKeys.wait(20)
        if (descendants(page, item => item.modelData?.id !== undefined).length)
            throw new Error("Cleared clipboard retained entry delegates")
        clipboardPages.openPage("notifications")
        toggleKeys.tryCompare(stack, "selectedCard", 0)
        clipboardWindow.visible = false
        clipboardAdapter.locked = false
        toggleKeys.tryCompare(clipboardAdapter, "available", true)
        const request = clipboardAdapter.request("load", "fixture:1")
        toggleKeys.tryCompare(clipboardAdapter, "busy", false)
        if (clipboardAdapter.confirmations.join(",") !== String(request)
                || clipboardAdapter.activeEntry !== "fixture:1")
            throw new Error("Clipboard adapter lost request confirmation/current selection")
        clipboardAdapter.receive(JSON.stringify({entries: [{id: "fixture:image", image: true,
            thumbnail: Qt.resolvedUrl("clipboard-image.png").toString()}], active: "fixture:image"}))
        clipboardAdapter.locked = true
        clipboardAdapter.receive(JSON.stringify({entries: [{id: "stale", image: true,
            thumbnail: Qt.resolvedUrl("clipboard-image.png").toString()}], active: "stale"}))
        if (clipboardAdapter.entries.length || clipboardAdapter.activeEntry || clipboardAdapter.available)
            throw new Error("Locked clipboard accepted late state")
    }

    function findAccessible(item, name) {
        if (item.Accessible?.name === name) return item
        for (const child of item.children ?? []) {
            const result = findAccessible(child, name)
            if (result) return result
        }
        return null
    }
    function findVisible(item, predicate) {
        if (item.visible && predicate(item)) return item
        for (const child of item.children ?? []) {
            const result = findVisible(child, predicate)
            if (result) return result
        }
        return null
    }
    Timer {
        id: finish
        interval: 1200
        onTriggered: {
            if (!gameLauncher.steamLaunching || !gameLauncher.pendingSteamCommand)
                throw new Error("Native Steam service query did not resolve a launch")
            gameLauncher.finishSteamLaunch()
            if (steamShortcuts.commands.length !== 0)
                throw new Error("Failed Steam shortcut refresh left stale filtering")
            if (!brightness.available || brightness.value !== 76)
                throw new Error("Pending brightness did not survive popup closure")
            if (root.sleepCalls !== 2)
                throw new Error("Battery sleep was missed or repeated after charging")
            if (network.history.length !== 2 || network.history[1].values[0] !== 0)
                throw new Error("Network sampler did not read counters")
            if (descendants(performance, item => item.metrics !== undefined && item instanceof Flickable)[0].implicitHeight <= 0
                    || descendants(performance, item => item.metrics !== undefined && item instanceof Flickable)[0].implicitHeight >= root.performanceHeightBefore)
                throw new Error("Performance popup did not shrink after GPU removal")
            if (coldGraph.minimum !== -5 || coldGraph.maximum !== 100)
                throw new Error("Temperature axis must include negative values and expire old samples")
            for (const sampler of [systemMetrics.cpu, systemMetrics.memory]) {
                const values = sampler.history
                const value = values[values.length - 1]?.values[0]
                if (values.length < 2 || value === null || !Number.isFinite(value)
                        || value < 0 || value > 100)
                    throw new Error("Live CPU/RAM sampling failed")
            }
            try {
                root.checkSharedCards(); root.checkBackgroundCards(); root.checkLayoutCards()
                root.checkPopoutFocus(); root.checkPowerCards(); root.checkAudioCards(); root.checkTailscaleConnection(); root.checkTailscaleLifetime()
                root.checkRetainedNetworkFocus()
            }
            catch (error) { console.error(error + "\\n" + error.stack); Qt.exit(1); return }
            console.log("CONTROL_CHECK_PASSED")
            Qt.quit()
        }
    }
}
"""

STACKS_QML = """import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import Quickshell.Io
import qs.config as Config
import "icewine/modules/topbar" as Bar
import "icewine/modules/topbar/CardModules.js" as Cards
import "icewine/modules/ShellState.js" as State
import "icewine/theme" as Theme
ShellRoot {
    QtObject {
        id: compositor
        property bool layoutAvailable: true
        property bool layoutPending: false
        property int layoutWorkspaceId: 1
        property string layoutError: ""
        property string layoutUnavailable: ""
        property var layoutStatus: ({effective: "master", autofullscreen: false})
        function selectLayout(choice) {}
        function selectAutofullscreen(choice) {}
        function activateWindow(address) {}
    }
    QtObject {
        id: service
        property int count: 0
        property var items: []
        property bool doNotDisturb: false
        property int highestUrgency: 0
        property int pulseToken: 0
        property bool keepAwake: false
        property var entries: []
        property bool available: true
        property bool busy: false
        property string error: ""
        property string activeEntry: ""
        function request() {}
        function requestLock() {}
        function requestSleep() {}
        function requestReboot() {}
        function requestShutdown() {}
    }
    SignalSpy { id: keyboardActions; target: host; signalName: "keyboardRequested" }
    FileView { id: dark; path: Qt.resolvedUrl("palette-dark.json"); blockAllReads: true }
    FileView { id: light; path: Qt.resolvedUrl("palette-light.json"); blockAllReads: true }
    Window {
        id: window
        visible: true
        width: 500; height: 620
        Bar.StatusPopout {
            id: host
            anchors.fill: parent
            compositor: compositor
            notificationService: service
            session: service
            powerState: service
            clipboardHistory: service
            monitorName: "fixture-no-screen"
            metrics: ({now: Date.now(), network: {history: []}, cpu: {history: []}, cpuTemperature: null,
                memory: {current: {usedGiB: 0, totalGiB: 1}, history: []}, gpus: []})
            backgroundItems: [{id: "fixture", title: "App", icon: "", status: 0, hasMenu: false, activate() {}}]
            engaged: true
        }
        Bar.StatusIcons {
            id: icons
            notificationService: service
            cardStacks: host.cardStacks
        }
        TestCase { id: input; when: false }
    }
    Timer {
        interval: 200; running: true
        onTriggered: {
            try {
                window.requestActivate()
                input.tryCompare(window, "active", true)
                // Existing preference files acquire the defaults without losing booleans.
                const file = Config.Settings.widgetsFile
                file.blockWrites = true // Serialise fixture writes before explicit reloads.
                file.setText(JSON.stringify({notificationToasts: false}))
                file.reload()
                input.tryCompare(Config.Settings, "notificationToasts", false)
                input.compare(Config.Settings.cardStacks.length, 6)
                input.compare(Config.Settings.barBehaviour, "keyboard")
                input.compare(Config.Settings.barLocation, "above")
                for (const behaviour of Cards.barBehaviours) for (const location of Cards.barLocations) {
                    file.setText(JSON.stringify({barBehaviour: behaviour, barLocation: location}))
                    file.reload()
                    input.tryCompare(Config.Settings, "barBehaviour", behaviour)
                    input.tryCompare(Config.Settings, "barLocation", location)
                }
                for (const invalid of [{barBehaviour: "unknown"}, {barLocation: false}]) {
                    file.setText(JSON.stringify(invalid))
                    file.reload()
                    input.wait(30)
                    input.compare(Config.Settings.barBehaviour, "always")
                    input.compare(Config.Settings.barLocation, "bottom")
                }
                input.compare(Config.Settings.oskAccess, "none")
                for (const access of Cards.oskAccessModes) {
                    file.setText(JSON.stringify({oskAccess: access}))
                    file.reload()
                    input.tryCompare(Config.Settings, "oskAccess", access)
                }
                file.setText(JSON.stringify({oskAccess: "invalid"}))
                file.reload(); input.wait(30)
                input.compare(Config.Settings.oskAccess, "topbar", "Bad saved input retains last good mode")
                host.cardStacks = [{id: "osk", modules: ["launcher"]}]
                host.currentPage = "launcher"
                input.wait(40)
                const launcher = host.cardFor("launcher")
                for (const access of ["none", "launcher", "topbar"]) {
                    file.setText(JSON.stringify({oskAccess: access}))
                    file.reload(); input.tryCompare(Config.Settings, "oskAccess", access)
                    host.openPage("launcher"); host.focusInitial()
                    const search = launcher.initialFocus
                    search.text = "osk"
                    input.wait(30)
                    const before = keyboardActions.count
                    input.keyClick(Qt.Key_Return)
                    input.compare(keyboardActions.count, before + (access === "launcher" ? 1 : 0))
                }
                file.setText(JSON.stringify({oskAccess: "launcher"}))
                file.reload(); input.tryCompare(Config.Settings, "oskAccess", "launcher")
                host.focusInitial(); launcher.initialFocus.text = "osk"; input.wait(30)
                const before = keyboardActions.count
                function findResults(item) {
                    if (item instanceof ListView) return item
                    for (const child of item.children ?? []) {
                        const result = findResults(child)
                        if (result) return result
                    }
                    return null
                }
                const results = findResults(launcher)
                input.verify(results.currentItem !== null)
                const touchAction = input.touchEvent(window)
                touchAction.press(0, results.currentItem, 60, 20).commit()
                touchAction.release(0, results.currentItem, 60, 20).commit()
                input.compare(keyboardActions.count, before + 1, "Touch dispatches the real Launcher action")
                host.focusInitial()
                input.keyPress(Qt.Key_Return)
                file.setText(JSON.stringify({oskAccess: "none"}))
                file.reload(); input.tryCompare(Config.Settings, "oskAccess", "none")
                input.keyRelease(Qt.Key_Return)
                input.compare(keyboardActions.count, before + 1, "Mode change cancels armed Enter")
                host.cardStacks = Qt.binding(() => Config.Settings.cardStacks)
                const mixed = [{id: "mixed", modules: ["notifications", "layout", "audio", "launcher"]}]
                file.setText(JSON.stringify({notificationToasts: false, cardStacks: mixed}))
                file.reload()
                input.tryVerify(() => Config.Settings.cardStacks[0]?.id === "mixed")
                for (const invalid of ["{", JSON.stringify({cardStacks: [{id: "bad", modules: ["stale"]}]})]) {
                    file.setText(invalid)
                    file.reload()
                    input.wait(30)
                    input.compare(Config.Settings.cardStacks[0].id, "mixed")
                }
                host.currentPage = "notifications"
                input.wait(40)
                const stack = host.currentItem
                input.compare(stack.cards.length, 4)
                for (const palette of [light, dark]) {
                    Theme.Palette.file.setText(palette.text())
                    input.verify(Theme.Palette.refresh())
                    input.wait(220)
                    const colours = [Theme.Palette.primary, Theme.Palette.secondary, Theme.Palette.tertiary, Theme.Palette.primary]
                    input.compare(stack.cards.map(card => card.accent.toString()).join(","), colours.map(String).join(","))
                    for (let index = 0; index < 4; ++index) {
                        stack.selectCard(index)
                        input.tryCompare(stack, "exchanging", false, 900)
                        input.compare(stack.frontCard, index)
                        const row = icons.children.find(item => item.children.some(child => child.page !== undefined))
                        input.compare(row.children.filter(item => item.page !== undefined)[0].page, "notifications")
                        input.compare(new Set(stack.cards.map(card => card.y)).size, 4)
                    }
                }
                host.focusInitial()
                input.keyClick(Qt.Key_Tab)
                input.tryCompare(stack, "exchanging", false, 900)
                input.compare(stack.frontCard, 0)
                input.keyClick(Qt.Key_Backtab)
                input.tryCompare(stack, "exchanging", false, 900)
                input.compare(stack.frontCard, 3)
                const touch = input.touchEvent(window)
                touch.press(0, stack.cards[0], 8, 6).commit()
                touch.release(0, stack.cards[0], 8, 6).commit()
                input.tryCompare(stack, "exchanging", false, 900)
                input.compare(stack.frontCard, 0)
                stack.selectCard(3)
                input.tryCompare(stack, "exchanging", false, 900)
                host.cardStacks = mixed.concat([{id: "other", modules: ["clipboard"]}])
                host.currentPage = "clipboard"
                input.wait(40)
                host.currentPage = "notifications"
                input.wait(40)
                input.tryCompare(stack, "exchanging", false, 900)
                input.compare(stack.frontCard, 3)
                host.openPage("notifications")
                input.tryCompare(stack, "exchanging", false, 900)
                input.compare(stack.frontCard, 0)
                host.backgroundItems = []
                host.layoutsEnabled = false
                host.cardStacks = [{id: "filtered", modules: ["background", "layout", "audio"]}]
                host.currentPage = "audio"
                input.wait(40)
                input.compare(stack.cards.length, 1)
                input.compare(stack.cards[0].accent.toString(), Theme.Palette.tertiary.toString())
                icons.layoutsEnabled = false
                input.compare(icons.openingPage("background"), "audio")
                host.layoutsEnabled = true
                host.backgroundItems = [{id: "fixture", title: "App", icon: "", status: 0, hasMenu: false, activate() {}}]
                // Every current module can use the same host as a single card.
                for (const name of Cards.modules) {
                    input.compare(State.reduce(State.initial(), {type: "open", page: name,
                        engaged: true, screen: "fixture"}).page, name)
                    host.cardStacks = [{id: "single", modules: [name]}]
                    host.currentPage = name
                    input.wait(40)
                    input.compare(stack.cards.length, 1)
                    input.verify(!host.floatingCards)
                    input.compare(stack.cards[0].index, 0)
                    input.compare(stack.cards[0].accent.toString(), Theme.Palette.primary.toString())
                    input.verify(stack.cards[0].implicitHeight > 0)
                }
                host.cardStacks = []
                input.wait(30)
                input.compare(stack.cards.length, 0)
                input.compare(host.implicitHeight, 0)
                file.setText("{}")
                file.reload()
                console.log("STACKS_CHECK_PASSED")
                Qt.quit()
            } catch (error) { console.error(error + "\\n" + error.stack); Qt.exit(1) }
        }
    }
}
"""

# Separate run so rendering waits cannot disturb the metric/lifecycle timers.
STATUS_ICONS_QML = """import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import qs.config as Config
import "icewine/modules/topbar" as Bar
ShellRoot {
    Window {
        visible: true
        width: 300; height: 80
        Bar.StatusIcons {
            id: icons
            width: implicitWidth; height: implicitHeight
            notificationService: ({count: 1, highestUrgency: 1, doNotDisturb: false, pulseToken: 0})
            property string activated: ""
            property int keyboardActions: 0
            onKeyboardRequested: keyboardActions++
            onPopoutActivated: page => activated = page
        }
        TestCase { id: input; when: false }
    }
    Timer {
        interval: 100; running: true
        onTriggered: {
            try {
                const row = icons.children.find(item => item.children.filter(child => child.page !== undefined).length > 0)
                const buttons = row.children.filter(item => item.page !== undefined && item.visible)
                input.compare(buttons.map(item => item.page).join(","), "launcher,media,audio,network,notifications,battery")
                const snapshot = {}
                for (const field of icons.iconSnapshot().split(" ")) { const parts = field.split("="); snapshot[parts[0]] = parts[1] }
                input.compare(Object.keys(snapshot).length, 13)
                for (const button of buttons) input.compare(snapshot[button.page], button.icon)
                input.compare(icons.implicitWidth, row.implicitWidth + 9)
                input.compare(icons.battery, null)
                input.compare(buttons[5].label, "")
                for (let i = 0; i < buttons.length; ++i) {
                    const button = buttons[i]
                    input.verify(button.visible)
                    if (i) {
                        input.compare(button.x, buttons[i - 1].x + buttons[i - 1].width + row.spacing)
                        icons.updateHoveredPage(row.mapToItem(icons, button.x - row.spacing / 2, button.height / 2))
                        input.compare(icons.hoveredPage, "")
                    }
                    const point = button.mapToItem(icons, button.width / 2, button.height / 2)
                    icons.updateHoveredPage(point)
                    input.compare(icons.hoveredPage, button.page)
                    input.mouseClick(button, button.width / 2, button.height / 2)
                    input.compare(icons.activated, button.page)
                }
                icons.sink.audio.muted = true
                input.tryCompare(icons, "muted", true)
                input.compare(icons.iconFor("audio"), "󰝟")
                input.verify(icons.iconSnapshot().includes("audio=󰝟"))
                const volume = icons.sink.audio.volume
                const audio = buttons[2]
                input.mouseWheel(audio, audio.width / 2, audio.height / 2, 0, 120)
                input.tryCompare(icons.sink.audio, "muted", false)
                input.verify(icons.sink.audio.volume > volume)
                icons.cardStacks = []
                input.verify(!icons.visible)
                Config.Settings.widgetSelections = {oskAccess: "topbar"}
                input.wait(30)
                input.verify(icons.visible)
                const keyboard = row.children.find(item => item.page === "keyboard")
                input.verify(keyboard.visible)
                input.compare(keyboard.Accessible.name, "Onscreen Keyboard")
                input.compare(icons.implicitWidth, keyboard.width + 9)
                icons.updateHoveredPage(keyboard.mapToItem(icons, keyboard.width / 2, keyboard.height / 2))
                input.compare(icons.hoveredPage, "", "OSK action never previews a card")
                input.mouseClick(keyboard, keyboard.width / 2, keyboard.height / 2)
                input.compare(icons.keyboardActions, 1)
                const touch = input.touchEvent(keyboard.Window.window)
                touch.press(0, keyboard, 8, 8).commit()
                touch.release(0, keyboard, 8, 8).commit()
                input.compare(icons.keyboardActions, 2)
                input.mousePress(keyboard, keyboard.width / 2, keyboard.height / 2)
                Config.Settings.widgetSelections = {oskAccess: "none"}
                input.wait(30)
                input.mouseRelease(keyboard, keyboard.width / 2, keyboard.height / 2)
                input.compare(icons.keyboardActions, 2, "Hidden action cancels pending mouse release")
                input.verify(!icons.visible)
                Config.Settings.widgetSelections = {oskAccess: "launcher"}
                input.verify(!icons.visible)
                console.log("STATUS_ICONS_CHECK_PASSED")
                Qt.quit()
            } catch (error) { console.error(error + "\\n" + error.stack); Qt.exit(1) }
        }
    }
}
"""

ARROW_QML = """import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtTest
import Quickshell
import "icewine/modules/topbar" as Bar
import "icewine/modules/topbar/popouts" as Popouts
ShellRoot {
    Window {
        id: window
        visible: true
        width: 500; height: 600
        property int activations: 0
        Item {
            anchors.fill: parent
            property int bubbled: 0
            id: boundary
            Keys.priority: Keys.AfterItem
            Keys.onPressed: event => { if ([Qt.Key_Left, Qt.Key_Right].includes(event.key)) ++bubbled }
            Bar.CardStack {
                id: stack
                anchors.fill: parent
                cards: [first, second]
                Bar.Card {
                    id: first
                    stack: stack
                    arrowKeyOwners: [customButton, directionalGroup]
                    Slider { id: slider; y: 50; from: 0; to: 1; stepSize: 0.1; value: 0.5 }
                    ScrollBar { id: bar; y: 100; width: 200; orientation: Qt.Horizontal; size: 0.2 }
                    TextField { id: field; y: 150; text: "abc" }
                    TextEdit { id: edit; y: 200; text: "abc" }
                    Button { id: button; y: 300; text: "Native button"; onClicked: ++window.activations }
                    Popouts.ActionButton { id: action; y: 350; text: "Real action"; onClicked: ++window.activations }
                    Popouts.Toggle { id: toggle; y: 400; text: "Real toggle"; onToggled: ++window.activations }
                    Button { id: disabled; enabled: false }
                    Button { id: hidden; visible: false }
                    ToolButton { id: tool; text: "Tool" }
                    ButtonGroup { id: nativeGroup }
                    Button { id: grouped; checkable: true; checked: true; ButtonGroup.group: nativeGroup }
                    RadioButton { id: radio; text: "Radio" }
                    TabButton { id: tab; text: "Tab" }
                    MenuItem { id: entry; text: "Menu entry" }
                    Button {
                        id: customButton
                        property int value: 0
                        Keys.onPressed: event => {
                            if (event.key === Qt.Key_Right && value < 1) { ++value; event.accepted = true }
                        }
                    }
                    Item {
                        id: directionalGroup
                        Button { id: groupStart; KeyNavigation.right: groupEnd }
                        Button { id: groupEnd; x: 100; KeyNavigation.left: groupStart }
                    }
                    // A custom owner deliberately ignores its endpoint, like native text controls.
                    Item {
                        id: custom
                        y: 250; width: 100; height: 30
                        property int value: 0
                        Keys.onPressed: event => {
                            if (event.key === Qt.Key_Right && value < 1) { ++value; event.accepted = true }
                        }
                    }
                    Menu {
                        id: menu
                        Menu {
                            id: submenu
                            title: "Nested"
                            MenuItem { text: "Entry" }
                        }
                        MenuItem { text: "Last" }
                    }
                }
                Bar.Card { id: second; stack: stack; index: 1
                    Button { id: rear; enabled: second.active }
                    TextInput { id: nonTab; text: "no Tab focus policy" }
                }
            }
        }
        TestCase { id: keys; when: false }
    }
    function unchanged(item, key, modifiers = Qt.NoModifier) {
        item.forceActiveFocus()
        keys.keyClick(key, modifiers)
        if (stack.selectedCard !== 0 || stack.exchanging) throw new Error("Control arrow escaped: " + item)
    }
    Timer {
        interval: 100; running: true
        onTriggered: {
            try {
                window.requestActivate()
                keys.tryCompare(window, "active", true)
                field.cursorPosition = field.length
                edit.cursorPosition = edit.length
                for (const item of [slider, bar, field, edit, custom]) {
                    unchanged(item, Qt.Key_Right)
                    unchanged(item, Qt.Key_Left)
                }
                if (slider.value !== 0.5 || field.cursorPosition !== 2 || edit.cursorPosition !== 2
                        || custom.value !== 1) throw new Error("Native/custom controls lost their arrow handling")
                for (const endpoint of [0, 1]) {
                    slider.value = endpoint
                    unchanged(slider, endpoint ? Qt.Key_Right : Qt.Key_Left)
                    if (slider.value !== endpoint) throw new Error("Slider endpoint changed")
                    bar.position = endpoint ? 0.8 : 0
                    unchanged(bar, endpoint ? Qt.Key_Right : Qt.Key_Left)
                    for (const text of [field, edit]) {
                        text.cursorPosition = endpoint ? text.length : 0
                        const before = boundary.bubbled
                        unchanged(text, endpoint ? Qt.Key_Right : Qt.Key_Left)
                        if (boundary.bubbled !== before + 1) throw new Error("Expected native text endpoint bubbling")
                        unchanged(text, endpoint ? Qt.Key_Right : Qt.Key_Left, Qt.ShiftModifier)
                        unchanged(text, endpoint ? Qt.Key_Right : Qt.Key_Left, Qt.ControlModifier)
                    }
                }
                // Literal tabs stay in multiline editing; ordinary text fields switch cards.
                edit.forceActiveFocus()
                keys.keyClick(Qt.Key_Tab)
                if (stack.selectedCard !== 0 || !edit.text.includes("\t"))
                    throw new Error("Multiline literal Tab escaped")
                field.forceActiveFocus()
                keys.keyClick(Qt.Key_Tab)
                keys.tryCompare(stack, "exchanging", false, 900)
                if (stack.selectedCard !== 1) throw new Error("Text field Tab did not switch cards")
                keys.keyClick(Qt.Key_Tab, Qt.ShiftModifier)
                keys.tryCompare(stack, "exchanging", false, 900)
                if (stack.selectedCard !== 0) throw new Error("Shift+Tab did not return")
                toggle.forceActiveFocus()
                keys.keyClick(Qt.Key_Right)
                if (!tool.activeFocus) throw new Error("Hidden/disabled controls were not skipped")
                slider.forceActiveFocus()
                keys.keyClick(Qt.Key_Tab, Qt.ControlModifier)
                if (!field.activeFocus) throw new Error("Native arrow owner has no explicit traversal escape")
                keys.keyClick(Qt.Key_Tab, Qt.ControlModifier | Qt.ShiftModifier)
                if (!slider.activeFocus) throw new Error("Reverse explicit traversal failed")
                // Ordinary controls follow native focus-chain order without activation.
                for (const [item, key, expected] of [[button, Qt.Key_Right, action],
                        [action, Qt.Key_Down, toggle], [toggle, Qt.Key_Left, action],
                        [action, Qt.Key_Up, button]]) {
                    item.forceActiveFocus()
                    keys.keyClick(key)
                    if (!expected.activeFocus || stack.selectedCard !== 0 || stack.exchanging)
                        throw new Error("Bounded control focus failed: " + item + " -> " + window.activeFocusItem)
                }
                if (window.activations !== 0 || toggle.checked || !grouped.checked)
                    throw new Error("Arrow navigation activated content")
                action.forceActiveFocus()
                keys.keyPress(Qt.Key_Return)
                keys.keyClick(Qt.Key_Tab)
                keys.keyRelease(Qt.Key_Return)
                keys.tryCompare(stack, "exchanging", false, 900)
                if (window.activations !== 0 || action.activationKey !== 0)
                    throw new Error("Tab released a stale button activation")
                keys.keyClick(Qt.Key_Backtab)
                keys.tryCompare(stack, "exchanging", false, 900)
                for (const item of [radio, tab, entry]) {
                    unchanged(item, Qt.Key_Left)
                    unchanged(item, Qt.Key_Right)
                }
                unchanged(customButton, Qt.Key_Right)
                if (customButton.value !== 1) throw new Error("Custom button lost first key handling")
                const ownerBefore = boundary.bubbled
                unchanged(customButton, Qt.Key_Right)
                unchanged(customButton, Qt.Key_Left)
                if (boundary.bubbled !== ownerBefore + 2) throw new Error("Custom button endpoint did not bubble")
                groupStart.forceActiveFocus()
                keys.keyClick(Qt.Key_Right)
                if (!groupEnd.activeFocus || stack.selectedCard !== 0) throw new Error("Native group navigation failed")
                unchanged(groupEnd, Qt.Key_Right)
                groupEnd.forceActiveFocus()
                keys.keyClick(Qt.Key_Left)
                if (!groupStart.activeFocus || stack.selectedCard !== 0) throw new Error("Native group reversal failed")
                unchanged(groupStart, Qt.Key_Left)
                field.cursorPosition = 0
                unchanged(field, Qt.Key_Right, Qt.ShiftModifier)
                if (field.selectedText !== "a") throw new Error("Native text selection failed")
                custom.value = 1
                const before = boundary.bubbled
                unchanged(custom, Qt.Key_Right)
                if (boundary.bubbled !== before + 1) throw new Error("Custom endpoint did not reach shared boundary")
                menu.popup()
                keys.tryCompare(menu, "visible", true)
                menu.currentIndex = 0
                menu.itemAt(0).forceActiveFocus()
                keys.keyClick(Qt.Key_Right)
                keys.tryCompare(submenu, "visible", true)
                keys.keyClick(Qt.Key_Left)
                keys.tryCompare(submenu, "visible", false)
                menu.currentIndex = 1
                menu.itemAt(1).forceActiveFocus()
                keys.keyClick(Qt.Key_Right)
                if (stack.selectedCard !== 0 || stack.exchanging) throw new Error("Nested menu arrow escaped")
                keys.keyClick(Qt.Key_Tab)
                if (stack.selectedCard !== 0 || stack.exchanging) throw new Error("Menu Tab escaped to stack")
                menu.close()
                keys.tryCompare(menu, "visible", false)

                // Resetting the selected card cancels release activation without focus loss.
                for (const key of [Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space]) {
                    first.selector.forceActiveFocus()
                    keys.keyPress(key)
                    stack.resetSelection()
                    keys.keyRelease(key)
                    if (stack.selectedCard !== 0 || stack.exchanging || first.selector.activationKey !== 0)
                        throw new Error("Selector retained stale activation after reset")
                }
                // A one-control card wraps locally; arrows never walk into the rear card.
                keys.keyClick(Qt.Key_Tab)
                keys.tryCompare(stack, "exchanging", false, 900)
                keys.keyClick(Qt.Key_Down)
                if (!rear.activeFocus) throw new Error("Selector did not enter the card")
                for (const key of [Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down]) {
                    keys.keyClick(key)
                    if (!rear.activeFocus || stack.selectedCard !== 1)
                        throw new Error("Single-control focus escaped its card")
                }
                // A non-Tab focus target with no other controls must terminate traversal.
                rear.enabled = false
                nonTab.forceActiveFocus()
                keys.keyClick(Qt.Key_Tab, Qt.ControlModifier)
                if (!nonTab.activeFocus) throw new Error("Empty control chain lost its native target")
                rear.enabled = true
                keys.keyClick(Qt.Key_Backtab)
                keys.tryCompare(stack, "exchanging", false, 900)
                // A superseding selection cancels a pending motion key without focus loss.
                for (const key of [Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space]) {
                    first.selector.forceActiveFocus()
                    keys.keyClick(Qt.Key_Tab)
                    keys.wait(30)
                    const motion = window.activeFocusItem
                    if (motion !== stack.motionInitialFocus || !stack.exchanging)
                        throw new Error("Expected stationary motion focus before pending activation selected=" + stack.selectedCard + " motion=" + stack.exchanging + " focus=" + motion)
                    keys.keyPress(key)
                    if (motion.activationKey !== key) throw new Error("Motion activation was not armed")
                    keys.keyClick(Qt.Key_Backtab)
                    if (stack.selectedCard !== 0 || window.activeFocusItem !== motion)
                        throw new Error("Tab reversal lost selection or stationary focus")
                    keys.keyRelease(key)
                    if (stack.selectedCard !== 0 || motion.activationKey !== 0)
                        throw new Error("Stale motion activation undid Tab reversal: " + key)
                    keys.tryCompare(stack, "exchanging", false, 900)
                    if (!first.selector.activeFocus) throw new Error("Reversal lost selected focus")
                }
                // Real presses, reversal, and fresh repeated presses use the shared path.
                first.selector.forceActiveFocus()
                keys.keyPress(Qt.Key_Tab)
                if (stack.selectedCard !== 1 || !stack.exchanging) throw new Error("Tab did not select next")
                keys.keyRelease(Qt.Key_Tab)
                keys.wait(20)
                keys.keyClick(Qt.Key_Backtab)
                if (stack.selectedCard !== 0) throw new Error("Backtab did not reverse to previous")
                keys.tryCompare(stack, "exchanging", false, 900)
                for (const key of [Qt.Key_Backtab, Qt.Key_Tab, Qt.Key_Tab, Qt.Key_Backtab]) {
                    const expected = 1 - stack.selectedCard
                    keys.keyClick(key)
                    if (stack.selectedCard !== expected) throw new Error("Cyclic pair endpoint failed")
                    keys.tryCompare(stack, "exchanging", false, 900)
                    if (!stack.initialFocus.activeFocus) throw new Error("Navigation lost visible selector focus")
                }
                first.selector.focus = false
                stack.forceActiveFocus()
                if (window.activeFocusItem !== stack) throw new Error("Fixture did not focus stack itself")
                keys.keyClick(Qt.Key_Tab)
                keys.tryCompare(stack, "exchanging", false, 900)
                second.forceActiveFocus()
                if (window.activeFocusItem !== second) throw new Error("Fixture did not focus card itself")
                keys.keyClick(Qt.Key_Backtab)
                keys.tryCompare(stack, "exchanging", false, 900)
                stack.cards = [first]
                first.selector.forceActiveFocus()
                keys.keyClick(Qt.Key_Tab); keys.keyClick(Qt.Key_Backtab)
                if (stack.selectedCard !== 0 || stack.exchanging || !first.selector.activeFocus)
                    throw new Error("Single-card Tab lost bounded focus")
                stack.cards = [first, second]
                for (const property of ["visible", "enabled"]) {
                    first.selector.forceActiveFocus()
                    stack[property] = false
                    stack.cycleCard(1)
                    keys.keyClick(Qt.Key_Tab)
                    if (stack.selectedCard !== 0 || stack.exchanging)
                        throw new Error("Unavailable stack navigated or consumed")
                    stack[property] = true
                }
                console.log("ARROW_CHECK_PASSED")
                Qt.quit()
            } catch (error) { console.error(error + "\\n" + error.stack); Qt.exit(1) }
        }
    }
}
"""

MENU_QML = """import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import Quickshell.Io
import "icewine/modules/topbar/popouts" as Popouts
import "icewine/theme" as Theme
ShellRoot {
    id: root
    Window {
        id: networkPages
        visible: true; width: 760; height: 600
        Popouts.Tailscale { id: page; width: 380; height: 500; active: true }
        TestCase { id: networkKeys; when: false }
    }
    function descendants(item, predicate) {
        let result = predicate(item) ? [item] : []
        for (const child of item.children ?? []) result = result.concat(descendants(child, predicate))
        return result
    }
    FileView { id: darkPalette; path: Qt.resolvedUrl("palette-dark.json"); blockAllReads: true }
    FileView { id: lightPalette; path: Qt.resolvedUrl("palette-light.json"); blockAllReads: true }
    function luminance(color) {
        const linear = value => value <= 0.04045 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4)
        return 0.2126 * linear(color.r) + 0.7152 * linear(color.g) + 0.0722 * linear(color.b)
    }
    function contrast(first, second) {
        // Checkmark images use translucent ink; compare its composite against the box.
        first = Qt.rgba(first.r * first.a + second.r * (1 - first.a),
                        first.g * first.a + second.g * (1 - first.a),
                        first.b * first.a + second.b * (1 - first.a), 1)
        const a = luminance(first), b = luminance(second)
        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
    }
    function captureMenu(menu, name) {
        const image = networkKeys.grabImage(menu.contentItem.parent)
        const directory = Quickshell.env("ICEWINE_CONTROL_CAPTURES")
        if (directory) image.save(directory + "/" + name + ".png")
        return image
    }
    function checkMenuSurface(menu, name) {
        const image = captureMenu(menu, name)
        // Sample the empty right edge of an unhighlighted row, not the assigned palette.
        const background = image.pixel(image.width - 6, 8)
        if (background.toString() !== Theme.Palette.surface.toString()
                || contrast(menu.itemAt(0).contentItem.color, background) < 4.5)
            throw new Error(name + ": rendered menu background/text mismatch: " + background)
    }
    function checkMenuStates(menu, page, label) {
        menu.currentIndex = -1
        networkKeys.wait(30)
        checkMenuSurface(menu, label + "-normal")
        const row = menu.itemAt(1)
        row.forceActiveFocus()
        menu.currentIndex = 1
        networkKeys.wait(30)
        if (!row.activeFocus || !row.highlighted
                || contrast(row.contentItem.color, row.background.color) < 4.5)
            throw new Error(label + ": keyboard highlight is unreadable: focus=" + row.activeFocus + " highlighted=" + row.highlighted + " colors=" + row.contentItem.color + "/" + row.background.color + " contrast=" + contrast(row.contentItem.color, row.background.color))
        captureMenu(menu, label + "-focus")
        menu.currentIndex = -1
        networkKeys.mouseMove(row, row.width / 2, row.height / 2)
        networkKeys.wait(40)
        if (!row.hovered || !row.highlighted
                || contrast(row.contentItem.color, row.background.color) < 4.5)
            throw new Error(label + ": mouse hover is unreadable: hovered=" + row.hovered + " hoverEnabled=" + row.hoverEnabled + " highlighted=" + row.highlighted)
        captureMenu(menu, label + "-hover")
        networkKeys.mouseMove(networkPages, 0, networkPages.height - 1)
        menu.currentIndex = -1
        const originalData = page.data
        const id = menu.title === "Australia" ? "fixture-sydney-best" : "fixture-exit"
        page.data = Object.assign({}, originalData, {exits: originalData.exits.map(peer =>
            peer.id === id ? Object.assign({}, peer, {address: ""}) : peer)})
        networkKeys.wait(30)
        if (row.contentItem.color.toString() === Theme.Palette.foreground.toString()
                || contrast(row.contentItem.color, menu.background.color) < 3)
            throw new Error(label + ": disabled label is indistinguishable/unreadable: " + row.contentItem.color + " / " + menu.background.color)
        captureMenu(menu, label + "-disabled")
        if (row.enabled) throw new Error(label + ": unavailable entry stayed enabled")
        page.data = originalData
    }
    function checkMenuRendering(menu, page) {
        const country = menu.menuAt(4)
        const selected = menu.itemAt(0)
        if (!selected.checked) throw new Error("None lost its initial checkmark")
        for (const [name, palette] of [["dark", darkPalette], ["light", lightPalette]]) {
            // Use the real palette-file refresh path while the root popup stays open.
            Theme.Palette.file.setText(palette.text())
            if (!Theme.Palette.refresh()) throw new Error("Fixture palette refresh failed")
            networkKeys.wait(220)
            checkMenuStates(menu, page, name + "-root")
            const separator = menu.itemAt(3).contentItem
            const separatorImage = captureMenu(menu, name + "-separator")
            const point = separator.mapToItem(menu.contentItem.parent, 5, 0)
            const separatorContrast = Math.max(...[0, 1].map(offset => contrast(
                separatorImage.pixel(Math.round(point.x), Math.floor(point.y) + offset), menu.background.color)))
            if (separatorContrast < 1.5) throw new Error(name + ": separator disappeared")
            const arrow = menu.itemAt(4).arrow
            if (!arrow.visible || contrast(arrow.color, menu.background.color) < 4.5)
                throw new Error(name + ": country arrow is unreadable")
            const mark = descendants(selected.indicator, item => item.source !== undefined && item.visible)[0]
            if (!mark || contrast(mark.color, selected.indicator.color) < 3)
                throw new Error(name + ": None checkmark is unreadable")
            menu.currentIndex = 4
            const countryEntry = menu.itemAt(4)
            countryEntry.forceActiveFocus()
            networkKeys.mouseMove(countryEntry, countryEntry.width / 2, countryEntry.height / 2)
            networkKeys.wait(40)
            if (!countryEntry.hovered || !countryEntry.highlighted
                    || contrast(countryEntry.contentItem.color, countryEntry.background.color) < 4.5
                    || contrast(arrow.color, countryEntry.background.color) < 4.5)
                throw new Error(name + ": highlighted country label/arrow is unreadable")
            captureMenu(menu, name + "-country-hover")
            networkKeys.keyClick(Qt.Key_Right)
            networkKeys.tryCompare(country, "visible", true)
            checkMenuStates(country, page, name + "-cities")
            // Refresh again with both popups open: inherited colours must stay live.
            Theme.Palette.file.setText((name === "light" ? darkPalette : lightPalette).text())
            if (!Theme.Palette.refresh()) throw new Error("Open submenu refresh failed")
            networkKeys.wait(220)
            country.currentIndex = -1; menu.currentIndex = -1
            if (!menu.visible || !country.visible) throw new Error("Theme refresh closed an open menu")
            checkMenuSurface(menu, name + "-root-live")
            checkMenuSurface(country, name + "-cities-live")
            country.close()
            menu.currentIndex = -1
            const originalData = page.data
            page.data = Object.assign({}, originalData, {connected: false})
            networkKeys.wait(30)
            if (country.enabled || contrast(countryEntry.contentItem.color, menu.background.color) < 3
                    || countryEntry.contentItem.color.toString() === Theme.Palette.foreground.toString()
                    || contrast(arrow.color, menu.background.color) < 3)
                throw new Error(name + ": disabled country label/arrow is unreadable")
            captureMenu(menu, name + "-country-disabled")
            page.data = originalData
        }
        Theme.Palette.file.setText(darkPalette.text())
        if (!Theme.Palette.refresh()) throw new Error("Fixture palette restore failed")
        networkKeys.wait(220)
        menu.currentIndex = 0
        menu.itemAt(0).forceActiveFocus()
    }
    Timer {
        interval: 300; running: true
        onTriggered: {
            try {
                networkPages.requestActivate()
                networkKeys.tryCompare(networkPages, "active", true)
                const picker = descendants(page, item => item.Accessible?.name === "Exit node")[0]
                networkKeys.tryCompare(picker, "enabled", true)
                picker.forceActiveFocus()
                networkKeys.keyClick(Qt.Key_Space)
                const menu = Array.from(picker.data).find(child => child.title !== undefined && child.count !== undefined)
                networkKeys.tryCompare(menu, "visible", true)
                networkKeys.tryCompare(menu, "count", 6)
                root.checkMenuRendering(menu, page)
                menu.currentIndex = 4
                networkKeys.keyClick(Qt.Key_Right)
                const country = menu.menuAt(4)
                networkKeys.tryCompare(country, "visible", true)
                country.currentIndex = 1
                networkKeys.keyClick(Qt.Key_Return)
                networkKeys.tryCompare(menu, "visible", false)
                networkKeys.tryCompare(page, "confirming", "")
                networkKeys.tryCompare(picker, "enabled", true)
                if (page.data.selected !== "fixture-sydney-best") throw new Error("City selection was not confirmed")
                picker.forceActiveFocus()
                networkKeys.keyClick(Qt.Key_Space)
                networkKeys.tryCompare(menu, "visible", true)
                const checkedCountry = menu.menuAt(4)
                menu.currentIndex = 4
                networkKeys.keyClick(Qt.Key_Right)
                networkKeys.tryCompare(checkedCountry, "visible", true)
                for (const [name, palette] of [["dark", darkPalette], ["light", lightPalette]]) {
                    Theme.Palette.file.setText(palette.text())
                    if (!Theme.Palette.refresh()) throw new Error("Checked city theme refresh failed")
                    networkKeys.wait(220)
                    const city = checkedCountry.itemAt(1)
                    const mark = descendants(city.indicator, item => item.source !== undefined && item.visible)[0]
                    if (!city.checked || !mark || contrast(mark.color, city.indicator.color) < 3)
                        throw new Error(name + ": selected city checkmark is unreadable")
                    captureMenu(checkedCountry, name + "-checked-city")
                }
                Theme.Palette.file.setText(darkPalette.text())
                if (!Theme.Palette.refresh()) throw new Error("Checked city theme restore failed")
                checkedCountry.close()
                menu.close()
                networkKeys.wait(220)
                const touch = networkKeys.touchEvent(picker)
                touch.press(0, picker).commit()
                touch.release(0, picker).commit()
                networkKeys.tryCompare(menu, "visible", true)
                menu.close()
                console.log("MENU_RENDER_CHECK_PASSED")
                Qt.quit()
            } catch (error) { console.error(error + "\\n" + error.stack); Qt.exit(1) }
        }
    }
}
"""

# Compare real stack pixels against an independent native single-caster reference.
SHADOW_QML = """import QtQuick
import QtQuick.Window
import QtQuick.Effects
import QtTest
import Quickshell
import "icewine/modules/topbar" as Bar
ShellRoot {
    Window {
        id: window
        visible: true
        width: 800; height: 280
        color: "white"
        Bar.Widget {
            id: widget
            width: 320; height: 240
            Bar.CardStack {
                id: stack
                shadowHost: widget.cardShadowHost
                width: 320; height: 240
                cards: [front, rear]
                Bar.Card { id: front; stack: stack; color: "white" }
                Bar.Card { id: rear; index: 1; stack: stack; color: "white" }
                Bar.Card { id: third; index: 2; stack: stack; color: "white"; visible: stack.cards.length === 3 }
            }
        }
        Item {
            id: reference
            x: 400; width: stack.width; height: stack.height
            property int drop: 2
            property var caster: front
            Rectangle { anchors.fill: parent; color: "white" }
            Rectangle {
                id: shape
                x: reference.caster.x; y: reference.caster.y
                width: reference.caster.width; height: reference.caster.height
                radius: reference.caster.radius
                color: "white"
                visible: false
            }
            MultiEffect {
                source: shape
                anchors.fill: shape
                shadowEnabled: true
                shadowColor: "black"; shadowOpacity: 0.35
                shadowBlur: 0.6; blurMax: 16
                shadowVerticalOffset: reference.drop
            }
        }
        TestCase { id: keys; when: false }
        function comparePixel(caster, drop, x, y, label) {
            if (window.GraphicsInfo.api === GraphicsInfo.Software) return
            reference.caster = caster
            reference.drop = drop
            keys.wait(40)
            const actual = keys.grabImage(window.contentItem).pixel(x, y)
            const expected = keys.grabImage(reference).pixel(x, y)
            if (expected.r > 0.995) throw new Error("Reference shadow did not render: " + label)
            if (Math.abs(actual.r - expected.r) > 2 / 255)
                throw new Error(label + ": actual=" + actual + " expected=" + expected)
        }
        function descendants(item) {
            return Array.from(item.children).reduce((items, child) => items.concat([child], descendants(child)), [])
        }
        function checkProjections(expected) {
            const effects = descendants(window.contentItem).filter(item => item.casterRank !== undefined && item.visible)
            const drops = effects.map(item => item.shadowVerticalOffset).sort().join(",")
            if (drops !== expected) throw new Error("Receiver drops: " + drops + " expected " + expected)
            for (const effect of effects) {
                if (!effect.source || effect.width !== stack.width || effect.height !== stack.height
                        || !effect.shadowEnabled || !effect.source.clip)
                    throw new Error("Projection lost common stack coordinates")
                if (effect.maskEnabled === effect.autoPaddingEnabled
                        || (effect.maskEnabled && !effect.maskSource.layer.enabled))
                    throw new Error("Card receiver lost its surface mask")
            }
        }
        function checkPair(label) {
            checkProjections("2,2,4")
            const top = stack.cards.find(card => card.z === 2)
            const lower = stack.cards.find(card => card !== top)
            comparePixel(top, 2, 160, top.y - 2, label + " onto card")
            comparePixel(top, 4, 160, top.y + top.height + 2, label + " onto windows")
            comparePixel(lower, 2, 160, lower.y - 2, label + " lower onto windows")
            const image = keys.grabImage(window.contentItem)
            if (image.pixel(160, top.y + 20).r !== 1 || image.pixel(360, 120).r !== 1)
                throw new Error("Shadow occlusion or constrained clip regressed")
            const directory = Quickshell.env("ICEWINE_CONTROL_CAPTURES")
            if (directory) image.save(directory + "/shadow-" + label + ".png")
        }
        Timer {
            interval: 250; running: true
            onTriggered: {
                try {
                    window.checkPair("pair")
                    widget.shadowDrop = 6
                    stack.shadowDrop = Qt.binding(() => widget.shadowDrop)
                    window.checkProjections("3,3,6")
                    widget.shadowDrop = 4
                    stack.selectCard(1)
                    keys.wait(40)
                    stack.selectCard(0)
                    keys.tryCompare(stack, "exchanging", false, 900)
                    window.checkPair("reversed")
                    stack.selectCard(1)
                    keys.tryCompare(stack, "exchanging", false, 900)
                    window.checkPair("selected")
                    stack.cards = [front, rear, third]
                    keys.wait(60)
                    window.checkProjections("1,1,2,2,3,4")
                    window.comparePixel(rear, 1, 160, rear.y - 2, "middle onto bottom")
                    window.comparePixel(front, 1, 160, front.y - 2, "top onto middle")
                    window.comparePixel(front, 4, 160, front.y + front.height + 2, "triple top onto windows")
                    window.comparePixel(third, 2, 160, third.y - 2, "bottom onto windows")
                    const directory = Quickshell.env("ICEWINE_CONTROL_CAPTURES")
                    if (directory) keys.grabImage(window.contentItem).save(directory + "/shadow-triple.png")
                    stack.selectCard(1)
                    keys.wait(30)
                    stack.selectCard(2)
                    keys.tryCompare(stack, "exchanging", false, 900)
                    window.checkProjections("1,1,2,2,3,4")
                    widget.animateClose = false
                    widget.shown = false
                    keys.wait(20)
                    window.checkProjections("")
                    widget.shown = true
                    keys.wait(200)
                    stack.visible = false
                    keys.wait(20)
                    window.checkProjections("")
                    stack.visible = true
                    stack.cards = [front]
                    third.visible = false
                    rear.visible = false
                    keys.wait(60)
                    if (front.x !== 0 || front.y !== 0 || front.width !== stack.width
                            || keys.grabImage(stack).pixel(160, 1).r !== 1)
                        throw new Error("Single-card appearance changed")
                    if (window.GraphicsInfo.api === GraphicsInfo.Software)
                        console.log("SHADOW_PIXELS_UNAVAILABLE: software scene graph does not render MultiEffect; native preview required")
                    console.log("SHADOW_CHECK_PASSED")
                    Qt.quit()
                } catch (error) { console.error(error + "\\n" + error.stack); Qt.exit(1) }
            }
        }
    }
}
"""

SERVICE_FIXTURES = {
    "UPower": "property var displayDevice: null",
    "UPowerDeviceState": "enum State { Charging, PendingCharge }",
    "Pipewire": """
        // Real Pipewire audio properties notify bindings; nested JS objects do not.
        property QtObject firstAudio: QtObject { property bool muted: false; property real volume: 0.5 }
        property QtObject secondAudio: QtObject { property bool muted: false; property real volume: 0.5 }
        property var nodes: ({values: Array.from({length: 2}, (_, id) => ({
            id: id, name: "Audio " + id, description: "Device " + id,
            isSink: true, isStream: false, audio: id === 0 ? firstAudio : secondAudio}))})
        property var defaultAudioSink: nodes.values[0]
        property var defaultAudioSource: null
        property var preferredDefaultAudioSink: null
        property var preferredDefaultAudioSource: null
    """,
    "Bluetooth": """
        id: bluetooth
        property var calls: []
        property QtObject testDevice: QtObject {
            property string name: "Fixture headphones"
            property string deviceName: name
            property string icon: "audio-headset"
            property bool paired: false
            property bool bonded: false
            property bool pairing: false
            property bool connected: false
            property int state: 0
            property bool batteryAvailable: false
            property real battery: 0.5
            function pair() { bluetooth.calls.push("pair"); pairing = true }
            function connect() { bluetooth.calls.push("connect") }
            function disconnect() { bluetooth.calls.push("disconnect") }
            function forget() { bluetooth.calls.push("forget") }
        }
        property QtObject fixtureAdapter: QtObject {
            property bool enabled: true
            property bool discovering: false
            property var devices: ({values: [bluetooth.testDevice]})
        }
        property var defaultAdapter: fixtureAdapter
    """,
    "BluetoothDeviceState": "enum State { Idle, Connecting, Disconnecting }",
    "Networking": """
        property bool wifiEnabled: true
        property bool wifiHardwareEnabled: true
        property var devices: ({values: [{type: DeviceType.Wifi, name: "fixture-wifi",
            scannerEnabled: false, networks: {values: Array.from({length: 12}, (_, id) => ({
                name: "Network " + id, connected: false, stateChanging: false,
                signalStrength: 0.5, security: WifiSecurityType.Open,
                connect: function() {}, disconnect: function() {} }))}}]})
    """,
    "DeviceType": "enum Type { Wifi, Wired }",
    "WifiSecurityType": "enum Security { Open, Unknown }",
    "ConnectionFailReason": "enum Reason { NoSecrets }",
}

source = Path(sys.argv[1]).resolve()
battery = (source / "quickshell/modules/topbar/popouts/Battery.qml").read_text()
assert battery.index('text: "Power"') < battery.index('id: lockButton')
assert battery.index('id: lockButton') < battery.index('id: keepAwake')
assert battery.index('id: keepAwake') < battery.index('visible: root.batteryPresent')
assert battery.index('id: keepAwake') < battery.index('text: "Battery condition"')
for action in ["Lock", "Sleep", "Reboot", "Shutdown"]:
    assert f'Accessible.name: "{action}"' in battery
    assert re.search(r'text: "[^"\n]*\s+' + re.escape(action) + '"', battery)
bluetooth = (source / "quickshell/modules/topbar/popouts/Bluetooth.qml").read_text()
assert re.search(r'ActionButton\s*\{\s*id: forget', bluetooth)
assert 'Accessible.name: "Forget "' in bluetooth and 'onClicked: deviceRow.forgotten()' in bluetooth
QML = QML.replace("ssh-ed25519 fixture-public", SSH_PUBLIC)

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "icewine").mkdir()
    # Exercise the real pages, substituting only service imports for synthetic devices.
    shutil.copytree(source / "quickshell/modules", root / "icewine/modules", copy_function=shutil.copyfile)
    for name, service in (("Audio", "Quickshell.Services.Pipewire"),
                          ("Bluetooth", "Quickshell.Bluetooth"),
                          ("Network", "Quickshell.Networking")):
        page = root / f"icewine/modules/topbar/popouts/{name}.qml"
        page_source = page.read_text()
        assert page_source.count(f"import {service}\n") == 1, "Expected exactly one fixture service import"
        page.write_text(page_source.replace(f"import {service}\n", "import ControlFixtures\n"))
    metrics = root / "icewine/modules/topbar/SystemMetrics.qml"
    metrics_source = metrics.read_text()
    discovery = "Process {\n        running: true"
    assert metrics_source.count(discovery) == 1, "Expected exactly one sensor discovery process"
    metrics.write_text(metrics_source.replace(discovery, "Process {\n        running: false"))
    fixtures = root / "ControlFixtures"
    fixtures.mkdir()
    (fixtures / "qmldir").write_text("module ControlFixtures\n" + "".join(
        f"singleton {name} 1.0 {name}.qml\n" for name in SERVICE_FIXTURES) +
        "PwObjectTracker 1.0 PwObjectTracker.qml\n")
    for name, qml in SERVICE_FIXTURES.items():
        (fixtures / f"{name}.qml").write_text("pragma Singleton\nimport QtQuick\nQtObject {\n" + qml + "\n}\n")
    (fixtures / "PwObjectTracker.qml").write_text("import QtQuick\nQtObject { property var objects: [] }\n")
    (root / "icewine/theme").symlink_to(root / "theme")
    for name in ("Desktop.qml", "Handheld.qml", "adapters", "deck"):
        (root / "icewine" / name).symlink_to(source / "quickshell" / name)
    fixture_config = theme_fixture(source, root)
    (root / "palette-dark.json").write_bytes((Path(fixture_config) / "icewine/current/palette.json").read_bytes())
    import runpy
    render_theme = runpy.run_path(str(source / "scripts/theme"))["render_theme"]
    assets = source / "theme/assets"
    (root / "palette-light.json").write_text(render_theme(assets, assets / "themes/catppuccin-latte.json")["palette.json"])
    shutil.copytree(source / "quickshell/config", root / "config")
    (root / "bin").mkdir()
    clipboard_command = root / "bin/icewine-clipboard"
    # A real 2:1 PNG plus decode failures exercise the native Qt image path.
    (root / "clipboard-image.png").write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAIAAAB7QOjdAAAAD0lEQVR4nGP4z8DA8J8BAAf/Af8Bf4mnAAAAAElFTkSuQmCC"))
    (root / "clipboard-broken.png").write_bytes(b"invalid PNG fixture")
    clipboard_command.write_text("#!" + sys.executable + "\n" + '''import json, sys
state = dict(entries=[dict(id="fixture:1", preview="<b>fixture</b>")], active="", selection=None, error="", request=0, loaded=False)
print(json.dumps(state), flush=True)
for line in sys.stdin:
    request = json.loads(line)
    state.update(request=request.get("request", 0), loaded=request["action"] == "load", active="fixture:1", selection=["text/plain;charset=utf-8", "a" * 64])
    print(json.dumps(state), flush=True)
''')
    clipboard_command.chmod(0o755)
    ssh_command = root / "bin/icewine-ssh"
    ssh_command.write_text("#!" + sys.executable + "\n" + '''import json, sys, time
request = json.load(sys.stdin)
if request["action"] == "generate": time.sleep(2)
message = ""
if request["action"] == "import" and "path" in request:
    assert request["path"] == "/synthetic/selected-key" and request["passphrase"] == "fixture secret" and request["expectedFingerprint"] == "SHA256:disk", "Selected path mismatch"
    message = "Selected file import received"
if request["action"] == "import" and "private" in request:
    assert request["private"] == "synthetic private key\\nsecond line", "Pasted transport mismatch"
    assert request["passphrase"] == "fixture secret" and not request.get("path") and not request.get("expectedFingerprint"), "Pasted request mismatch"
    message = "Pasted import received"
print(json.dumps(dict(available=True, error="", entries=[dict(public="ssh-ed25519 fixture-public",
    paths=[], loaded=True, temporary=True, origin="Generated temporarily", type="ssh-ed25519",
    fingerprint="SHA256:fixture")], message=message)))
'''.replace("ssh-ed25519 fixture-public", SSH_PUBLIC))
    ssh_command.chmod(0o755)
    copy_public = root / "bin/wl-copy"
    copy_public.write_text("#!" + sys.executable + "\nimport sys\nassert sys.argv[1:] == ['--type', 'text/plain']\nassert sys.stdin.read() == 'ssh-ed25519 fixture-public'\n".replace("ssh-ed25519 fixture-public", SSH_PUBLIC))
    copy_public.chmod(0o755)
    mock = root / "bin/icewine-monitor-brightness"
    mock.write_text("#!" + shutil.which("bash") + '\nprintf "%s\\n" "$1" >> "' + str(root / "brightness-calls") + '"\necho "${2:-37}"\n')
    mock.chmod(0o755)
    notify = root / "bin/notify-send"
    notify.write_text("#!" + shutil.which("bash") + '\nprintf "%s\\n" "$*" >> "' + str(root / "notifications") + '"\n')
    notify.chmod(0o755)
    shortcuts = root / "bin/icewine-steam-shortcuts"
    shortcuts.write_text("#!" + shutil.which("bash") + '\nif [ -e "' + str(root / "shortcuts-read")
                         + '" ]; then exit 1; fi\ntouch "' + str(root / "shortcuts-read")
                         + '"\necho \'[["demo"]]\'\n')
    shortcuts.chmod(0o755)
    uwsm = root / "bin/uwsm"
    uwsm.write_text("#!" + shutil.which("bash") + "\nexit 0\n")
    uwsm.chmod(0o755)
    service = root / "bin/systemctl"
    service.write_text("#!" + shutil.which("bash") + '\nprintf "LoadState=not-found\\nMainPID=0\\n"\n')
    service.chmod(0o755)
    capabilities = root / "bin/icewine-monitor-capabilities"
    capabilities.write_text("#!" + shutil.which("bash") + '\nexit 0\n')
    capabilities.chmod(0o755)
    tailscale = root / "bin/tailscale"
    tailscale.write_text("#!" + shutil.which("python3") + "\n" +
        "import json, pathlib, sys, time\n" +
        "state = pathlib.Path(" + repr(str(root / "exit-node")) + ")\n" +
        "backend = pathlib.Path(" + repr(str(root / "backend-state")) + ")\n" +
        "profile = pathlib.Path(" + repr(str(root / "tailscale-profile")) + ")\n" +
        "mode_file = pathlib.Path(" + repr(str(root / "tailscale-mode")) + ")\n" +
        "mode = mode_file.read_text() if mode_file.exists() else ''\n" +
        "log = pathlib.Path(" + repr(str(root / "tailscale-calls")) + ")\n" +
        "with log.open('a') as f: f.write(json.dumps(sys.argv[1:]) + '\\n')\n" +
        "if sys.argv[1:] == ['status', '--json']:\n" +
        " if mode == 'status-slow': time.sleep(0.3)\n" +
        " selection = state.read_text() if state.exists() else ''\n" +
        " selected = selection not in ('', 'cleared')\n" +
        " print(json.dumps({'BackendState': backend.read_text() if backend.exists() else 'Running', 'Self': {'ID': profile.read_text() if profile.exists() else 'fixture-local', 'HostName': '<b>Fixture laptop</b>', 'Online': selection not in ('offline', 'cleared')}, " +
        "'Peer': {'demo': {'ID': 'fixture-exit', 'HostName': 'Home gateway', 'TailscaleIPs': ['100.64.0.2'], 'Online': True, 'ExitNodeOption': True}, " +
        "'local': {'ID': profile.read_text() if profile.exists() else 'fixture-local', 'HostName': 'Local duplicate', 'TailscaleIPs': ['100.64.0.4'], 'Online': True}, " +
        "'equal': {'ID': 'fixture-equal', 'HostName': '<b>Fixture laptop</b>', 'TailscaleIPs': ['100.64.0.3'], 'Online': True}, " +
        "'alt': {'ID': 'fixture-alt', 'HostName': 'Remote gateway', 'TailscaleIPs': ['100.64.0.5'], 'Online': True, 'ExitNodeOption': True}, " +
        "'sydney': {'ID': 'fixture-sydney', 'DNSName': 'sydney.mullvad.ts.net.', 'TailscaleIPs': ['100.64.0.6'], 'Online': True, 'ExitNodeOption': True, 'Location': {'Country': 'Australia', 'City': 'Sydney', 'Priority': 1}}, " +
        "'best': {'ID': 'fixture-sydney-best', 'DNSName': 'best.mullvad.ts.net.', 'TailscaleIPs': ['100.64.0.7'], 'Online': True, 'ExitNodeOption': True, 'Location': {'Country': 'Australia', 'City': 'Sydney', 'Priority': 2}}, " +
        "'mel': {'ID': 'fixture-melbourne', 'DNSName': 'mel.mullvad.ts.net.', 'TailscaleIPs': ['100.64.0.8'], 'Online': True, 'ExitNodeOption': True, 'Location': {'Country': 'Australia', 'City': 'Melbourne'}}, " +
        "'de': {'ID': 'fixture-berlin', 'DNSName': 'berlin.mullvad.ts.net.', 'TailscaleIPs': ['100.64.0.9'], 'Online': True, 'ExitNodeOption': True, 'Location': {'Country': 'Germany', 'City': 'Berlin'}}}, " +
        "'ExitNodeStatus': {'ID': 'fixture-sydney-best' if selection == 'city' else 'fixture-exit', 'Online': True} if selected else None}))\n" +
        "elif sys.argv[1:] == ['up']: time.sleep(0.1); backend.write_text('Running')\n" +
        "elif sys.argv[1:] == ['down']:\n" +
        " if mode == 'success':\n" +
        "  while not (mode_file.parent / 'tailscale-release').exists(): time.sleep(0.01)\n" +
        " else: time.sleep(1 if mode else 0.1)\n" +
        " if mode == 'failure': print('request failed', file=sys.stderr); sys.exit(1)\n" +
        " backend.write_text('Stopped')\n" +
        " if mode == 'profile': profile.write_text('fixture-other')\n" +
        "elif sys.argv[1:] == ['set', '--exit-node=100.64.0.7']: state.write_text('city')\n" +
        "elif sys.argv[1:] == ['set', '--exit-node=100.64.0.2']: state.write_text('offline')\n" +
        "elif sys.argv[1:] == ['set', '--exit-node=']: state.write_text('cleared')\n" +
        "else: sys.exit(1)\n")
    tailscale.chmod(0o755)
    (root / "shell.qml").write_text(QML)
    (root / "network.txt").write_text("eth0: 100 0 0 0 0 0 0 0 50 0 0 0 0 0 0 0\n")
    (root / "cpu.txt").write_text("cpu 100 0 0 400 0 0 0 0\n")
    (root / "memory.txt").write_text("MemTotal: 1000 kB\nMemAvailable: 600 kB\n")
    # Ponytail: inherited feature flags stay until a real fixture failure warrants explicit inputs; then pin only the tested flags.
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QML_IMPORT_PATH=str(root),
               HYPRLAND_INSTANCE_SIGNATURE="", WAYLAND_DISPLAY="",
               ICEWINE_BATTERY_ENABLED="true",
               DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(root / "no-session-bus"),
               DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(root / "no-system-bus"),
               XDG_CACHE_HOME=str(root / "cache"), XDG_RUNTIME_DIR=str(root / "runtime"),
               XDG_STATE_HOME=str(root / "state"), ICEWINE_WIDGET_POLICY="{}",
               PATH=str(root / "bin") + os.pathsep + os.environ["PATH"])
    env["XDG_CONFIG_HOME"] = fixture_config
    if "--clipboard-only" in sys.argv:
        (root / "state").mkdir()
        assert not (root / "state/icewine").exists(), "First-use fixture must lack the preference directory"
    else:
        (root / "state/icewine").mkdir(parents=True)
    if "--ssh-only" in sys.argv:
        (root / "shell.qml").write_text(QML.replace("property bool sshOnly: false", "property bool sshOnly: true"))
        result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                                capture_output=True, text=True, timeout=20)
        output = result.stdout + result.stderr
        assert result.returncode == 0 and "SSH_UI_CHECK_PASSED" in output, output
        assert not re.search(r"ReferenceError|TypeError|[Bb]inding loop|Unable to assign", output), output
        print("three-card SSH keyboard entry, concealed input, cancel/dismiss/reopen/page lifecycle pass")
        sys.exit(0)
    if "--clipboard-only" in sys.argv:
        (root / "shell.qml").write_text(QML.replace("property bool clipboardOnly: false",
                                                   "property bool clipboardOnly: true"))
        result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                                capture_output=True, text=True, timeout=15)
        output = result.stdout + result.stderr
        assert result.returncode == 0 and "CLIPBOARD_CHECK_PASSED" in output, output
        assert not re.search(r"ReferenceError|TypeError|[Bb]inding loop|Unable to assign", output), output
        import json
        assert json.loads((root / "state/icewine/clipboard.json").read_text()) == {"expirySeconds": 1800}
        # A fresh shell must load the saved duration without opening a card.
        (root / "shell.qml").write_text("""import QtQuick
import Quickshell
import qs.config as Config
ShellRoot {
    Timer { interval: 100; running: true; repeat: true
        onTriggered: if (Config.Settings.clipboardExpiry === 1800) {
            console.log("CLIPBOARD_PREFERENCE_RESTART_PASSED"); Qt.quit()
        }
    }
}
""")
        restarted = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                                   capture_output=True, text=True, timeout=10)
        assert restarted.returncode == 0 and "CLIPBOARD_PREFERENCE_RESTART_PASSED" in restarted.stdout + restarted.stderr
        print("notification/clipboard stack, row actions, image previews, scrolling and adapter checks pass")
        sys.exit(0)
    (root / "shell.qml").write_text(STACKS_QML)
    result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                            capture_output=True, text=True, timeout=20)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and "STACKS_CHECK_PASSED" in output, output
    assert not re.search(r"ReferenceError|TypeError|[Bb]inding loop|Unable to assign|unresolvable import", output), output
    if "--stacks-only" in sys.argv:
        print("shared stacks: all modules alone, mixed four-card order/navigation, live accent wrap, stable identity and last-good preferences pass")
        sys.exit(0)
    status_icons = root / "icewine/modules/topbar/StatusIcons.qml"
    native_status_icons = status_icons.read_text()
    status_icons.write_text(native_status_icons.replace("import Quickshell.Services.Pipewire\n", "import ControlFixtures\n")
                            .replace("import Quickshell.Services.UPower\n", ""))
    (root / "shell.qml").write_text(STATUS_ICONS_QML)
    result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                            capture_output=True, text=True, timeout=15)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and "STATUS_ICONS_CHECK_PASSED" in output, output
    assert not re.search(r"ReferenceError|TypeError|[Bb]inding loop|Unable to assign|unresolvable import|not a type", output), output
    status_icons.write_text(native_status_icons)
    (root / "shell.qml").write_text('''import QtQuick
import Quickshell
import "icewine/modules/topbar" as Bar
ShellRoot {
    Bar.StatusIcons { notificationService: ({count: 0, highestUrgency: 0, doNotDisturb: false, pulseToken: 0}) }
    Timer { interval: 100; running: true; onTriggered: { console.log("STATUS_IMPORT_CHECK_PASSED"); Qt.quit() } }
}
''')
    result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                            capture_output=True, text=True, timeout=15)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and "STATUS_IMPORT_CHECK_PASSED" in output, output
    assert not re.search(r"ReferenceError|TypeError|[Bb]inding loop|Unable to assign|unresolvable import|not a type", output), output
    if "--status-icons-only" in sys.argv:
        print("status icon composition, batteryless access, hover, taps and volume scrolling pass")
        sys.exit(0)
    (root / "shell.qml").write_text(SHADOW_QML)
    result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                            capture_output=True, text=True, timeout=15)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and "SHADOW_CHECK_PASSED" in output, output
    assert not re.search(r"ReferenceError|TypeError|[Bb]inding loop|Unable to assign|Cannot stack", output), output
    for line in output.splitlines():
        if "SHADOW_PIXELS_UNAVAILABLE" in line:
            print(line)
    if "--shadows-only" in sys.argv:
        print("receiver-relative shadow scene checks pass; pixel checks run only on an effect-capable scene graph")
        sys.exit(0)
    (root / "shell.qml").write_text(ARROW_QML)
    result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                            capture_output=True, text=True, timeout=25)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and "ARROW_CHECK_PASSED" in output, output
    assert not re.search(r"ReferenceError|TypeError|[Bb]inding loop|Unable to assign", output), output
    if "--arrows-only" in sys.argv:
        print("native control ownership and stack keyboard checks pass")
        sys.exit(0)
    (root / "shell.qml").write_text(MENU_QML)
    # The offscreen platform has no desktop hover capability unless supplied explicitly.
    result = subprocess.run(["qs", "-p", str(root), "--no-color"],
                            env=dict(env, QT_QUICK_CONTROLS_HOVER_ENABLED="1"),
                            capture_output=True, text=True, timeout=15)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and "MENU_RENDER_CHECK_PASSED" in output, output
    assert not re.search(r"ReferenceError|TypeError|[Bb]inding loop|Unable to assign", output), output
    # The rendering fixture confirms a city using the fake CLI; reset it for lifecycle checks.
    for name in ("exit-node", "tailscale-calls"):
        (root / name).unlink(missing_ok=True)
    (root / "shell.qml").write_text(QML)
    try:
        result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                                capture_output=True, text=True, timeout=50)
    except subprocess.TimeoutExpired as error:
        raise AssertionError((error.stdout or b"").decode() + (error.stderr or b"").decode()) from error
    output = result.stdout + result.stderr
    for line in output.splitlines():
        if "TAILSCALE_REFRESH" in line:
            print(line)
    assert result.returncode == 0 and "CONTROL_CHECK_PASSED" in output, output
    assert not re.search(r"ReferenceError|TypeError|[Bb]inding loop|Unable to assign", output), output
    assert "performance-only" not in (root / "brightness-calls").read_text().splitlines(), "Performance entry started brightness polling"
    import json
    calls = [json.loads(line) for line in (root / "tailscale-calls").read_text().splitlines()]
    assert [call for call in calls if call[0] == "set"] == [
        ["set", "--exit-node=100.64.0.7"], ["set", "--exit-node=100.64.0.2"], ["set", "--exit-node="]], calls
    assert [call for call in calls if call[0] in ("up", "down")] == [["down"], ["up"]] * 4 + [["down"], ["down"]], calls
    notifications = (root / "notifications").read_text().splitlines()
    assert len(notifications) == 4, notifications
    assert any("-u normal Battery Low 20%" in call for call in notifications), notifications
    assert any("-u critical Battery Critical 10%" in call for call in notifications), notifications
    assert any("-u critical Battery Danger 5%" in call for call in notifications), notifications
    # Restore native service imports for the existing packaged-entry resolution check.
    for name in ("Audio", "Bluetooth", "Network"):
        relative = f"quickshell/modules/topbar/popouts/{name}.qml"
        (root / "icewine/modules/topbar/popouts" / f"{name}.qml").write_bytes((source / relative).read_bytes())
    # Native panels require a Wayland backend. Resolve the actual writable entry
    # imports as far as that boundary without starting a compositor/session.
    for entry in (source / "quickshell/shell.qml", source / "quickshell/deck/shell.qml"):
        (root / "shell.qml").write_bytes(entry.read_bytes())
        result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                                capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        assert result.returncode != 0 and "No PanelWindow backend loaded." in output, output
        assert not re.search(r"unresolvable import|not a type|No such file", output), output
    print("control lifecycle and packaged entry imports pass; native panels require session validation")
