#!/usr/bin/env python3
"""Exercise actual Steam launch and workspace presentation with offscreen fixtures.
Authentication and native OSK coverage lives in breeze-lock.py/breeze-sddm.py.
Run: python3 tests/render-ready.py . [preview-directory] [--workspaces=THEME].
"""
import os
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from qml_fixture import theme_fixture

workspace_theme = next((arg.split("=", 1)[1] for arg in sys.argv[2:]
                        if arg.startswith("--workspaces=")), None)
source = Path(sys.argv[1]).resolve()
preview_arg = next((arg for arg in sys.argv[2:] if not arg.startswith("--")), None)
preview_dir = Path(preview_arg).resolve() if preview_arg else None
if preview_dir:
    preview_dir.mkdir(parents=True, exist_ok=True)
qml = """import QtQuick
import QtTest
import Quickshell
import "icewine/modules" as Modules
ShellRoot {
    id: root
    property int launches: 0
    QtObject {
        id: compositor
        property var toplevels: []
        property string activated: ""
        signal monitorsChanged()
        function getMonitors() {
            return [{name: Quickshell.screens[0].name, width: 640, height: 480, focused: true}]
        }
        function activateWindow(address) { activated = address }
    }
    Modules.GameLauncher { id: launcher; compositor: compositor }
    TestCase { id: keys; when: false }
    Component.onCompleted: launcher.launchSteamGamescope()
    Timer {
        id: renderTimer
        interval: 100; running: true; repeat: true
        onTriggered: {
            renderTimer.stop()
            if (launcher.pendingSteamCommand !== null) { renderTimer.start(); return }
            if (!launcher.steamLaunching)
                throw new Error("Missing launch state after the placeholder's first frame")
            if (!JSON.parse(launcher.launchSteamGamescope()).pending)
                throw new Error("Repeated request was not guarded")
            if (root.launches === 0) {
                // The running Flatpak singleton opens an outer window after splash startup.
                compositor.toplevels = [{address: "0xouter", lastIpcObject: {class: "com.valvesoftware.Steam"}}]
                keys.tryCompare(launcher, "steamLaunching", false)
                if (launcher.steamLaunching || launcher.steamRequestPending
                        || launcher.pendingSteamCommand !== null || compositor.activated !== "0xouter")
                    throw new Error("Outside singleton did not complete the shared launch")
                const reused = JSON.parse(launcher.launchSteamGamescope())
                if (!reused.reused || !reused.outsideGamescope || launcher.steamLaunching)
                    throw new Error("Visible outside session was not identified/reused")
                launcher.steamRequestPending = true
                launcher.steamGamescopePid = 481
                compositor.toplevels = [{address: "0xnested", wayland: {appId: "gamescope"},
                    lastIpcObject: {pid: 481}}, ...compositor.toplevels]
                keys.tryCompare(compositor, "activated", "0xnested")
                if (launcher.steamRequestPending)
                    throw new Error("Managed nested reuse left a pending request")
                const nestedReuse = JSON.parse(launcher.launchSteamGamescope())
                if (!nestedReuse.reused || nestedReuse.outsideGamescope
                        || compositor.activated !== "0xnested")
                    throw new Error("Shared entry did not prefer the managed nested session")
                compositor.toplevels = []
                launcher.steamRequestPending = true
                launcher.resolveSteamRequest("unavailable")
                if (launcher.steamRequestPending || launcher.steamLaunching)
                    throw new Error("Detection error retained launch state")
            } else {
                launcher.finishSteamLaunch()
            }
            if (launcher.steamLaunching)
                throw new Error("Teardown did not clear launch state")
            if (++root.launches === 2) {
                console.log("RENDER_READY_PASSED")
                Qt.quit()
            } else {
                launcher.launchSteamGamescope()
                renderTimer.start()
            }
        }
    }
}
"""

