#!/usr/bin/env python3
"""Check controls, live metric sampling and performance layout updates.
Run with python3 tests/controls.py . (requires qs on PATH).
"""
import os
from pathlib import Path
from qml_fixture import theme_fixture
import re
import shutil
import subprocess
import sys
import tempfile

QML = """import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import Quickshell.Services.UPower
import Quickshell.Io
import ControlFixtures as Fixtures
import "icewine/deck" as Deck
import "icewine/modules" as Modules
import "icewine/modules/topbar" as Bar
import "icewine/modules/topbar/popouts" as Popouts
import "icewine/theme" as Theme
ShellRoot {
    id: root
    Component { id: handheldOverlay; Deck.DeckOverlay { compositor: compositor; sessionLocked: false; shell: root } }
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
            monitorName: "DP-1"
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
    function checkPopoutFocus() {
        focusWindow.requestActivate()
        toggleKeys.tryCompare(focusWindow, "active", true)
        focusPopout.currentPage = "media"
        toggleKeys.wait(30)
        focusPopout.focusInitial()
        toggleKeys.wait(20)
        const play = root.findAccessible(focusPopout, "Play")
        assertRevealed(play, "Media initial")
        const surface = focusPopout.currentItem.parent.parent
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

        focusWindow.height = 40
        focusPopout.currentPage = "audio"
        toggleKeys.wait(30)
        const audio = descendants(focusPopout, item => item instanceof Flickable)[0]
        const rows = descendants(audio, item => item.label !== undefined && item.activeFocusOnTab)
        rows[0].forceActiveFocus()
        toggleKeys.wait(10)
        assertRevealed(rows[0], "Audio first")
        for (const [key, index] of [[Qt.Key_Down, 1], [Qt.Key_Backtab, 0],
                [Qt.Key_Tab, 1], [Qt.Key_Up, 0]]) {
            const before = audio.contentY
            toggleKeys.keyClick(key)
            toggleKeys.wait(10)
            assertRevealed(rows[index], "Audio boundary " + key)
            if (index === 1 ? audio.contentY <= before : audio.contentY >= before)
                throw new Error("Audio did not cross the scroll boundary in the expected direction")
        }

        focusWindow.height = 150
        root.items = Array.from({length: 3}, (_, index) => ({
            summary: "Notification " + index, appName: "Fixture", appIcon: "", body: "",
            urgency: 1, actions: [], dismiss: function() {} }))
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
    function selectCardTarget(target) { target.parent.stack.selectCard(target.parent.index) }
    function checkNetworkCards(selected, other, page) {
        const front = selected.parent
        const rear = other.parent
        const body = descendants(front, item => item instanceof Flickable)[0]
        if (front.x - rear.x !== 18 || front.y - rear.y !== 48 || front.z <= rear.z
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
                || !front.children.find(item => item.z === 101)?.visible || !body.enabled
                || front.border.width !== 0 || rear.border.width !== 0
                || descendants(rear, item => item instanceof Flickable)[0].enabled)
            throw new Error("Card input, selection or focus ownership is incorrect")
        if (body.height <= 0 || !body.clip)
            throw new Error("Card must retain its constrained scroll viewport")
    }
    function settleCards(page) {
        networkKeys.tryCompare(page, "exchanging", false, 900)
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
        for (let i = 0; i < 30 && !second.activeFocus; ++i) networkKeys.keyClick(Qt.Key_Tab)
        if (!second.activeFocus) throw new Error("Rear card is missing from keyboard focus traversal")
        // Mere hover, keyboard focus and arrow navigation must not select a card.
        networkKeys.mouseMove(second, 40, 20)
        second.forceActiveFocus()
        networkKeys.keyClick(Qt.Key_Right)
        networkKeys.wait(30)
        if (page.selectedCard !== 0 || page.exchanging)
            throw new Error("Hover/focus/arrow selected the alternate card")
        // Real click and early reversal, with both bodies inert and focus stationary.
        networkKeys.mouseClick(second, 40, 20)
        networkKeys.wait(150)
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
            const outline = page.children.find(item => item.z === 3 && item.height === 3)
            if (focus !== stationary || page.initialFocus !== stationary || !focus.activeFocus
                    || !focus.visible || !focus.enabled || !outline?.visible
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
        networkKeys.wait(190)
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
        networkKeys.wait(420)
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
        networkKeys.wait(100)
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
        networkKeys.wait(100)
        networkPages.shown = false
        if (page.exchanging || page.wifiDevice.scannerEnabled || tailscale.active)
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
                        if (descendants(first.parent, item => item.text === "Networking")[0].color.toString() !== Theme.Palette.success.toString()
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
            const title = root.findAccessible(page, "<b>Fixture laptop</b> · Connected")
            const titleEnd = title.mapToItem(page, title.width, 0).x
            const switchStart = connection.mapToItem(page, 0, 0).x
            if (titleEnd > switchStart || switchStart + connection.width > page.width
                    || connection.width < 44 || connection.height < 44)
                throw new Error("Status and connection touch target overlap or overflow")
        }
        networkWindow.width = 280
        for (const input of [Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter, "mouse", "touch", "touch"]) {
            connection.forceActiveFocus()
            networkKeys.wait(30) // Let the actual popout reveal the target before pointer/touch delivery.
            const wasChecked = connection.checked
            if (typeof input === "number") networkKeys.keyClick(input)
            else if (input === "mouse") networkKeys.mouseClick(connection, connection.width - 17, connection.height / 2)
            else {
                const touch = networkKeys.touchEvent(networkWindow)
                touch.press(0, connection, connection.width - 17, connection.height / 2).commit()
                touch.release(0, connection, connection.width - 17, connection.height / 2).commit()
            }
            networkKeys.tryCompare(page, "busy", true)
            if (connection.checked !== wasChecked || connection.enabled || picker.enabled)
                throw new Error("Connection must retain confirmed state and serialize input while busy")
            page.toggleConnection()
            page.selectExit("")
            networkKeys.tryCompare(page, "busy", false)
            networkKeys.tryCompare(page, "confirming", "")
            networkKeys.tryCompare(connection, "enabled", true)
            if (connection.checked === wasChecked || connection.Accessible.checked !== connection.checked || page.error)
                throw new Error("Connection input did not confirm a state change: " + input + " / " + page.error)
            if (connection.checked && (page.data.selected !== "fixture-sydney-best"
                    || picker.text !== "Australia · Sydney"))
                throw new Error("Reconnection lost the saved exit-node preference")
        }
    }
    FileView { id: tailscaleRelease; path: Qt.resolvedUrl("tailscale-release") }
    FileView { id: tailscaleMode; path: Qt.resolvedUrl("tailscale-mode") }
    function checkTailscaleLifetime() {
        const connection = root.findAccessible(networkPages, "Tailscale connection")
        const picker = root.findAccessible(networkPages, "Exit node")
        const page = picker.parent.parent.parent
        tailscaleMode.setText("success")
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
        let networkPage = networking
        while (networkPage && networkPage.wifiDevice === undefined) networkPage = networkPage.parent
        if (!networkPage.wifiDevice.scannerEnabled || page.active)
            throw new Error("Retained Network did not restore ordinary tab activity")
        networkPages.shown = false
        networkKeys.tryCompare(networkPages, "visible", false)
        if (networkPage.wifiDevice.scannerEnabled || page.active)
            throw new Error(`Retained Network left background scanning/polling active while hidden: networkVisible=${networkPage.visible}, scanning=${networkPage.wifiDevice.scannerEnabled}, tailscaleActive=${page.active}`)
        networkPages.shown = true
        networkKeys.wait(30)
        if (!networkPage.wifiDevice.scannerEnabled || page.active)
            throw new Error("Retained Network did not resume scanning on reopening its Networking tab")
    }
    function checkRetainedNetworkFocus() {
        networkWindow.requestActivate()
        networkKeys.tryCompare(networkWindow, "active", true)
        networkPages.currentPage = "network"
        const networking = root.findAccessible(networkPages, "Networking card")
        let page = networking
        while (page && page.wifiDevice === undefined) page = page.parent
        const password = descendants(page,
            item => item instanceof TextInput && item.echoMode === TextInput.Password)[0]
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
            // Sample within the rate model's three-second window, before deliberate motion waits.
            root.tick()
            networkWindow.requestActivate()
            networkKeys.tryCompare(networkWindow, "active", true)
            const firstTab = root.findAccessible(networkPages, "Networking card")
            const secondTab = root.findAccessible(networkPages, "Tailscale card")
            networkPages.focusInitial()
            if (!firstTab.activeFocus || !firstTab.checked || secondTab.checked)
                throw new Error("Network initial tab/focus is incorrect")
            let networkPage = firstTab
            while (networkPage && networkPage.wifiDevice === undefined) networkPage = networkPage.parent
            const password = descendants(networkPage,
                item => item instanceof TextInput && item.echoMode === TextInput.Password)[0]
            networkPage.passwordNetwork = {name: "Fixture Wi-Fi"}
            password.text = "fixture secret"
            networkPages.focusInitial()
            if (!password.activeFocus) throw new Error("Host initial focus lost password precedence")
            const tabCentre = firstTab.mapToItem(networkPage, firstTab.width / 2, firstTab.height / 2)
            if (networkPage.childAt(tabCentre.x, tabCentre.y) !== password.parent.parent.parent)
                throw new Error("Password overlay must remain above both cards")
            selectCardTarget(firstTab)
            selectCardTarget(secondTab)
            if (networkPage.selectedCard !== 0 || networkPage.exchanging
                    || firstTab.enabled || secondTab.enabled || networkPage.wifiDevice.scannerEnabled)
                throw new Error("Password overlay did not suppress card input/scanning")
            networkPage.closePassword()
            if (password.text || networkPage.passwordNetwork)
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
            networkPage.errorMessage = "Retained fixture error"
            secondTab.forceActiveFocus()
            networkKeys.keyClick(Qt.Key_Enter)
            root.settleCards(networkPage)
            if (!secondTab.checked || !secondTab.activeFocus)
                throw new Error("Enter did not select/focus Tailscale card")
            networkKeys.wait(20)
            root.checkNetworkCards(secondTab, firstTab, networkPage)
            if (!networkPage || networkPage.wifiDevice.scannerEnabled)
                throw new Error("Tailscale tab left synthetic Wi-Fi scanning active")
            const picker = root.findAccessible(networkPages, "Exit node")
            networkKeys.tryCompare(picker, "enabled", true)
            const page = picker.parent.parent.parent
            networkKeys.tryVerify(() => page.data.peers.length === 2)
            const localLabel = root.findAccessible(page, "<b>Fixture laptop</b> · Connected")
            if (!localLabel || localLabel.textFormat !== Text.PlainText)
                throw new Error("Local device name must appear as plain text in the status title")
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
            networkKeys.tryCompare(page, "confirming", "")
            if (page.data.selected !== "fixture-sydney-best" || picker.text !== "Australia · Sydney")
                throw new Error("City selection did not confirm its highest-priority exit node")
            picker.forceActiveFocus()
            networkKeys.keyClick(Qt.Key_Space)
            networkKeys.tryCompare(menu, "visible", true)
            menu.currentIndex = 0
            networkKeys.keyClick(Qt.Key_Down)
            networkKeys.keyClick(Qt.Key_Return)
            networkKeys.tryCompare(menu, "visible", false)
            networkKeys.tryCompare(picker, "enabled", true)
            networkKeys.tryCompare(page, "confirming", "")
            if (page.data.connected || page.data.selected !== "fixture-exit")
                throw new Error("Expected confirmed Running/offline selected-node fixture")
            picker.forceActiveFocus()
            networkKeys.keyClick(Qt.Key_Tab)
            networkKeys.wait(20)
            const focused = networkWindow.activeFocusItem
            if (focused.text !== "Refresh Tailscale")
                throw new Error("Tailscale refresh did not receive keyboard focus")
            let scroll = focused.parent
            while (scroll && !(scroll instanceof Flickable)) scroll = scroll.parent
            const top = focused.mapToItem(scroll, 0, 0).y
            if (top < -1 || top + focused.height > scroll.height + 1)
                throw new Error("Current StatusPopout did not reveal the focused Tailscale control")
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
            if (!firstTab.checked || !firstTab.activeFocus || picker.enabled || !networkPage.wifiDevice.scannerEnabled)
                throw new Error(`Space did not restore Networking card: selected=${networkPage.selectedCard}, front=${networkPage.frontCard}, checked=${firstTab.checked}, focus=${firstTab.activeFocus}, pickerEnabled=${picker.enabled}, scanning=${networkPage.wifiDevice.scannerEnabled}, activeFocus=${networkWindow.activeFocusItem}`)
            root.checkNetworkCards(firstTab, secondTab, networkPage)
            if (wifiPage.contentY !== 50 || networkPage.errorMessage !== "Retained fixture error"
                    || page.active || page.data.selected !== "")
                throw new Error("Card exchange reset page state or left Tailscale active")
            networkPage.errorMessage = ""
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
                throw new Error("Screenshot dismissal must hide the widget immediately")
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
            root.performanceHeightBefore = performance.implicitHeight
            performance.metrics = { now: root.now, cpu: { history: [] },
                cpuTemperature: null, memory: { current: null, history: [] }, gpus: [] }
            finish.start()
            } catch (error) { console.error(error); Qt.exit(1) }
        }
    }
    Timer {
        id: cancelSleep
        interval: 100
        onTriggered: chargingBattery.state = UPowerDeviceState.Charging
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
            if (performance.implicitHeight <= 0
                    || performance.implicitHeight >= root.performanceHeightBefore)
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
            try { root.checkSharedCards(); root.checkPopoutFocus(); root.checkTailscaleConnection(); root.checkTailscaleLifetime(); root.checkRetainedNetworkFocus() }
            catch (error) { console.error(error); Qt.exit(1); return }
            console.log("CONTROL_CHECK_PASSED")
            Qt.quit()
        }
    }
}
"""

