#!/usr/bin/env python3
"""Check controls, live metric sampling and performance layout updates.
Run with python3 tests/controls.py . (requires qs on PATH).
"""
import os
from pathlib import Path
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
    Timer {
        interval: 400
        running: true
        onTriggered: {
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
            try { root.checkPopoutFocus() }
            catch (error) { console.error(error); Qt.exit(1); return }
            console.log("CONTROL_CHECK_PASSED")
            Qt.quit()
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
    shutil.copytree(source / "quickshell/modules", root / "icewine/modules")
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
    (root / "theme").mkdir()
    palette = (source / "theme/assets/templates/Palette.qml.in").read_text()
    (root / "theme/Palette.qml").write_text(re.sub(r"@\w+@", "7aa2f7", palette))
    (root / "theme/qmldir").write_text("singleton Palette 1.0 Palette.qml\n")
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
    try:
        result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                                capture_output=True, text=True, timeout=25)
    except subprocess.TimeoutExpired as error:
        raise AssertionError((error.stdout or b"").decode() + (error.stderr or b"").decode()) from error
    output = result.stdout + result.stderr
    assert result.returncode == 0 and "CONTROL_CHECK_PASSED" in output, output
    assert not re.search(r"ReferenceError|TypeError|Binding loop|Unable to assign", output), output
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