if workspace_theme:
    qml = """import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import "icewine/modules/topbar" as Topbar
import "theme" as Theme
ShellRoot {
    id: root
    QtObject { id: first; property bool activated: true; property var wayland: ({appId: ""}) }
    QtObject { id: second; property bool activated: false; property var wayland: ({appId: ""}) }
    QtObject { id: third; property bool activated: false; property var wayland: ({appId: ""}) }
    QtObject {
        id: compositor
        property var monitor: ({activeWorkspace: {id: 1}})
        property int requests: 0
        function monitorFor(screen) { return monitor }
        function workspaceIdsForMonitor(monitor) { return [1, 2, 3] }
        function toplevelsForWorkspace(id) { return id === 1 ? [first, second] : id === 2 ? [third] : [] }
        function activateWorkspace(id) { requests++; monitor = {activeWorkspace: {id: id}} }
    }
    Window {
        id: window
        visible: true; width: 640; height: 140
        color: Theme.Palette.background
        Rectangle { anchors.fill: parent; color: Theme.Palette.background }
        Text { x: 20; y: 15; text: "Active workspace / focused window · 2× preview"; color: Theme.Palette.foreground }
        Topbar.Workspaces { id: workspaces; x: 20; y: 65; scale: 2; transformOrigin: Item.TopLeft; compositor: compositor; screen: Quickshell.screens[0] }
        TestCase {
            id: keys
            when: false
            function descendants(item, predicate) {
                let result = predicate(item) ? [item] : []
                for (const child of item.children ?? []) result = result.concat(descendants(child, predicate))
                return result
            }
            function blend(colour, background) {
                return [colour.r, colour.g, colour.b].map((value, i) => colour.a * value + (1 - colour.a) * background[i])
            }
            function luminance(rgb) {
                return rgb.map(value => value <= 0.04045 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4))
                    .reduce((sum, value, i) => sum + value * [0.2126, 0.7152, 0.0722][i], 0)
            }
            function contrast(colour, background) {
                const a = luminance([colour.r, colour.g, colour.b]), b = luminance(background)
                return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
            }
            function test_focusPresentation() {
                tryVerify(() => DesktopEntries.byId("workspace-test") !== null, 2000)
                for (const app of [first, second, third]) app.wayland = {appId: "workspace-test"}
                wait(100)
                const buttons = descendants(workspaces, item => item.workspaceId !== undefined)
                compare(buttons.length, 3)
                verify(buttons[0].active)
                verify(buttons[0].color.a < 0.3, "Workspace tint must stay subtle")
                const icons = descendants(workspaces, item => item.appId !== undefined)
                compare(icons.length, 3)
                compare(icons.filter(item => item.focused).length, 1)
                const backgrounds = icons.map(item => item.children.find(child => child.radius === 4))
                compare(backgrounds[0].color, Theme.Palette.primary)
                compare(backgrounds[1].color.a, 0)
                const base = blend(workspaces.color, [window.color.r, window.color.g, window.color.b])
                const activeBackground = blend(buttons[0].color, base)
                const label = descendants(buttons[0], item => item.text === "1")[0]
                verify(contrast(label.color, activeBackground) >= 4.5, "Workspace label contrast")
                const fallback = descendants(icons[0], item => item.text !== undefined)[0]
                verify(contrast(fallback.color, [backgrounds[0].color.r, backgrounds[0].color.g, backgrounds[0].color.b]) >= 4.5, "Focused fallback contrast")
                const images = descendants(workspaces, item => item.sourceSize !== undefined)
                for (const image of images) tryCompare(image, "status", Image.Ready, 2000)
                const directory = Quickshell.env("ICEWINE_PREVIEW_DIR")
                if (directory) {
                    let captured = false
                    verify(window.contentItem.grabToImage(result => {
                        verify(result.saveToFile(directory + "/workspaces.png"))
                        captured = true
                    }))
                    tryVerify(() => captured, 2000)
                }
                first.activated = false; second.activated = true
                wait(20)
                compare(backgrounds[0].color.a, 0)
                compare(backgrounds[1].color, Theme.Palette.primary)
                const secondLabel = descendants(buttons[1], item => item.text === "2")[0]
                mouseClick(secondLabel, secondLabel.width / 2, secondLabel.height / 2)
                compare(compositor.requests, 1)
                compare(workspaces.activeId, 2)
                wait(150)
                verify(buttons[1].active)
                verify(buttons[1].color.a < 0.3)
                console.log("WORKSPACES_PASSED")
                Qt.quit()
            }
        }
        Timer {
            interval: 100; running: true; repeat: false
            onTriggered: {
                try { keys.test_focusPresentation() }
                catch (error) { console.error("Workspace check failed:", error); Qt.exit(1) }
            }
        }
    }
}
"""

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "icewine").mkdir()
    (root / "icewine/modules").symlink_to(source / "quickshell/modules")
    (root / "icewine/theme").symlink_to(root / "theme")
    fixture_config = theme_fixture(source, root, workspace_theme or "tokyo-night")
    if workspace_theme:
        (root / "data/applications").mkdir(parents=True)
        (root / "data/window.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect x="2" y="3" width="28" height="26" rx="3" fill="#3a82c3" stroke="#ffffff" stroke-width="2"/><path d="M3 10h26" stroke="#ffffff" stroke-width="2"/></svg>')
        (root / "data/applications/workspace-test.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Workspace fixture\nExec=true\nIcon=" + str(root / "data/window.svg") + "\n")
    (root / "bin").mkdir()
    for name, body in {
        "uwsm": 'printf "%s\\n" "$*" >> "$TEST_LAUNCHES"\n',
        "notify-send": 'printf "%s\\n" "$*" >> "$TEST_NOTIFICATIONS"\n',
        "icewine-monitor-capabilities": "exit 0\n",
        "systemctl": 'printf "LoadState=not-found\\nMainPID=0\\n"\n',
        "gdbus": '''if [[ "$1" == "call" ]]; then
    printf "(objectpath '/org/freedesktop/login1/session/_test',)\\n"
else
    exec sleep 10
fi
''',
    }.items():
        command = root / "bin" / name
        command.write_text("#!" + shutil.which("bash") + "\n" + body)
        command.chmod(0o700)
    (root / "shell.qml").write_text(qml)
    runtime = root / "runtime"
    runtime.mkdir(mode=0o700)
    # Ponytail: inherited feature flags stay until a real fixture failure warrants explicit inputs; then pin only the tested flags.
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
               XDG_CACHE_HOME=str(root / "cache"), XDG_RUNTIME_DIR=str(runtime),
               QML_IMPORT_PATH=str(root), XDG_CONFIG_HOME=fixture_config,
               PATH=str(root / "bin") + os.pathsep + os.environ["PATH"],
               TEST_LAUNCHES=str(root / "launches"), TEST_NOTIFICATIONS=str(root / "notifications"), XDG_DATA_HOME=str(root / "data"))
    if workspace_theme:
        env["XDG_DATA_DIRS"] = str(root / "data")
    if preview_dir:
        env["ICEWINE_PREVIEW_DIR"] = str(preview_dir)
    try:
        result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                                capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired as error:
        raise AssertionError((error.stdout or b"") + (error.stderr or b"")) from error
    output = result.stdout + result.stderr
    assert result.returncode == 0 and ("WORKSPACES_PASSED" if workspace_theme else "RENDER_READY_PASSED") in output, output
    assert "Failed to load configuration" not in output, output
    assert not re.search(r"ReferenceError|TypeError|Binding loop|Unable to assign", output), output
    if workspace_theme:
        print("Workspace focus presentation passed:", workspace_theme)
        sys.exit(0)
    launches = (root / "launches").read_text().splitlines()
    assert len(launches) == 2 and all(
        line.startswith("app -t service -u icewine-steam-gamescope.service "
                        "-p ExitType=main -p KillMode=control-group "
                        "-- gamescope ")
        for line in launches
    ), launches
    notifications = (root / "notifications").read_text().splitlines()
    assert len(notifications) == 2 and all(
        "Steam is already running outside Gamescope" in line
        and "Quit Steam to launch it in Gamescope." in line for line in notifications), notifications
    print("PASS: Steam launch, singleton reuse, request guards and teardown")
