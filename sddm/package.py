#!/usr/bin/env python3
"""Package the installed upstream Breeze with Icewine's public colour fallback."""
import os
from pathlib import Path
import runpy
import shutil
import sys

upstream, theme, colours, renderer, assets = map(Path, sys.argv[1:6])
selected = sys.argv[6] if len(sys.argv) > 6 else ""
shutil.copytree(upstream, theme, dirs_exist_ok=True)
theme.chmod(0o755)
main = theme / "Main.qml"
original = main.read_text()
needle = "sceneBackgroundColor: config.color"
if original.count(needle) != 1:
    raise ValueError("upstream Breeze background contract changed")
main.chmod(0o644)
main.write_text(original.replace(needle, "sceneBackgroundColor: Kirigami.Theme.backgroundColor"))
login = theme / "Login.qml"
original_login = login.read_text()
changes = {
    "loginRequest(username, password);": "loginRequest(username, password);\n        passwordBox.clear();",
    "passwordBox.selectAll()": "passwordBox.clear()",
}
for before, after in changes.items():
    if original_login.count(before) != 1:
        raise ValueError("upstream Breeze password clearing contract changed")
    original_login = original_login.replace(before, after)
login.chmod(0o644)
login.write_text(original_login)
settings = theme / "theme.conf.user"
if settings.exists():
    settings.chmod(0o644)
settings.write_text("[General]\ntype=color\niconTheme=breeze\n")
os.environ["ICEWINE_THEME_ASSETS"] = str(assets)
render = runpy.run_path(str(renderer))
files = render["render_theme"](assets, assets / "themes" / ((selected or render["DEFAULT"]) + ".json"))
colours.parent.mkdir(parents=True, exist_ok=True)
colours.write_text(files["kdeglobals"])
