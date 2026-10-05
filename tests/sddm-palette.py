#!/usr/bin/env python3
"""Exercise the packaged SDDM palette selector with a temporary data path."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile


palette = Path(sys.argv[1]).read_text(encoding="utf-8")
qml = sys.argv[2]
imports = sys.argv[3]
published = "file:///var/lib/icewine/sddm/theme.ini"
assert palette.count(published) == 1

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "theme").mkdir()
    (root / "runtime").mkdir(mode=0o700)
    selection = root / "theme.ini"
    (root / "theme/Palette.qml").write_text(
        palette.replace(published, selection.as_uri()), encoding="utf-8")
    (root / "theme/qmldir").write_text("singleton Palette 1.0 Palette.qml\n")
    environment = dict(os.environ, HOME=str(root), XDG_RUNTIME_DIR=str(root / "runtime"),
                       QT_QPA_PLATFORM="offscreen")

    for theme, background, dark in [
        (None, "#1a1b26", "true"),
        ("gruvbox-light", "#f2e5bc", "false"),
        ("__proto__", "#1a1b26", "true"),
        ("unreadable", "#1a1b26", "true"),
    ]:
        if theme is None:
            selection.unlink(missing_ok=True)
        elif theme == "unreadable":
            selection.unlink()
            selection.mkdir()
        else:
            selection.write_text(f"[General]\ntheme={theme}\n", encoding="utf-8")
        (root / "Main.qml").write_text(f'''import QtQuick
import "theme" as Theme
Window {{
    visible: true
    Component.onCompleted: {{
        if (Theme.Palette.background.toString().toLowerCase() !== "{background}"
                || Theme.Palette.dark !== {dark})
            throw new Error("wrong SDDM palette")
        Qt.quit()
    }}
}}
''', encoding="utf-8")
        result = subprocess.run([qml, "-I", imports, str(root / "Main.qml")],
                                env=environment, capture_output=True, text=True, timeout=5)
        assert result.returncode == 0, (theme, result.stdout, result.stderr)

print("PASS: SDDM packaged fallback, light palette, invalid and unreadable IDs")
