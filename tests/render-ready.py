#!/usr/bin/env python3
"""Exercise the real frame-swapped readiness component offscreen."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
qml = """import QtQuick
import Quickshell
import "modules" as Modules
ShellRoot {
    Window {
        id: window
        visible: true
        width: 32; height: 32
        Rectangle { anchors.fill: parent; color: "black" }
        Modules.RenderReady {
            item: window.contentItem
            onReady: { console.log("RENDER_READY_PASSED"); Qt.quit() }
        }
    }
}
"""

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "modules").symlink_to(source / "quickshell/modules")
    (root / "shell.qml").write_text(qml)
    runtime = root / "runtime"
    runtime.mkdir(mode=0o700)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
               XDG_CACHE_HOME=str(root / "cache"), XDG_RUNTIME_DIR=str(runtime))
    result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                            capture_output=True, text=True, timeout=10)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and "RENDER_READY_PASSED" in output, output
    assert "Failed to load configuration" not in output, output
    print("render readiness check passed")
