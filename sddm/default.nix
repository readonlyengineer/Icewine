{ runCommand, kdePackages, python3, theme ? null }:
# Use KDE's greeter with a solid, palette-driven backdrop.
runCommand "icewine-breeze-sddm-theme" {
  selectedTheme = if theme == null then "" else theme;
} ''
  theme="$out/share/sddm/themes/breeze"
  mkdir -p "$theme"
  cp -r ${kdePackages.plasma-desktop}/share/sddm/themes/breeze/. "$theme/"
  chmod -R u+w "$theme"
  substituteInPlace "$theme/Main.qml" --replace-fail \
    'sceneBackgroundColor: config.color' \
    'sceneBackgroundColor: Kirigami.Theme.backgroundColor'
  mkdir -p "$out/share/icewine/sddm"
  ${python3}/bin/python3 - ${../scripts/theme} ${../theme/assets} "$out/share/icewine/sddm/kdeglobals" <<'PYTHON'
import os, runpy, sys
from pathlib import Path
os.environ["ICEWINE_THEME_ASSETS"] = sys.argv[2]
renderer = runpy.run_path(sys.argv[1])
assets = Path(sys.argv[2])
selected = os.environ["selectedTheme"] or renderer["DEFAULT"]
files = renderer["render_theme"](assets, assets / "themes" / (selected + ".json"))
Path(sys.argv[3]).write_text(files["kdeglobals"])
PYTHON
  cat > "$theme/theme.conf.user" <<'EOF'
[General]
type=color
iconTheme=breeze
EOF
''
