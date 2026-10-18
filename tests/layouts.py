#!/usr/bin/env python3
"""Real layout CLI and Lua preferences, isolated from the live compositor."""
import importlib.machinery
import io
import os
import shutil
from pathlib import Path
from qml_fixture import theme_fixture
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

# Exercise the picker and shared host against the real adapter, with native IPC replaced.
if "--qml" in sys.argv:
    import json
    import re
    qml = '''import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import "icewine/adapters" as Adapters
import "icewine/modules/topbar" as Bar
import "theme" as Theme
ShellRoot {
    id: root
    property var calls: []
    property int queries: 0
    property bool hostOwnsLayout: false
    Adapters.Hyprland { id: backend }
    Connections {
        target: backend.layoutProcess
        function onRunningChanged() { if (backend.layoutProcess.running) ++root.queries }
    }
    Binding {
        target: backend
        property: "layoutActive"
        value: host.layoutActive
        when: root.hostOwnsLayout
    }
    function checkHostedRefresh() {
        keys.compare(backend.layoutStatus, null)
        keys.compare(backend.layoutAvailable, false)
        const before = root.queries
        root.hostOwnsLayout = true
        host.shown = true
        keys.tryCompare(host, "layoutActive", true)
        keys.tryCompare(backend, "layoutAvailable", true)
        keys.compare(root.queries, before + 1)
        // Activity must stay true while a real action disables picker availability.
        backend.selectLayout("master")
        keys.tryCompare(backend, "layoutPending", true)
        keys.compare(host.layoutActive, true)
        keys.tryCompare(backend, "layoutPending", false)
        keys.tryCompare(root, "queries", before + 3)
        keys.tryCompare(backend.layoutProcess, "running", false)
        keys.compare(backend.layoutAvailable, true)
        keys.compare(host.layoutActive, true)
        host.shown = false
        keys.tryCompare(host, "layoutActive", false)
        keys.compare(backend.layoutStatus, null)
        console.log("LAYOUT_HOST_PASSED")
    }
    function checkRefresh() {
        keys.wait(850)
        backend.layoutWorkspaceId = 2
        keys.wait(30)
        if (root.queries !== 0) throw new Error("Disabled adapter queried at startup or focus change")
        backend.layoutActive = true
        backend.layoutWorkspaceId = 3
        backend.layoutWorkspaceId = 4
        keys.tryCompare(backend, "layoutAvailable", true)
        if (backend.layoutStatus.workspace !== 4 || root.queries !== 2)
            throw new Error("In-flight workspace refresh was lost or not coalesced")
        backend.selectLayout("master")
        keys.tryCompare(backend, "layoutPending", false)
        keys.tryCompare(root, "queries", 4)
        keys.tryCompare(backend.layoutProcess, "running", false)
        // Close and reopen during a same-workspace query; discard its old result.
        backend.refreshLayout()
        backend.layoutActive = false
        backend.layoutActive = true
        keys.tryCompare(root, "queries", 6)
        keys.tryCompare(backend, "layoutAvailable", true)
        backend.refreshLayout()
        backend.layoutActive = false
        keys.tryCompare(backend.layoutProcess, "running", false)
        const closedQueries = root.queries
        backend.layoutWorkspaceId = 5
        keys.wait(850)
        if (root.queries !== closedQueries || backend.layoutStatus !== null)
            throw new Error("Closed adapter published or restarted status queries")
        console.log("LAYOUT_REFRESH_PASSED")
    }
    QtObject {
        id: compositor
        property int layoutWorkspaceId: 1
        property bool layoutAvailable: true
        property bool layoutPending: false
        property string layoutError: ""
        property string layoutUnavailable: ""
        property var layoutStatus: ({workspace: 1, effective: "scrolling", default: "master", override: "", autofullscreen: false})
        function selectLayout(layout) { root.calls.push([layoutWorkspaceId, layout]) }
        function selectAutofullscreen(enabled) { root.calls.push([layoutWorkspaceId, enabled]) }
    }
    Window {
        id: window
        visible: true
        width: 380; height: 300
        color: Theme.Palette.backgroundDark
        Bar.LayoutPicker { id: picker; width: parent.width; compositor: compositor }
        Bar.StatusPopout {
            id: host
            compositor: backend
            currentPage: "layout"
            cardStacks: [{id: "layout", modules: ["layout"]}]
            shown: false
            anchors.fill: parent
        }
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
                root.checkRefresh()
                root.checkHostedRefresh()
                root.checkPreviews()
                const button = root.named(picker, "Dwindle layout")
                if (!button || !button.enabled) throw new Error("Missing enabled choice")
                button.forceActiveFocus()
                keys.keyClick(Qt.Key_Return)
                const toggle = root.named(picker, "Autofullscreen")
                if (!toggle) throw new Error("Missing autofullscreen control")
                toggle.forceActiveFocus()
                keys.keyClick(Qt.Key_Space)
                if (JSON.stringify(root.calls) !== JSON.stringify([[1, "dwindle"], [1, true]]))
                    throw new Error("Keyboard selection/toggle targeted the wrong action")
                compositor.layoutWorkspaceId = 2
                compositor.layoutStatus = ({workspace: 2, effective: "monocle", default: "master", override: "monocle", autofullscreen: false})
                const heading = picker.children.find(child => child.text?.startsWith("Workspace "))
                if (!heading) throw new Error("Missing workspace layout heading")
                if (heading.text.split(" · ")[0] !== "Workspace 2") throw new Error("Stale workspace heading")
                const selectedPreview = root.named(picker, "Monocle layout").contentItem.children[0]
                keys.compare(selectedPreview.children[0].border.color, Theme.Palette.primary)
                compositor.layoutPending = true
                if (toggle.enabled || picker.initialFocus.enabled || root.named(picker, "Master layout").enabled) throw new Error("Pending actions enabled")
                compositor.layoutPending = false
                compositor.layoutAvailable = false
                compositor.layoutUnavailable = "Fixture unavailable"
                if (toggle.enabled || picker.initialFocus.enabled) throw new Error("Unavailable choices enabled")
                if (!picker.children.some(child => child.visible && child.text === "Fixture unavailable"))
                    throw new Error("Missing unavailable feedback")
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
            shutil.copytree(source / "quickshell/config", root / "config")
            (root / "icewine/modules").symlink_to(source / "quickshell/modules")
            (root / "icewine/theme").symlink_to(root / "theme")
            # Replace only the native focus input; execute the real adapter/Process lifecycle.
            (root / "icewine/adapters").mkdir()
            adapter = (source / "quickshell/adapters/Hyprland.qml").read_text()
            focus_binding = "readonly property int layoutWorkspaceId: focusedWorkspaceId()"
            assert adapter.count(focus_binding) == 1
            (root / "icewine/adapters/Hyprland.qml").write_text(
                adapter.replace(focus_binding, "property int layoutWorkspaceId: 1"))
            (root / "bin").mkdir()
            cli = root / "bin/hyprctl"
            cli.write_text("#!" + sys.executable + "\n" +
                           "import json,re,sys,time\ntime.sleep(0.1)\n" +
                           "if sys.argv[1] == 'eval': print('ok')\n" +
                           "else:\n workspace=int(re.search(r'status\\((-?\\d+)\\)', sys.argv[2])[1])\n" +
                           " print(json.dumps(dict(workspace=workspace,identity='31',effective='master'," +
                           "default='scrolling',override='',autofullscreen=False)))\n")
            cli.chmod(0o755)
            fixture_config = theme_fixture(source, root, theme_name)
            (root / "shell.qml").write_text(qml)
            env = os.environ | {"QT_QPA_PLATFORM": "offscreen", "XDG_CACHE_HOME": str(root / "cache"),
                                "XDG_RUNTIME_DIR": str(root / "runtime"), "XDG_CONFIG_HOME": fixture_config,
                                "XDG_STATE_HOME": str(root / "state"), "ICEWINE_WIDGET_POLICY": "{}",
                                "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(root / "no-bus"),
                                "DBUS_SYSTEM_BUS_ADDRESS": "unix:path=" + str(root / "no-system-bus"),
                                "HYPRLAND_INSTANCE_SIGNATURE": "", "WAYLAND_DISPLAY": "",
                                "PATH": str(root / "bin") + os.pathsep + os.environ["PATH"]}
            result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                                    capture_output=True, text=True, timeout=10)
            output = result.stdout + result.stderr
            assert result.returncode == 0 and "LAYOUT_PICKER_PASSED" in output and "LAYOUT_REFRESH_PASSED" in output and "LAYOUT_HOST_PASSED" in output, output
            assert not re.search(r"ReferenceError|TypeError|Binding loop|Unable to assign", output), output
    print("PASS actual QML adapter: disabled startup, coalesced focus, action completion, reopen and hidden lifetime; shared host cold status and pending action; picker: four rendered previews at 380/320px, dark/light, unselected/selected/focused/disabled; keyboard choice/toggle, external state, pending/unavailable")
