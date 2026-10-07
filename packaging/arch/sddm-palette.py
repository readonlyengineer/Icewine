#!/usr/bin/env python3
"""Generate the native SDDM palette using the existing template and theme data."""
import json
from pathlib import Path

assets = Path(__file__).resolve().parents[2] / "theme/assets"
palettes = {path.stem: json.loads(path.read_text()) for path in sorted((assets / "themes").glob("*.json"))}
text = (assets / "templates/Palette.qml.in").read_text()
text = text.replace("import QtQuick\n", "import QtQuick\nimport QtCore\n")
text = text.replace("QtObject {\n", '''QtObject {
    property Settings themeSettings: Settings {
        location: "file:///var/lib/icewine/sddm/theme.ini"
    }
    readonly property var palettes: (''' + json.dumps(palettes) + ''')
    readonly property string themeId: themeSettings.value("theme", "")
    readonly property var palette: Object.prototype.hasOwnProperty.call(palettes, themeId)
        ? palettes[themeId] : palettes["tokyo-night"]
''')
text = text.replace('"@appearance@"', 'palette.appearance')
for name in palettes["tokyo-night"]:
    text = text.replace('"#@' + name + '@"', '"#" + palette.' + name)
assert "@" not in text, "unexpanded SDDM palette token"
print(text, end="")
