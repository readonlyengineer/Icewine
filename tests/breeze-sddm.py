#!/usr/bin/env python3
"""Check packaged stock Breeze and native KDE colours with fixture public paths.

Run by checks.sddm with the actual module-configured Qt runtime and greeter.
The native wrapper hook supplies fixture config paths; upstream QML is intact.
"""
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import tempfile

source, package, qml, greeter, config_root, redirect = map(Path, sys.argv[1:])
renderer = runpy.run_path(str(source / "scripts/theme"))
assets = source / "theme/assets"
theme = package / "share/sddm/themes/breeze"

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    public, fallback = (config_root / name for name in ("public", "fallback"))
    runtime = root / "runtime"
    for path in (public, fallback, runtime):
        path.mkdir(mode=0o755 if path != runtime else 0o700)
    shutil.copyfile(package / "share/icewine/sddm/kdeglobals", fallback / "kdeglobals")
    environment = dict(os.environ, HOME=str(root), XDG_RUNTIME_DIR=str(runtime),
                       QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QT_IM_MODULE="qtvirtualkeyboard",
                       QT_FORCE_STDERR_LOGGING="1",
                       ICEWINE_SDDM_KDEGLOBALS_FILE=str(public / "kdeglobals"))
    executables = (qml, greeter)
    # SDDM test mode still reads its session model from native configuration.
    sessions = root / "sessions"
    sessions.mkdir()
    (sessions / "fixture.desktop").write_text(
        f"[Desktop Entry]\nType=Application\nName=Fixture\nExec={sys.executable}\nTryExec={sys.executable}\n")
    config = root / "sddm.conf"
    config.write_text(f"[X11]\nSessionDir={sessions}\n[Wayland]\nSessionDir={sessions}\n")
    greeter_environment = dict(environment, LD_PRELOAD=str(redirect),
                               NIX_REDIRECTS=f"/etc/sddm.conf={config}")

    probe = root / "Palette.qml"
    probe.write_text('''import QtQuick
import QtQuick.Controls
import QtQuick.VirtualKeyboard
import org.kde.kirigami as Kirigami
Window {
    visible: true
    Item { id: complementary; Kirigami.Theme.inherit: false
        Kirigami.Theme.colorSet: Kirigami.Theme.Complementary }
    Item { id: view; Kirigami.Theme.inherit: false
        Kirigami.Theme.colorSet: Kirigami.Theme.View }
    Item { id: selection; Kirigami.Theme.inherit: false
        Kirigami.Theme.colorSet: Kirigami.Theme.Selection }
    Button { id: button; text: "Login" }
    InputPanel { id: keyboard }
    Timer { interval: 300; running: true; onTriggered: {
        console.log("PALETTE=" + JSON.stringify({
            background: complementary.Kirigami.Theme.backgroundColor.toString(),
            foreground: complementary.Kirigami.Theme.textColor.toString(),
            view: view.Kirigami.Theme.backgroundColor.toString(),
            button: button.Kirigami.Theme.backgroundColor.toString(),
            selection: selection.Kirigami.Theme.backgroundColor.toString(),
            selectedText: selection.Kirigami.Theme.textColor.toString()
        })); Qt.quit();
    } }
}
''')
    default = renderer["DEFAULT"]
    for state, expected in (("missing", default), ("dracula", "dracula"),
                            ("gruvbox-light", "gruvbox-light"), ("invalid", default),
                            ("non-file", default)):
        colours = public / "kdeglobals"
        if colours.is_dir():
            colours.rmdir()
        else:
            colours.unlink(missing_ok=True)
        if state in ("dracula", "gruvbox-light"):
            files = renderer["render_theme"](assets, assets / "themes" / (state + ".json"))
            previous = os.environ.get("ICEWINE_SDDM_KDEGLOBALS_FILE")
            os.environ["ICEWINE_SDDM_KDEGLOBALS_FILE"] = str(colours)
            try:
                renderer["publish_sddm"](files, state)
            finally:
                if previous is None:
                    os.environ.pop("ICEWINE_SDDM_KDEGLOBALS_FILE", None)
                else:
                    os.environ["ICEWINE_SDDM_KDEGLOBALS_FILE"] = previous
        elif state == "invalid":
            colours.write_text("invalid palette state\n")
        elif state == "non-file":
            colours.mkdir()  # A directory cannot be read as a KConfig file.
        result = subprocess.run([str(executables[0]), str(probe)], env=environment,
                                capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        assert result.returncode == 0, (state, output)
        match = re.search(r"PALETTE=(\{[^\n]+\})", output)
        assert match, (state, output)
        actual = json.loads(match[1])
        palette = json.loads((assets / "themes" / (expected + ".json")).read_text())
        assert actual["background"].lower() == ("#ffffff" if palette["appearance"] == "light" else "#000000"), (state, actual)
        for role, key in (("foreground", "foreground"),
                          ("view", "backgroundDark"), ("button", "surface"), ("selection", "highlight")):
            assert actual[role].lower() == "#" + palette[key], (state, role, actual)
        # Selection.ForegroundNormal is the renderer's gtkAccentFg role.
        assert renderer["gtk_foreground"](palette["highlight"], palette["backgroundDark"]) == actual["selectedText"].lstrip("#"), (state, actual)

    # Smoke the stock greeter once; the probe above covers all palette states.
    colours.rmdir()  # The last probe left non-file public state; use missing state.
    process = subprocess.Popen([str(executables[1]), "--test-mode", "--theme", str(theme)],
                               env=greeter_environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        output, _ = process.communicate(timeout=3)
        raise AssertionError(("greeter exited early", process.returncode, output))
    except subprocess.TimeoutExpired:
        process.terminate()
        output, _ = process.communicate(timeout=5)
    assert not re.search(r'is not installed|Type .* unavailable|QQmlApplicationEngine failed|Cannot load library|Error loading QML|Fallback to embedded theme|ReferenceError|TypeError', output), output

print("PASS: stock Breeze startup/imports and native black/white backdrops and dark/light/missing/invalid/non-file palette")
