#!/usr/bin/env python3
"""Real layout CLI and Lua preferences, isolated from the live compositor."""
import importlib.machinery
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from unittest.mock import patch

source = Path(__file__).resolve().parent.parent
if "--qml" not in sys.argv:
    theme = importlib.machinery.SourceFileLoader("layout_theme", str(source / "scripts/theme")).load_module()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state = root / "state/icewine"
        state.mkdir(parents=True)
        (root / "runtime/hypr/fixture").mkdir(parents=True)
        env = {"XDG_STATE_HOME": str(state.parent), "XDG_RUNTIME_DIR": str(root / "runtime"),
               "HYPRLAND_INSTANCE_SIGNATURE": "", "HOME": str(root)}
        with patch.dict(os.environ, env), patch.object(theme.subprocess, "run") as ipc:
            def command(*args):
                out = io.StringIO()
                with redirect_stdout(out): theme.dispatch(["layout", *args])
                return out.getvalue()
            assert "Layout: scrolling" in command()
            assert "Pending:" in command("master") and (state / "layout").read_text() == "master\n"
            assert not ipc.called
            try: command("invalid")
            except ValueError: pass
            else: raise AssertionError("Accepted unsupported layout")
            assert (state / "layout").read_text() == "master\n"
            (state / "layout").write_text("invalid\n")
            assert "Layout: scrolling" in command()
            with patch.dict(os.environ, HYPRLAND_INSTANCE_SIGNATURE="fixture"):
                ipc.side_effect = subprocess.TimeoutExpired("hyprctl", 10)
                try: command("dwindle")
                except ValueError as error: assert "saved, but" in str(error)
                else: raise AssertionError("IPC failure accepted")
                assert "Layout: dwindle" in command()
                ipc.side_effect = None
                ipc.return_value = subprocess.CompletedProcess([], 0, stdout="error: unavailable\n")
                try: command("monocle")
                except ValueError as error: assert "saved, but" in str(error)
                else: raise AssertionError("Semantic IPC failure accepted")
                ipc.return_value.stdout = "ok\n"
                command("scrolling")
                assert ipc.call_args.args[0] == ["hyprctl", "reload"]
        subprocess.run(["lua", str(source / "hyprland/tests/layouts.lua"), str(root),
                        str(source / "hyprland/modules/Layouts.lua")],
                       env=os.environ | env | {"HYPRLAND_INSTANCE_SIGNATURE": "fixture"}, check=True)
    print("PASS layout CLI: persistent fallback, validation and saved-but-failed delivery")

# Reuse the existing controls.py offscreen QtTest pattern for the picker. This
# fixture has no metrics, DBus clients or compositor adapter/processes.
if "--qml" in sys.argv:
    import re
    qml = '''import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import "icewine/modules/topbar" as Bar
ShellRoot {
    id: root
    property var calls: []
    QtObject {
        id: compositor
        property int layoutWorkspaceId: 1
        property bool layoutAvailable: true
        property bool layoutPending: false
        property string layoutError: ""
        property string layoutUnavailable: ""
        property var layoutStatus: ({workspace: 1, effective: "scrolling", default: "master", override: ""})
        function selectLayout(layout) { root.calls.push([layoutWorkspaceId, layout]) }
    }
    Window {
        id: window
        visible: true
        width: 380; height: 300
        Bar.LayoutPicker { id: picker; width: parent.width; compositor: compositor }
        Bar.LayoutButton { id: trigger; y: 260; compositor: compositor }
        TestCase { id: keys; when: false }
    }
    function named(item, name) {
        if (item.Accessible?.name === name) return item
        for (const child of item.children ?? []) {
            const result = named(child, name)
            if (result) return result
        }
        return null
    }
    Timer {
        interval: 250; running: true
        onTriggered: {
            window.requestActivate()
            keys.tryCompare(window, "active", true)
            const button = root.named(picker, "Dwindle layout")
            if (!button || !button.enabled) throw new Error("Missing enabled choice")
            button.forceActiveFocus()
            keys.keyClick(Qt.Key_Return)
            picker.initialFocus.forceActiveFocus()
            keys.keyClick(Qt.Key_Space)
            if (JSON.stringify(root.calls) !== JSON.stringify([[1, "dwindle"], [1, "default"]]))
                throw new Error("Keyboard selection/reset targeted the wrong action")
            compositor.layoutWorkspaceId = 2
            compositor.layoutStatus = ({workspace: 2, effective: "monocle", default: "master", override: "monocle"})
            keys.tryCompare(trigger, "text", "▥ Monocle")
            compositor.layoutPending = true
            if (picker.initialFocus.enabled || root.named(picker, "Master layout").enabled) throw new Error("Pending actions enabled")
            compositor.layoutPending = false
            compositor.layoutAvailable = false
            compositor.layoutUnavailable = "Fixture unavailable"
            if (picker.initialFocus.enabled) throw new Error("Unavailable reset enabled")
            keys.tryCompare(trigger, "text", "▥ Layout")
            console.log("LAYOUT_PICKER_PASSED")
            Qt.quit()
        }
    }
}'''
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "icewine").mkdir()
        (root / "icewine/modules").symlink_to(source / "quickshell/modules")
        (root / "icewine/theme").symlink_to(root / "theme")
        (root / "theme").mkdir()
        palette = (source / "theme/assets/templates/Palette.qml.in").read_text()
        (root / "theme/Palette.qml").write_text(re.sub(r"@\w+@", "7aa2f7", palette))
        (root / "theme/qmldir").write_text("singleton Palette 1.0 Palette.qml\n")
        (root / "shell.qml").write_text(qml)
        env = os.environ | {"QT_QPA_PLATFORM": "offscreen", "XDG_CACHE_HOME": str(root / "cache"),
                            "XDG_RUNTIME_DIR": str(root / "runtime"),
                            "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(root / "no-bus"),
                            "DBUS_SYSTEM_BUS_ADDRESS": "unix:path=" + str(root / "no-system-bus")}
        result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                                capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        assert result.returncode == 0 and "LAYOUT_PICKER_PASSED" in output, output
    print("PASS actual QML picker: keyboard choice/reset, focused external state, pending and unavailable")
