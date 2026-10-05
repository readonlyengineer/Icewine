#!/usr/bin/env python3
"""Exercise Steam launch, shared winter visuals and the SDDM adapter offscreen."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
qml = """import QtQuick
import Quickshell
import "icewine/modules" as Modules
import "sddm" as Sddm
ShellRoot {
    id: root
    property int launches: 0
    property var winterChildren: []
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
        ListElement { name: "demo"; realName: "Demo" }
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
    Sddm.Main { id: login; width: 1000; height: 500 }
    property var winter: Array.from(login.children).find(child => child.controller !== undefined)
    Modules.SessionControl { id: session; authenticationRequired: false }
    Modules.LockScreenSurface { width: 1000; height: 500; session: session }
    function winterChild(predicate) {
        for (const child of winter.children ?? []) {
            if (predicate(child)) return child
        }
        return null
    }
    Component.onCompleted: launcher.launchSteamGamescope()
    Timer {
        interval: 100
        running: true
        repeat: true
        onTriggered: {
            if (root.winterChildren.length === 0) {
                const controller = winter.controller
                const inputPanel = Array.from(login.children).find(child => child.active !== undefined)
                if (controller.keyboardEnabled !== false || controller.keyboardVisible
                        || !inputPanel || inputPanel.visible)
                    throw new Error("SDDM keyboard must start hidden")
                if (inputPanel.width > 900 || inputPanel.width > login.width
                        || inputPanel.width > login.height * 1.5
                        || inputPanel.x !== (login.width - inputPanel.width) / 2)
                    throw new Error("SDDM keyboard size or centring failed")
                controller.toggleKeyboard(winter)
                if (!controller.keyboardEnabled)
                    throw new Error("SDDM keyboard explicit enable failed")
                controller.toggleKeyboard(winter)
                if (controller.keyboardEnabled || inputPanel.visible)
                    throw new Error("SDDM keyboard explicit disable failed")
                if (controller.userCount !== 2 || controller.userLabel !== "Demo"
                        || controller.sessionCount !== 2 || controller.sessionLabel !== "Hyprland")
                    throw new Error("SDDM model bindings failed")
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
                const background = root.winterChild(item => item.color !== undefined
                    && String(item.color).toLowerCase() === "#000000"
                    && item.width === winter.width && item.height === winter.height)
                if (!background)
                    throw new Error("Winter black background failed to load")
                root.winterChildren = Array.from(winter.children)
                session.keyboardHost = winter
                login.width = 800
                login.height = 600
            }
            if (launcher.pendingSteamCommand !== null) return
            if (!launcher.steamLaunching || !launcher.steamSplashVisible)
                throw new Error("Missing launch state after the placeholder's first frame")
            if (!JSON.parse(launcher.launchSteamGamescope()).pending)
                throw new Error("Repeated request was not guarded")
            launcher.finishSteamLaunch()
            if (launcher.steamLaunching || launcher.steamSplashVisible)
                throw new Error("Teardown did not clear launch state")
            if (++root.launches === 2) {
                const background = root.winterChild(item => item.color !== undefined
                    && String(item.color).toLowerCase() === "#000000")
                const keyboard = root.winterChild(item => !root.winterChildren.includes(item))
                if (winter.scaleFactor !== 5 / 12
                        || background.width !== 800 || background.height !== 600)
                    throw new Error("Winter size bindings failed")
                if (!keyboard || keyboard.width !== winter.width
                        || keyboard.y !== winter.height - keyboard.height
                        || session.keyboardHeight !== keyboard.height)
                    throw new Error("SessionControl keyboard host bindings failed")
                winter.palette = Object.assign({}, winter.palette,
                    { dark: false, background: "#fbf1c7" })
                if (String(background.color).toLowerCase() !== "#fbf1c7")
                    throw new Error("Light lock-screen background failed")
                console.log("RENDER_READY_PASSED")
                Qt.quit()
            } else {
                launcher.launchSteamGamescope()
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
    (root / "theme/Palette.qml").write_text(re.sub(r"@\w+@", "7aa2f7", palette))
    (root / "theme/qmldir").write_text("singleton Palette 1.0 Palette.qml\n")
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
               TEST_LAUNCHES=str(root / "launches"))
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
    print("Steam launch, winter visuals, locker and SDDM adapter checks passed")
