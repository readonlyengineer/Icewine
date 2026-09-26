{ runCommand, writeText }:
let
  palette = import ../theme/palette.nix;
  paletteQml = writeText "icewine-palette.qml" (
    builtins.replaceStrings
      (map (name: "@${name}@") (builtins.attrNames palette))
      (builtins.attrValues palette)
      (builtins.readFile ../quickshell/theme/Palette.qml.in)
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
