{ quickshell, qt6, symlinkJoin, makeWrapper }:
symlinkJoin {
  name = "icewine-${quickshell.name}";
  inherit (quickshell) pname version meta;
  passthru = quickshell.passthru or { };
  paths = [ quickshell ];
  nativeBuildInputs = [ makeWrapper ];
  postBuild = ''
    # Keep nixpkgs' Qt wrapper; only add the matching runtime keyboard modules.
    for program in qs quickshell; do
      rm "$out/bin/$program"
      makeWrapper "${quickshell}/bin/$program" "$out/bin/$program" \
        --prefix QT_PLUGIN_PATH : "${qt6.qtvirtualkeyboard}/lib/qt-6/plugins" \
        --prefix NIXPKGS_QT6_QML_IMPORT_PATH : "${qt6.qtvirtualkeyboard}/lib/qt-6/qml"
    done
  '';
}
