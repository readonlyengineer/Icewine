#!/usr/bin/env python3
"""Exercise the shared native/Nix Breeze packaging transformation and fallback."""
import configparser
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
assets = source / "theme/assets"
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    upstream = root / "upstream"
    upstream.mkdir()
    (upstream / "Main.qml").write_text("sceneBackgroundColor: config.color\n")
    (upstream / "Login.qml").write_text("native presentation\nloginRequest(username, password);\npasswordBox.selectAll()\n")
    for palette_file in sorted((assets / "themes").glob("*.json")):
        theme, output = root / palette_file.stem, root / palette_file.stem / "kdeglobals"
        subprocess.run([sys.executable, str(source / "sddm/package.py"), str(upstream),
                        str(theme), str(output), str(source / "scripts/theme"),
                        str(assets), palette_file.stem], check=True, capture_output=True, text=True)
        config = configparser.ConfigParser()
        config.read(output)
        palette = json.loads(palette_file.read_text())
        expected = "#ffffff" if palette["appearance"] == "light" else "#000000"
        assert config["Colors:Complementary"]["BackgroundNormal"] == expected, palette_file.stem
        assert config["Colors:Window"]["BackgroundNormal"] == "#" + palette["background"]
        assert "native presentation" in (theme / "Login.qml").read_text()
        assert (theme / "Login.qml").read_text().count("passwordBox.clear()") == 2
        assert "Kirigami.Theme.backgroundColor" in (theme / "Main.qml").read_text()
        assert "type=color" in (theme / "theme.conf.user").read_text()
    # An upstream contract change must fail packaging instead of shipping a
    # wallpaper/custom fallback after a silent failed replacement.
    (upstream / "Main.qml").write_text("changed upstream backdrop API\n")
    failed = subprocess.run([sys.executable, str(source / "sddm/package.py"), str(upstream),
                            str(root / "changed"), str(root / "changed/kdeglobals"),
                            str(source / "scripts/theme"), str(assets)], capture_output=True, text=True)
    assert failed.returncode != 0 and "background contract changed" in failed.stderr
print("PASS: shared Breeze packaging preserves upstream form, renders every fallback and rejects drift")
