{ quickshell, qt6 }:
quickshell.overrideAttrs (old: {
  buildInputs = old.buildInputs ++ [ qt6.qtvirtualkeyboard ];
})
