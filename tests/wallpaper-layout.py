#!/usr/bin/env python3
"""Observe Wallpaper's production bindings after coalesced output reports.
Run: python3 tests/wallpaper-layout.py . (requires qs on PATH).
Native anchored-size requests and Hyprland placement need a Wayland session.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
wallpaper = (source / "quickshell/modules/Wallpaper.qml").read_text()
# Keep the production bindings intact; substitute only native inputs and the
# PanelWindow boundary. Native polish compares the final implicit QSize, not
# the number of synchronous setters preceding it.
origin = re.search(r"            screen: modelData\n(.*?)            color:", wallpaper, re.S)
assert origin, "Wallpaper must retain its per-output size bindings"
# The size nudge is safe only while the compositor still owns both dimensions.
anchors = re.search(r"anchors \{([^}]+)\}", wallpaper).group(1)
assert all(re.search(rf"\b{edge}: true\b", anchors) for edge in ("top", "bottom", "left", "right"))
assert 'exclusionMode: ExclusionMode.Ignore' in wallpaper
assert 'WlrLayershell.keyboardFocus: WlrKeyboardFocus.None' in wallpaper
qml = """import QtQuick
import QtTest
import Quickshell
ShellRoot {
    QtObject { id: external; property int x: 1920; property int y: 0; property int width: 5120 }
    QtObject { id: other; property int x: 7040; property int y: 0 }
    component Surface: QtObject {
        required property var modelData
        property int implicitWidth
        property int implicitHeight
ORIGIN
    }
    Surface { id: wallpaper; modelData: external }
    Surface { id: unaffected; modelData: other }
    TestCase {
        id: checks
        name: "WallpaperOutputRelocation"
        when: false
        function observe(surface) {
            let observed
            Qt.callLater(() => observed = Qt.size(surface.implicitWidth, surface.implicitHeight))
            tryVerify(() => observed !== undefined)
            return observed
        }
        function changed(previous, current) {
            if (previous.width === current.width && previous.height === current.height)
                throw new Error("Changed final origin lost refresh at deferred size comparison: " + previous + " == " + current)
        }
        function test_relocation() {
            const initial = observe(wallpaper)
            const otherInitial = observe(unaffected)
            // Disable/removal may precede the actual reported output move.
            external.x = 1920
            external.width = 2560
            compare(observe(wallpaper), initial)
            // Two distinct reports before one deferred observation must not cancel.
            external.x = 0
            external.y = -1440
            const coalesced = observe(wallpaper)
            changed(initial, coalesced)
            compare(observe(unaffected), otherInitial)
            external.x = 0
            external.width = 5120
            compare(observe(wallpaper), coalesced)
            // Same-axis batching also ends at a different output origin.
            external.x = 1920
            external.x = 3840
            const horizontal = observe(wallpaper)
            changed(coalesced, horizontal)
            external.y = 0
            const vertical = observe(wallpaper)
            changed(horizontal, vertical)
            external.x = -1920
            const negative = observe(wallpaper)
            changed(vertical, negative)
            external.x = 1920
            const reopened = observe(wallpaper)
            changed(negative, reopened)
            external.x = 0
            const closed = observe(wallpaper)
            changed(reopened, closed)
            wait(30)
            compare(observe(wallpaper), closed, "No self-generated size-state changes")
            compare(observe(unaffected), otherInitial)
            console.log("WALLPAPER_LAYOUT_PASSED")
            Qt.quit()
        }
    }
    Component.onCompleted: Qt.callLater(() => {
        try { checks.test_relocation() }
        catch (error) { console.error(error); Qt.exit(1) }
    })
}
""".replace("ORIGIN", origin.group(1))
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "shell.qml").write_text(qml)
    runtime = root / "runtime"
    runtime.mkdir(mode=0o700)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
               XDG_RUNTIME_DIR=str(runtime), XDG_CACHE_HOME=str(root / "cache"))
    result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                            capture_output=True, text=True, timeout=10)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and "WALLPAPER_LAYOUT_PASSED" in output, output
    assert not re.search(r"ReferenceError|TypeError|[Bb]inding loop|Unable to assign|FAIL!", output), output
print("wallpaper: deferred coalesced relocation, no-op geometry and per-output isolation pass")
