{ lib, runCommand, writeText, qt6 }:
let
  themeFiles = builtins.filter (name: lib.hasSuffix ".json" name)
    (builtins.attrNames (builtins.readDir ../theme/assets/themes));
  palettes = builtins.listToAttrs (map (file: {
    name = lib.removeSuffix ".json" file;
    value = builtins.fromJSON (builtins.readFile (../theme/assets/themes + "/${file}"));
  }) themeFiles);
  colors = [ "background" "backgroundDark" "surface" "selection" "border"
    "foreground" "foregroundDark" "muted" "highlight" "highlightDark"
    "secondaryHighlight" "tertiaryHighlight" "success" "warning" "caution"
    "error" "info" ];
  paletteQml = writeText "icewine-palette.qml" (
    builtins.replaceStrings
      ([ "import QtQuick\n" "QtObject {\n" "\"@appearance@\"" ]
        ++ map (name: "\"#@${name}@\"") colors)
      ([ "import QtQuick\nimport QtCore\n" ''
QtObject {
    property Settings themeSettings: Settings {
        location: "file:///var/lib/icewine/sddm/theme.ini"
    }
    readonly property var palettes: (${builtins.toJSON palettes})
    readonly property string themeId: themeSettings.value("theme", "")
    readonly property var palette: Object.prototype.hasOwnProperty.call(palettes, themeId)
        ? palettes[themeId] : palettes["tokyo-night"]
'' "palette.appearance" ] ++ map (name: "\"#\" + palette.${name}") colors)
      (builtins.readFile ../theme/assets/templates/Palette.qml.in)
  );
in
runCommand "icewine-sddm-theme" { } ''
  theme="$out/share/sddm/themes/icewine"
  mkdir -p "$theme"/{modules,theme}
  cp ${./Main.qml} "$theme/Main.qml"
  ln -s ${../theme/assets/flower-branch.png} "$theme/wallpaper.png"
  cp -r ${../quickshell/QtQuick} "$theme/QtQuick"
  chmod -R u+w "$theme/QtQuick"
  substituteInPlace "$theme/QtQuick/VirtualKeyboard/Styles/icewine/style.qml" \
    --replace-fail 'import qs.icewine.theme as Theme' 'import IcewineTheme as Theme'
  cp ${./metadata.desktop} "$theme/metadata.desktop"
  cp ${../quickshell/modules/AuthScreen.qml} "$theme/modules/AuthScreen.qml"
  cp ${../quickshell/modules/AuthModel.js} "$theme/modules/AuthModel.js"
  cp ${paletteQml} "$theme/theme/Palette.qml"
  mkdir -p "$theme/IcewineTheme" "$out/${qt6.qtbase.qtQmlPrefix}"
  printf 'module IcewineTheme\nsingleton Palette 1.0 ../theme/Palette.qml\n' > "$theme/IcewineTheme/qmldir"
  ln -s "$theme/QtQuick" "$theme/IcewineTheme" "$out/${qt6.qtbase.qtQmlPrefix}/"
''
