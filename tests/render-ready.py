#!/usr/bin/env python3
"""Exercise Steam launch and real authentication adapters with offscreen mocks.
Run: python3 tests/render-ready.py . [preview-directory] (requires qs on PATH).
"""
import os
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
preview_dir = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None
if preview_dir:
    preview_dir.mkdir(parents=True, exist_ok=True)
qml = """import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import "icewine/modules" as Modules
import "sddm" as Sddm
import "theme" as Theme
ShellRoot {
    id: root
    property int launches: 0
    property var authChildren: []
    QtObject {
        id: compositor
        readonly property var toplevels: []
        signal monitorsChanged()
        function getMonitors() {
            return [{name: Quickshell.screens[0].name,
                width: 640, height: 480, focused: true}]
        }
        function activateWindow(address) { throw new Error("Unexpected focus request") }
    }
    Modules.GameLauncher { id: launcher; compositor: compositor }
    ListModel {
        id: userModel
        property int lastIndex: 0
        ListElement { name: "demo"; realName: "Peter" }
        ListElement { name: "guest"; realName: "" }
    }
    ListModel {
        id: sessionModel
        property int lastIndex: 1
        ListElement { name: "Other" }
        ListElement { name: "Hyprland" }
    }
    QtObject {
        id: sddm
        readonly property bool canReboot: true
        readonly property bool canPowerOff: true
        property int logins: 0
        signal loginFailed()
        signal loginSucceeded()
        function login(user, password, session) {
            if (user !== "guest" || password !== "test-secret" || session !== 0)
                throw new Error("Wrong SDDM login arguments")
            logins++
        }
    }
    Window {
        id: loginWindow
        visible: true
        width: 1920; height: 1080
        Sddm.Main { id: login; anchors.fill: parent }
        TestCase { id: keys; when: false }
    }
    property var auth: Array.from(login.children).find(child => child.controller !== undefined)
    Modules.SessionControl { id: session; authenticationRequired: false }
    QtObject {
        id: lockSession
        property bool locked: true
        property string password: ""
        property bool authenticationRequired: true
        property bool authenticating: false
        property bool failed: false
        property var keyboardHost: null
        property bool keyboardVisible: false
        property real keyboardHeight: 280
        property int submissions: 0
        property int reboots: 0
        property int shutdowns: 0
        function submit() { ++submissions; authenticating = true; password = "" }
        function requestReboot() { ++reboots }
        function requestShutdown() { ++shutdowns }
        function toggleKeyboard(host) { keyboardHost = host; keyboardVisible = !keyboardVisible }
    }
    Window {
        id: lockWindow
        visible: true
        width: 1280; height: 800
        Modules.LockScreenSurface { id: locker; anchors.fill: parent; session: lockSession }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width; height: lockSession.keyboardHeight
            visible: lockSession.keyboardVisible
            color: lockScreen.palette.backgroundDark
            border.color: lockScreen.palette.border
            Text { anchors.centerIn: parent; text: "Mock on-screen keyboard"; color: lockScreen.palette.foreground }
        }
    }
    property var lockScreen: Array.from(locker.children).find(child => child.controller !== undefined)
    function findItem(parent, name) {
        if (parent.objectName === name || parent.Accessible.name === name) return parent
        for (const child of parent.children ?? []) {
            const found = findItem(child, name)
            if (found) return found
        }
        return null
    }
    function checkLayout(screen, inset) {
        const panel = findItem(screen, "authPanel")
        const body = findItem(screen, "authBody")
        const footer = findItem(screen, "authFooter")
        const field = findItem(screen, "authPassword")
        if (panel.width > screen.width || panel.height !== screen.height
                || panel.width < Math.min(screen.width, 288)
                || body.height <= 0 || footer.y + footer.height > screen.height - inset)
            throw new Error("Authentication panel/content bounds failed")
        const mapped = field.mapToItem(body, 0, 0)
        if (field.activeFocus && (mapped.y < -1 || mapped.y + field.height > body.height + 1))
            throw new Error("Focused password obscured by keyboard")
        const status = findItem(screen, "authStatus")
        const statusPosition = status.mapToItem(body, 0, 0)
        if (field.activeFocus && status.text && statusPosition.y + status.height > body.height + 1)
            throw new Error("Authentication status obscured by keyboard")
        const keyboardButton = findItem(screen, "Keyboard")
        const sessionButton = findItem(screen, "Select session")
        if (sessionButton.visible && keyboardButton.y + keyboardButton.height > sessionButton.y)
            throw new Error("Keyboard must sit directly above session")
    }
    property int captures: 0
    function capture(item, name) {
        const directory = Quickshell.env("ICEWINE_PREVIEW_DIR")
        if (!directory) return
        ++captures
        item.grabToImage(result => {
            if (!result.saveToFile(directory + "/" + name + ".png"))
                throw new Error("Preview capture failed")
            --root.captures
        })
    }
    function authChild(predicate) {
        for (const child of auth.children ?? []) {
            if (predicate(child)) return child
        }
        return null
    }
    Component.onCompleted: launcher.launchSteamGamescope()
    Timer {
        id: renderTimer
        interval: 100
        running: true
        repeat: true
        onTriggered: {
            renderTimer.stop()
            if (root.authChildren.length === 0) {
                const controller = auth.controller
                const inputPanel = Array.from(login.children).find(child => child.active !== undefined)
                if (controller.keyboardEnabled !== false || controller.keyboardVisible
                        || !inputPanel || inputPanel.visible)
                    throw new Error("SDDM keyboard must start hidden")
                if (inputPanel.width > 900 || inputPanel.width > login.width
                        || inputPanel.width > login.height * 1.5
                        || inputPanel.x !== (login.width - inputPanel.width) / 2)
                    throw new Error("SDDM keyboard size or centring failed")
                // Mock input-method activation; offscreen has no native OSK service.
                inputPanel.visible = Qt.binding(() => controller.keyboardEnabled)
                loginWindow.requestActivate()
                root.findItem(auth, "authPassword").forceActiveFocus()
                controller.toggleKeyboard(auth)
                keys.tryCompare(inputPanel, "visible", true)
                keys.wait(50)
                root.checkLayout(auth, inputPanel.height)
                if (!controller.keyboardEnabled)
                    throw new Error("SDDM keyboard explicit enable failed")
                controller.toggleKeyboard(auth)
                if (controller.keyboardEnabled || inputPanel.visible)
                    throw new Error("SDDM keyboard explicit disable failed")
                if (controller.userCount !== 2 || controller.userLabel !== "Peter"
                        || controller.sessionCount !== 2 || controller.sessionLabel !== "Hyprland")
                    throw new Error("SDDM model bindings failed")
                root.capture(auth, "login-dark-idle")
                keys.tryCompare(root, "captures", 0, 2000)
                controller.password = "discard-on-user-change"
                controller.nextUser()
                controller.nextSession()
                if (controller.password !== "" || controller.userLabel !== "guest")
                    throw new Error("SDDM user selection failed")
                controller.password = "test-secret"
                controller.submit()
                controller.submit()
                if (sddm.logins !== 1 || !controller.busy || controller.password !== "")
                    throw new Error("SDDM submission guard failed")
                sddm.loginFailed()
                if (controller.busy || !controller.failed)
                    throw new Error("SDDM failure recovery failed")
                controller.password = "test-secret"
                controller.submit()
                sddm.loginSucceeded()
                if (sddm.logins !== 2 || controller.failed || !controller.busy)
                    throw new Error("SDDM retry failed")
                if (typeof session.keyboardVisible !== "boolean"
                        || !Number.isFinite(session.keyboardHeight))
                    throw new Error("SessionControl keyboard bindings failed")
                controller.busy = false
                const field = root.findItem(auth, "authPassword")
                loginWindow.requestActivate()
                keys.tryCompare(loginWindow, "active", true)
                field.forceActiveFocus()
                keys.keyClick(Qt.Key_Tab)
                if (!root.findItem(auth, "Continue").activeFocus)
                    throw new Error("Password Tab navigation failed: " + loginWindow.activeFocusItem)
                field.forceActiveFocus()
                controller.busy = false
                field.text = "test-secret"
                keys.keyClick(Qt.Key_Return)
                if (sddm.logins !== 3 || !controller.busy)
                    throw new Error("Password Return submission failed")
                sddm.loginFailed()
                keys.tryCompare(field, "activeFocus", true)
                if (field.text !== "" || !controller.failed)
                    throw new Error("Failure must clear and refocus password")
                root.checkLayout(auth, 0)
                root.capture(auth, "login-dark-desktop")
                keys.tryCompare(root.findItem(lockScreen, "authBackdrop"), "status", Image.Ready, 2000)
                root.capture(lockWindow.contentItem, "lock-dark-deck")
                keys.tryCompare(root, "captures", 0, 2000)
                root.authChildren = Array.from(auth.children)
                session.keyboardHost = auth
                loginWindow.width = 800
                loginWindow.height = 600
            }
            if (launcher.pendingSteamCommand !== null) { renderTimer.start(); return }
            if (!launcher.steamLaunching || !launcher.steamSplashVisible)
                throw new Error("Missing launch state after the placeholder's first frame")
            if (!JSON.parse(launcher.launchSteamGamescope()).pending)
                throw new Error("Repeated request was not guarded")
            launcher.finishSteamLaunch()
            if (launcher.steamLaunching || launcher.steamSplashVisible)
                throw new Error("Teardown did not clear launch state")
            if (++root.launches === 2) {
                const keyboard = root.authChild(item => !root.authChildren.includes(item))
                if (auth.scaleFactor !== 0.8)
                    throw new Error("Small-screen type scaling failed")
                if (!keyboard || keyboard.width !== auth.width
                        || keyboard.y !== auth.height - keyboard.height
                        || session.keyboardHeight !== keyboard.height)
                    throw new Error("SessionControl keyboard host bindings failed")
                auth.palette = Theme.LightPalette
                lockScreen.palette = Theme.LightPalette
                keys.wait(50)
                root.checkLayout(auth, 0)
                root.capture(auth, "login-light-small")
                keys.tryCompare(root, "captures", 0, 2000)
                lockWindow.width = 800; lockWindow.height = 600
                const lockField = root.findItem(lockScreen, "authPassword")
                lockWindow.requestActivate()
                keys.tryCompare(lockWindow, "active", true)
                lockField.forceActiveFocus()
                lockField.text = "mock-lock-secret"
                keys.keyClick(Qt.Key_Return)
                if (lockSession.submissions !== 1 || !lockSession.authenticating
                        || lockSession.password !== "" || !lockSession.locked)
                    throw new Error("Lock adapter submission bypassed session or retained password")
                lockSession.failed = true
                lockSession.authenticating = false
                keys.tryCompare(lockField, "activeFocus", true)
                root.findItem(lockScreen, "Keyboard").click()
                keys.wait(50)
                root.checkLayout(lockScreen, 280)
                root.capture(lockWindow.contentItem, "lock-light-small-keyboard")
                keys.tryCompare(root, "captures", 0, 2000)
                root.findItem(lockScreen, "Reboot").click()
                root.findItem(lockScreen, "Shutdown").click()
                if (lockSession.reboots !== 1 || lockSession.shutdowns !== 1)
                    throw new Error("Lock adapter power routing failed")
                root.findItem(lockScreen, "Keyboard").click()
                lockWindow.width = 320; lockWindow.height = 480
                keys.wait(50)
                root.checkLayout(lockScreen, 0)
                keys.tryCompare(root, "captures", 0, 2000)
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

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "icewine").mkdir()
    (root / "icewine/modules").symlink_to(source / "quickshell/modules")
    (root / "icewine/theme").symlink_to(root / "theme")
    (root / "theme").mkdir()
    palette = (source / "theme/assets/templates/Palette.qml.in").read_text()
    for name, theme in [("Palette", "tokyo-night"), ("LightPalette", "gruvbox-light")]:
        colours = json.loads((source / "theme/assets/themes" / (theme + ".json")).read_text())
        (root / "theme" / (name + ".qml")).write_text(
            re.sub(r"@(\w+)@", lambda match: colours[match[1]], palette))
    (root / "theme/qmldir").write_text(
        "singleton Palette 1.0 Palette.qml\nsingleton LightPalette 1.0 LightPalette.qml\n")
    (root / "sddm").mkdir()
    (root / "sddm/Main.qml").symlink_to(source / "sddm/Main.qml")
    (root / "sddm/modules").symlink_to(source / "quickshell/modules")
    (root / "sddm/theme").symlink_to(root / "theme")
    (root / "config").mkdir()
    (root / "config/qmldir").write_text("singleton Settings 1.0 Settings.qml\n")
    (root / "config/Settings.qml").write_text("""pragma Singleton
