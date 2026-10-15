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
    environment = dict(os.environ, selectedTheme="dracula")
    environment.pop("ICEWINE_THEME_ASSETS", None)
    subprocess.run([sys.executable, "-c", code, str(standalone), str(assets), str(output)],
                   env=environment, check=True, capture_output=True, text=True)
    config = configparser.ConfigParser()
    config.read(output)
    palette = json.loads((assets / "themes" / "dracula.json").read_text())
    assert config["Colors:Complementary"]["BackgroundNormal"] == "#" + palette["background"]

print("PASS: standalone fallback packaging renders explicit Dracula with no inherited assets env")
