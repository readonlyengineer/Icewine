"""Check the packaged upstream reader and CLI against Icewine's rendered input."""
import json
import os
import subprocess
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text())
assert manifest["name"] == "pywalfox" and manifest["type"] == "stdio"
assert manifest["allowed_extensions"] == ["pywalfox@frewacom.org"]
config = Path(os.environ["XDG_CONFIG_HOME"])
os.environ["XDG_CACHE_HOME"] = str(config / "icewine")
from pywalfox.fetcher import get_pywal_colors

success, fetched, error = get_pywal_colors()
assert success, error
palette = json.loads((config / "icewine/current/palette.json").read_text())
assert len(fetched["colors"]) == 16 and fetched["wallpaper"] == ""
assert fetched["colors"][0] == "#" + palette["background"]
assert fetched["colors"][8] == "#" + palette["surface"]
assert fetched["colors"][12] == "#" + palette["primary"]
assert fetched["colors"][15] == "#" + palette["foreground"]
# The wrapper must override a foreign wal cache and leave it untouched.
foreign_cache = config.parent / "foreign-cache"
foreign_input = foreign_cache / "wal/colors.json"
foreign_input.parent.mkdir(parents=True)
foreign_input.write_text("unrelated wal input")
environment = dict(os.environ, XDG_CACHE_HOME=str(foreign_cache))
subprocess.run([manifest["path"], "dark"], env=environment, check=True)
assert json.loads((config / "pywalfox/config.json").read_text())["theme_mode"] == "dark"
subprocess.run([manifest["path"], "update"], env=environment, check=True)
assert foreign_input.read_text() == "unrelated wal input"
print("packaged upstream Pywalfox input/CLI checks passed")
