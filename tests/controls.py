#!/usr/bin/env python3
"""Check controls, live metric sampling and the performance terminal handoff.
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
import Quickshell
import "modules/topbar" as Bar
import "modules/topbar/popouts" as Popouts
ShellRoot {
    id: root
    property bool keepAwake: false
    property bool doNotDisturb: false
    property int count: 0
    property var items: []
    property double now: Date.now()
    property bool handedOff: false
    property real performanceHeightBefore: 0
    property string sessionAction: ""
    signal tick()
    QtObject {
        id: compositor
        readonly property var toplevels: []
        function activateWindow(address) {}
    }
    QtObject {
        id: session
        function requestLock() { root.sessionAction = "lock" }
        function requestSleep() { root.sessionAction = "sleep" }
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
    Bar.SystemMetrics { id: systemMetrics }
    Bar.HistoryGraph {
        id: coldGraph
        width: 380
        title: "Temperature"
        unit: "°C"
        history: [{ time: root.now - 121000, values: [-50] },
            { time: root.now - 1000, values: [-5] }, { time: root.now, values: [null] }]
        now: root.now
    }

    function findButton(item) {
        if (item.text === "Advanced · btop") return item
        for (const child of item.children ?? []) {
            const button = findButton(child)
            if (button) return button
        }
        return null
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
            onHandoffRequested: root.handedOff = true
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
    Timer {
        interval: 400
        running: true
        onTriggered: {
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
            root.tick()
            const button = root.findButton(performance)
            if (!button) throw new Error("Missing btop button")
            button.click()
            root.performanceHeightBefore = performance.implicitHeight
            performance.metrics = { now: root.now, cpu: { history: [] },
                cpuTemperature: null, memory: { current: null, history: [] }, gpus: [] }
            finish.start()
        }
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
            if (!brightness.available || brightness.value !== 76)
                throw new Error("Pending brightness did not survive popup closure")
            if (network.history.length !== 2 || network.history[1].values[0] !== 0)
                throw new Error("Network sampler did not read counters")
            if (!root.handedOff) throw new Error("btop launch did not hand off focus")
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
            console.log("CONTROL_CHECK_PASSED")
            Qt.quit()
        }
    }
}
"""

source = Path(sys.argv[1]).resolve()
notifications = (source / "quickshell/modules/topbar/popouts/Notifications.qml").read_text()
battery = (source / "quickshell/modules/topbar/popouts/Battery.qml").read_text()
assert 'text: "Do Not Distrub"' in notifications
assert battery.index('text: "Power"') < battery.index('id: lockButton')
assert battery.index('id: lockButton') < battery.index('id: keepAwake')
assert battery.index('id: keepAwake') < battery.index('visible: root.batteryPresent')
assert battery.index('id: keepAwake') < battery.index('text: "Battery condition"')
for action in ["Lock", "Sleep", "Reboot", "Shutdown"]:
    assert f'Accessible.name: "{action}"' in battery
    assert f'Controls.ToolTip.text: "{action}"' in battery
action_button = (source / "quickshell/modules/topbar/popouts/ActionButton.qml").read_text()
assert 'focusPolicy: Qt.StrongFocus' in action_button
assert 'Keys.onReleased' in action_button
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "modules").symlink_to(source / "quickshell/modules")
    (root / "theme").mkdir()
    palette = (source / "theme/assets/templates/Palette.qml.in").read_text()
    (root / "theme/Palette.qml").write_text(re.sub(r"@\w+@", "7aa2f7", palette))
    (root / "theme/qmldir").write_text("singleton Palette 1.0 Palette.qml\n")
    (root / "bin").mkdir()
    mock = root / "bin/icewine-monitor-brightness"
    mock.write_text("#!" + shutil.which("bash") + '\necho "${2:-37}"\n')
    mock.chmod(0o755)
    uwsm = root / "bin/uwsm"
    uwsm.write_text("#!" + shutil.which("bash") + '\nprintf "%s\\n" "$@" > "' + str(root / "launch") + '"\n')
    uwsm.chmod(0o755)
    (root / "shell.qml").write_text(QML)
    (root / "network.txt").write_text("eth0: 100 0 0 0 0 0 0 0 50 0 0 0 0 0 0 0\n")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
               DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(root / "no-session-bus"),
               DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(root / "no-system-bus"),
               XDG_CACHE_HOME=str(root / "cache"), XDG_RUNTIME_DIR=str(root / "runtime"),
               PATH=str(root / "bin") + os.pathsep + os.environ["PATH"])
    result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                            capture_output=True, text=True, timeout=10)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and "CONTROL_CHECK_PASSED" in output, output
    assert not re.search(r"ReferenceError|TypeError|Binding loop|Unable to assign", output), output
    assert (root / "launch").read_text().splitlines() == ["app", "--", "icewine-terminal-exec", "btop"]
    print("control lifecycle checks passed")
