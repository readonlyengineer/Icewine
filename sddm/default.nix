{ runCommand, writeText }:
let
  palette = builtins.fromJSON (builtins.readFile ../theme/assets/themes/tokyo-night.json);
  paletteQml = writeText "icewine-palette.qml" (
    builtins.replaceStrings
      (map (name: "@${name}@") (builtins.attrNames palette))
      (builtins.attrValues palette)
      (builtins.readFile ../theme/assets/templates/Palette.qml.in)
  );
in
runCommand "icewine-sddm-theme" { } ''
  theme="$out/share/sddm/themes/icewine"
  mkdir -p "$theme"/{modules,theme}
  cp ${./Main.qml} "$theme/Main.qml"
  cp ${./metadata.desktop} "$theme/metadata.desktop"
  cp ${../quickshell/modules/WinterScreen.qml} "$theme/modules/WinterScreen.qml"
  cp ${../quickshell/modules/WinterModel.js} "$theme/modules/WinterModel.js"
  cp ${paletteQml} "$theme/theme/Palette.qml"
  printf 'singleton Palette 1.0 Palette.qml\n' > "$theme/theme/qmldir"
''
