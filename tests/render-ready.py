#!/usr/bin/env python3
"""Exercise Steam's real first-frame launch and placeholder teardown offscreen."""
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
import "modules" as Modules
ShellRoot {
    id: root
    property int launches: 0
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
    Component.onCompleted: launcher.launchSteamGamescope()
    Timer {
        interval: 100
        running: true
        repeat: true
        onTriggered: {
            if (launcher.pendingSteamCommand !== null) return
            if (!launcher.steamLaunching || !launcher.steamSplashVisible)
                throw new Error("Missing launch state after the placeholder's first frame")
            if (!JSON.parse(launcher.launchSteamGamescope()).pending)
                throw new Error("Repeated request was not guarded")
            launcher.finishSteamLaunch()
            if (launcher.steamLaunching || launcher.steamSplashVisible)
                throw new Error("Teardown did not clear launch state")
            if (++root.launches === 2) {
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
    (root / "modules").symlink_to(source / "quickshell/modules")
    (root / "theme").mkdir()
    palette = (source / "quickshell/theme/Palette.qml.in").read_text()
    (root / "theme/Palette.qml").write_text(re.sub(r"@\w+@", "7aa2f7", palette))
    (root / "theme/qmldir").write_text("singleton Palette 1.0 Palette.qml\n")
    (root / "bin").mkdir()
    for name, body in {
        "uwsm": 'printf "%s\\n" "$*" >> "$TEST_LAUNCHES"\n',
        "icewine-monitor-capabilities": "exit 0\n",
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
    launches = (root / "launches").read_text().splitlines()
    assert len(launches) == 2 and all(
        line.startswith("app -u icewine-steam-gamescope.scope -- gamescope ")
        for line in launches
    ), launches
    print("Steam first-frame launch, duplicate guard, teardown and relaunch passed")