import QtQml
QtObject {
    readonly property bool authenticationRequired: false
}
""")
    (root / "data/wallpapers").mkdir(parents=True)
    (root / "data/wallpapers/default.jpg").symlink_to(source / "theme/assets/flower-branch.png")
    (root / "bin").mkdir()
    for name, body in {
        "uwsm": 'printf "%s\\n" "$*" >> "$TEST_LAUNCHES"\n',
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
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
               XDG_CACHE_HOME=str(root / "cache"), XDG_RUNTIME_DIR=str(runtime),
               PATH=str(root / "bin") + os.pathsep + os.environ["PATH"],
               TEST_LAUNCHES=str(root / "launches"), XDG_DATA_HOME=str(root / "data"))
    if preview_dir:
        env["ICEWINE_PREVIEW_DIR"] = str(preview_dir)
    try:
        result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                                capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired as error:
        raise AssertionError((error.stdout or b"") + (error.stderr or b"")) from error
    output = result.stdout + result.stderr
    assert result.returncode == 0 and "RENDER_READY_PASSED" in output, output
    assert "Failed to load configuration" not in output, output
    assert not re.search(r"ReferenceError|TypeError|Binding loop|Unable to assign", output), output
    launches = (root / "launches").read_text().splitlines()
    assert len(launches) == 2 and all(
        line.startswith("app -t service -u icewine-steam-gamescope.service "
                        "-p ExitType=main -p KillMode=control-group "
                        "-- gamescope ")
        for line in launches
    ), launches
    print("Steam launch, auth visuals, locker and SDDM adapter checks passed")
