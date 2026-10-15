#!/usr/bin/env python3
"""Exercise the actual fallback packaging Python with a standalone store-like script."""
import configparser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
recipe = (source / "sddm/default.nix").read_text()
code = recipe.split("<<'PYTHON'\n", 1)[1].split("\nPYTHON", 1)[0]
assets = source / "theme/assets"
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    standalone = root / "store/hash-theme"
    standalone.parent.mkdir()
    shutil.copyfile(source / "scripts/theme", standalone)
    output = root / "kdeglobals"
    for palette_file in sorted((assets / "themes").glob("*.json")):
        environment = dict(os.environ, selectedTheme=palette_file.stem)
        environment.pop("ICEWINE_THEME_ASSETS", None)
        subprocess.run([sys.executable, "-c", code, str(standalone), str(assets), str(output)],
                       env=environment, check=True, capture_output=True, text=True)
        config = configparser.ConfigParser()
        config.read(output)
        palette = json.loads(palette_file.read_text())
        expected = "#ffffff" if palette["appearance"] == "light" else "#000000"
        assert config["Colors:Complementary"]["BackgroundNormal"] == expected, palette_file.stem
        assert config["Colors:Window"]["BackgroundNormal"] == "#" + palette["background"]

print("PASS: standalone fallback packaging renders black/white login backdrops for every theme")