# Separate run so rendering waits cannot disturb the metric/lifecycle timers.
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
            } catch (error) { console.error(error); Qt.exit(1) }
        }
    }
}
"""

SERVICE_FIXTURES = {
    "Pipewire": """
        property var nodes: ({values: Array.from({length: 2}, (_, id) => ({
            id: id, name: "Audio " + id, description: "Device " + id,
            isSink: true, isStream: false, audio: {muted: false, volume: 0.5}}))})
        property var defaultAudioSink: nodes.values[0]
        property var defaultAudioSource: null
        property var preferredDefaultAudioSink: null
        property var preferredDefaultAudioSource: null
    """,
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
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "icewine").mkdir()
    # Exercise the real pages, substituting only service imports for synthetic devices.
    shutil.copytree(source / "quickshell/modules", root / "icewine/modules", copy_function=shutil.copyfile)
    for name, service in (("Audio", "Quickshell.Services.Pipewire"),
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
    (root / "config").symlink_to(source / "quickshell/config")
    (root / "bin").mkdir()
    mock = root / "bin/icewine-monitor-brightness"
    mock.write_text("#!" + shutil.which("bash") + '\necho "${2:-37}"\n')
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
        " selection = state.read_text() if state.exists() else ''\n" +
        " selected = selection not in ('', 'cleared')\n" +
        " print(json.dumps({'BackendState': backend.read_text() if backend.exists() else 'Running', 'Self': {'ID': profile.read_text() if profile.exists() else 'fixture-local', 'HostName': '<b>Fixture laptop</b>', 'Online': selection not in ('offline', 'cleared')}, " +
        "'Peer': {'demo': {'ID': 'fixture-exit', 'HostName': 'Home gateway', 'TailscaleIPs': ['100.64.0.2'], 'Online': True, 'ExitNodeOption': True}, " +
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
                                capture_output=True, text=True, timeout=40)
    except subprocess.TimeoutExpired as error:
        raise AssertionError((error.stdout or b"").decode() + (error.stderr or b"").decode()) from error
    output = result.stdout + result.stderr
    assert result.returncode == 0 and "CONTROL_CHECK_PASSED" in output, output
    assert not re.search(r"ReferenceError|TypeError|[Bb]inding loop|Unable to assign", output), output
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
    for name in ("Audio", "Network"):
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
