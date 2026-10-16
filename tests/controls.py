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
    Timer { interval: 1300; running: true; onTriggered: cpuFixture.setText("cpu 300 0 0 700 0 0 0 0\\n") }
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
    function checkPopoutFocus() {
        focusWindow.requestActivate()
        toggleKeys.tryCompare(focusWindow, "active", true)
        focusPopout.currentPage = "media"
        toggleKeys.wait(30)
        focusPopout.focusInitial()
        toggleKeys.wait(20)
        const play = root.findAccessible(focusPopout, "Play")
        assertRevealed(play, "Media initial")
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
    function checkNetworkTabs(selected, other, page) {
        const front = selected.background.children[0]
        const back = other.background.children[0]
        const body = descendants(page, item => item instanceof Flickable && !(item instanceof ListView) && item.visible)[0]
        const card = page.children.find(item => item.bottomLeftRadius === 9)
        const edge = front.mapToItem(page, 0, front.height).y
        const top = body.mapToItem(page, 0, 0).y
        if (Math.abs(edge - top) > 0.5 || !card || Math.abs(card.y - top) > 0.5
                || front.color.toString() !== card.color.toString())
            throw new Error(`Selected tab must join the card with no air gap: edge=${edge}, top=${top}, bgY=${selected.background.y}, bgH=${selected.background.height}, tabH=${selected.height}`)
        if (front.y !== 0 || back.y !== 5 || front.height <= back.height)
            throw new Error("Tab silhouettes lost their front/back depth")
        for (const tab of [selected, other]) {
            const left = tab.mapToItem(page, 0, 0).x
            if (Math.abs(selected.width - other.width) > 0.5
                    || tab.contentItem.implicitWidth > tab.contentItem.width
                    || left < -0.5 || left + tab.width > page.width + 0.5)
                throw new Error(`Tab label/target overflow: page=${page.width}, left=${left}, width=${tab.width}, label=${tab.contentItem.implicitWidth}/${tab.contentItem.width}`)
        }
        const ring = descendants(front, item => item.border?.width === 2)[0]
        if (!selected.activeFocus || !ring?.visible)
            throw new Error("Selected tab keyboard focus ring is missing")
        if (body.height <= 0 || !body.clip || body.contentHeight <= body.height)
            throw new Error("Constrained network page must retain its scroll viewport")
    }
    FileView { id: tailscaleSelection; path: Qt.resolvedUrl("exit-node") }
    function checkTailscaleConnection() {
        networkWindow.requestActivate()
        networkKeys.tryCompare(networkWindow, "active", true)
        root.findAccessible(networkPages, "Tailscale tab").click()
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
    FileView { id: tailscaleMode; path: Qt.resolvedUrl("tailscale-mode") }
    function checkTailscaleLifetime() {
        const connection = root.findAccessible(networkPages, "Tailscale connection")
        const picker = root.findAccessible(networkPages, "Exit node")
        const page = picker.parent.parent.parent
        tailscaleMode.setText("success")
        connection.click()
        networkKeys.wait(50)
        const pending = page.request
        networkPages.shown = false
        networkKeys.wait(200) // Outlast the real close animation, while the one-second command is pending.
        if (networkPages.visible || page.active || !page.busy || page.request !== pending)
            throw new Error("Closing StatusPopout discarded or continued polling its pending network page")
        networkPages.shown = true
        networkKeys.wait(30)
        if (root.findAccessible(networkPages, "Tailscale connection") !== connection
                || page.request !== pending || connection.enabled)
            throw new Error("Reopening StatusPopout replaced the request owner or allowed a duplicate mutation")
        page.toggleConnection()
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
        const networking = root.findAccessible(networkPages, "Networking tab")
        networking.click()
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
        const networking = root.findAccessible(networkPages, "Networking tab")
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
            networkWindow.requestActivate()
            networkKeys.tryCompare(networkWindow, "active", true)
            const firstTab = root.findAccessible(networkPages, "Networking tab")
            const secondTab = root.findAccessible(networkPages, "Tailscale tab")
            networkPages.focusInitial()
            if (!firstTab.activeFocus || !firstTab.checked || secondTab.checked)
                throw new Error("Network initial tab/focus is incorrect")
            let networkPage = firstTab
            while (networkPage && networkPage.wifiDevice === undefined) networkPage = networkPage.parent
            const password = descendants(networkPage,
                item => item instanceof TextInput && item.echoMode === TextInput.Password)[0]
            networkPage.passwordNetwork = {name: "Fixture Wi-Fi"}
            password.text = "fixture secret"
            const tabCentre = firstTab.mapToItem(networkPage, firstTab.width / 2, firstTab.height / 2)
            if (networkPage.childAt(tabCentre.x, tabCentre.y) !== password.parent.parent.parent)
                throw new Error("Password overlay must remain above the file tabs")
            networkPage.closePassword()
            if (password.text || networkPage.passwordNetwork)
                throw new Error("Password dismissal retained a secret or pending network")
            for (const width of [380, 280, 200]) {
                networkWindow.width = width
                networkKeys.wait(20)
                root.checkNetworkTabs(firstTab, secondTab, networkPage)
            }
            networkWindow.width = 280
            networkKeys.wait(20)
            const wifiPage = descendants(networkPage, item => item instanceof Flickable && !(item instanceof ListView))[0]
            wifiPage.contentY = 50
            networkPage.errorMessage = "Retained fixture error"
            firstTab.forceActiveFocus()
            networkKeys.keyClick(Qt.Key_Right)
            if (!secondTab.checked || !secondTab.activeFocus)
                throw new Error("Right arrow did not select/focus Tailscale tab")
            networkKeys.wait(20)
            root.checkNetworkTabs(secondTab, firstTab, networkPage)
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
            secondTab.forceActiveFocus()
            networkKeys.keyClick(Qt.Key_Left)
            if (!firstTab.checked || !firstTab.activeFocus || picker.visible || !networkPage.wifiDevice.scannerEnabled)
                throw new Error("Left arrow did not restore Networking page")
            root.checkNetworkTabs(firstTab, secondTab, networkPage)
            if (wifiPage.contentY !== 50 || networkPage.errorMessage !== "Retained fixture error"
                    || page.active || page.data.selected !== "")
                throw new Error("Tab styling reset page state or left Tailscale active")
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
            root.tick()
            root.performanceHeightBefore = performance.implicitHeight
            performance.metrics = { now: root.now, cpu: { history: [] },
                cpuTemperature: null, memory: { current: null, history: [] }, gpus: [] }
            finish.start()
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
            try { root.checkPopoutFocus(); root.checkTailscaleConnection(); root.checkTailscaleLifetime(); root.checkRetainedNetworkFocus() }
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
        " time.sleep(1 if mode else 0.1)\n" +
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
                                capture_output=True, text=True, timeout=25)
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
