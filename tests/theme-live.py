#!/usr/bin/env python3
"""Exercise the real Quickshell theme IPC and asynchronous renderer offscreen."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time


source = Path(sys.argv[1]).resolve()
quickshell = shutil.which("qs")
colors = {
    "background": "background", "backgroundDark": "backgroundDark",
    "surface": "surface", "selection": "selection", "border": "border",
    "foreground": "foreground", "foregroundDark": "foregroundDark",
    "muted": "muted", "primary": "highlight", "primaryDark": "highlightDark",
    "secondary": "secondaryHighlight", "tertiary": "tertiaryHighlight",
    "success": "success", "warning": "warning", "caution": "caution",
    "error": "error", "info": "info",
}


def palette(theme):
    data = json.loads((source / "theme/assets/themes" / (theme + ".json")).read_text())
    return {"themeId": theme, "dark": data["appearance"] != "light",
            **{key: data[value] for key, value in colors.items()}}


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    (root / "modules").symlink_to(source / "quickshell/modules")
    (root / "theme").symlink_to(source / "quickshell/theme")
    (root / "shell.qml").write_text('''import QtQuick
import Quickshell
import "modules" as Modules
ShellRoot {
    Modules.ThemeService {}
    Timer { interval: 1000; running: true; repeat: true }
}
''')
    current = root / "config/icewine/current"
    current.parent.mkdir(parents=True)
    initial = root / "initial"
    initial.mkdir()
    current.symlink_to(initial)
    (current / "palette.json").write_text(json.dumps(palette("tokyo-night")))
    (root / "state/icewine").mkdir(parents=True)
    (root / "runtime").mkdir()
    (root / "bin").mkdir()
    for theme in ("tokyo-night", "dracula", "nord"):
        (root / (theme + ".json")).write_text(json.dumps(palette(theme)))
    renderer = root / "bin/icewine-theme"
    renderer.write_text("#!/bin/sh\n"
                        "sleep 0.15\n"
                        'test ! -e "$TEST_ROOT/fail" || exit 2\n'
                        'theme=$(cat "$XDG_STATE_HOME/icewine/theme")\n'
                        'cp "$TEST_ROOT/$theme.json" "$XDG_CONFIG_HOME/icewine/current/palette.json"\n')
    renderer.chmod(0o755)
    env = dict(os.environ, HOME=str(root), QT_QPA_PLATFORM="offscreen", WAYLAND_DISPLAY="icewine-test",
               XDG_CONFIG_HOME=str(root / "config"),
               XDG_DATA_HOME=str(root / "data"), ICEWINE_THEME_ASSETS=str(source / "theme/assets"),
               ICEWINE_GTK_ENABLE="false", ICEWINE_DEFAULT_FILES="", HYPRLAND_INSTANCE_SIGNATURE="",
               XDG_STATE_HOME=str(root / "state"), XDG_RUNTIME_DIR=str(root / "runtime"),
               XDG_CACHE_HOME=str(root / "cache"), TEST_ROOT=str(root),
               ICEWINE_THEME_IDS="tokyo-night:dracula:nord:catppuccin-mocha", ICEWINE_THEME_POLICY="",
               ICEWINE_THEME_TRANSITION="off",
               PATH=str(root / "bin") + os.pathsep + os.environ["PATH"])

    def call(function, *args):
        return subprocess.run([quickshell, "-p", str(root), "ipc", "call", "theme", function, *args],
                              env=env, capture_output=True, text=True, timeout=5)

    def until(expected):
        end = time.monotonic() + 8
        while time.monotonic() < end:
            if shell.poll() is not None:
                stdout, stderr = shell.communicate()
                raise AssertionError(f"Quickshell exited during theme check: {stdout} {stderr}")
            result = call("status")
            if result.returncode == 0 and result.stdout.strip() == expected:
                return
            time.sleep(0.05)
        raise AssertionError(f"theme status never became {expected!r}: {result.stdout} {result.stderr}")

    shell = subprocess.Popen(["qs", "-p", str(root), "--no-color"], env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        until("applied: tokyo-night")
        assert call("select", "missing").stdout.strip().startswith("failed:")
        assert not (root / "state/icewine/theme").exists()
        assert call("select", "dracula").stdout.strip().startswith("pending:")
        assert call("select", "nord").stdout.strip().startswith("pending:")
        until("applied: nord")
        assert json.loads((current / "palette.json").read_text())["themeId"] == "nord"
        assert shell.poll() is None

        (root / "fail").touch()
        assert call("select", "dracula").stdout.strip().startswith("pending:")
        until("failed: theme saved, but shell palette kept its previous colours")
        assert (root / "state/icewine/theme").read_text() == "dracula\n"
        assert json.loads((current / "palette.json").read_text())["themeId"] == "nord"
        (root / "fail").unlink()
        assert call("select", "dracula").stdout.strip().startswith("pending:")
        until("applied: dracula")
        assert shell.poll() is None

        state_dir = root / "state/icewine"
        state_dir.chmod(0o500)
        try:
            call("select", "nord")
            until("failed: selection could not be saved")
            assert (state_dir / "theme").read_text() == "dracula\n"
        finally:
            state_dir.chmod(0o700)

        # Use the real CLI/renderer for reset and same-theme reselection. Route
        # its IPC into this disposable offscreen shell, never the user's shell.
        renderer.write_text("#!/bin/sh\nexec " + shlex.join([sys.executable, str(source / "scripts/theme")]) + ' "$@"\n')
        ipc = root / "bin/qs"
        ipc.write_text("#!/bin/sh\nexec " + shlex.join([quickshell, "-p", str(root)]) + ' "$@"\n')
        ipc.chmod(0o755)
        yazi = root / "bin/ya"
        yazi.write_text("#!/bin/sh\nexit 0\n")
        yazi.chmod(0o755)

        def cli(*args):
            result = subprocess.run([sys.executable, str(source / "scripts/theme"), *args],
                                    env=env, capture_output=True, text=True, timeout=15)
            assert result.returncode == 0, (result.stdout, result.stderr)
            return result

        cli("theme", "nord")
        until("applied: nord")
        for _ in range(2):
            cli("reset", "kitty")
            assert (state_dir / "theme").read_text() == "nord\n"
            assert json.loads((current / "palette.json").read_text())["themeId"] == "nord"
            cli("reset")
            until("applied: catppuccin-mocha")
            assert not (state_dir / "theme").exists()
            cli("theme", "nord")
            until("applied: nord")
            assert (state_dir / "theme").read_text() == "nord\n"
            assert json.loads((current / "palette.json").read_text())["themeId"] == "nord"
    finally:
        shell.terminate()
        try:
            shell.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            shell.kill()
            shell.communicate()

print("live theme IPC checks passed")
