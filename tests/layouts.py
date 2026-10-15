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
    import json
    import re
    qml = '''import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import "icewine/modules/topbar" as Bar
import "theme" as Theme
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
        color: Theme.Palette.backgroundDark
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
    function checkPreviews() {
        const names = ["Scrolling", "Dwindle", "Master", "Monocle"]
        for (const width of [380, 320]) {
            window.width = width
            keys.wait(20)
            for (const state of ["unselected", "selected", "focused", "disabled"]) {
                const signatures = []
                for (const name of names) {
                    const button = root.named(picker, name + " layout")
                    compositor.layoutStatus = {effective: state === "unselected" ? "default" : name.toLowerCase()}
                    compositor.layoutPending = state === "disabled"
                    picker.forceActiveFocus()
                    if (state === "focused") button.forceActiveFocus()
                    keys.wait(20)
                    const label = width + "/" + state + "/" + name
                    const preview = button.contentItem.children[0]
                    if (!preview.visible || preview.opacity <= 0 || preview.width <= 8 || preview.height <= 0)
                        throw new Error(label + ": invisible preview")
                    const origin = preview.mapToItem(button, 0, 0)
                    if (origin.x < 0 || origin.y < 0 || origin.x + preview.width > button.width + 0.5
                            || origin.y + preview.height > button.height + 0.5)
                        throw new Error(label + ": preview outside button")
                    const panes = Array.from(preview.children).filter(child => child.border !== undefined)
                    if (panes.length !== (name === "Dwindle" ? 4 : 3))
                        throw new Error(label + ": missing window panes")
                    for (const pane of panes) {
                        if (!pane.visible || pane.opacity <= 0 || pane.width < 4 || pane.height < 4
                                || pane.x < 0 || pane.y < 0 || pane.x + pane.width > preview.width + 0.5
                                || pane.y + pane.height > preview.height + 0.5)
                            throw new Error(label + ": vanished or clipped pane " + [pane.x, pane.y, pane.width, pane.height])
                    }
                    // Capture the real scene: positive geometry alone cannot detect transparent/missing borders.
                    // QtTest's offscreen grab of a nested item crops from the window origin.
                    const image = keys.grabImage(window.contentItem)
                    const offset = preview.mapToItem(window.contentItem, 0, 0)
                    const signature = Array(16 * 12).fill(0)
                    let ink = 0
                    for (let y = 0; y < Math.floor(preview.height); ++y) {
                        for (let x = 0; x < Math.floor(preview.width); ++x) {
                            const pixel = image.pixel(Math.round(offset.x) + x, Math.round(offset.y) + y)
                            const surface = Theme.Palette.surface
                            if (pixel.a > 0.5 && Math.max(Math.abs(pixel.r - surface.r),
                                    Math.abs(pixel.g - surface.g), Math.abs(pixel.b - surface.b)) > 0.05) {
                                ++ink
                                signature[Math.floor(y * 12 / preview.height) * 16 + Math.floor(x * 16 / preview.width)] = 1
                            }
                        }
                    }
                    if (ink < preview.width) throw new Error(label + ": preview has too little visible ink: " + ink)
                    if (signatures.includes(signature.join("")))
                        throw new Error(label + ": indistinguishable preview")
                    signatures.push(signature.join(""))
                }
            }
        }
        compositor.layoutPending = false
        compositor.layoutStatus = {effective: "scrolling", default: "master", override: ""}
        window.width = 380
    }
    Timer {
        interval: 250; running: true
        onTriggered: {
            try {
                window.requestActivate()
                keys.tryCompare(window, "active", true)
                root.checkPreviews()
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
            } catch (error) { console.error(error); Qt.exit(1) }
        }
    }
}'''
    for theme_name in ["tokyo-night", "gruvbox-light"]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "icewine").mkdir()
            (root / "icewine/modules").symlink_to(source / "quickshell/modules")
            (root / "icewine/theme").symlink_to(root / "theme")
            (root / "theme").mkdir()
            palette = (source / "theme/assets/templates/Palette.qml.in").read_text()
            colours = json.loads((source / "theme/assets/themes" / (theme_name + ".json")).read_text())
            (root / "theme/Palette.qml").write_text(re.sub(r"@(\w+)@", lambda match: colours[match[1]], palette))
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
            assert not re.search(r"ReferenceError|TypeError|Binding loop|Unable to assign", output), output
    print("PASS actual QML picker: four rendered previews at 380/320px, dark/light, unselected/selected/focused/disabled; keyboard choice/reset, external state, pending/unavailable")
