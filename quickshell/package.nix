{ quickshell, qt6, kdePackages, symlinkJoin, writeShellScriptBin }:
let
  runtime = quickshell.overrideAttrs (old: {
    buildInputs = old.buildInputs ++ (with kdePackages; [
      libplasma plasma-workspace kirigami ki18n breeze breeze-icons plasma-integration qqc2-breeze-style
    ]) ++ [ qt6.qtvirtualkeyboard ];
    qtWrapperArgs = (old.qtWrapperArgs or [ ]) ++ [
      "--set" "KIRIGAMI_PLATFORM_THEME" "org.kde.breeze"
    ];
  });
in symlinkJoin {
  name = "icewine-quickshell";
  paths = [ (writeShellScriptBin "qs" ''
    # Apply Breeze's supported KConfig setting only to this opted-out process.
    if [ "''${ICEWINE_THEME_TRANSITION:-}" = off ]; then
      export XDG_CONFIG_DIRS="${./no-animations}:''${XDG_CONFIG_DIRS:-/etc/xdg}"
    fi
    exec ${runtime}/bin/qs "$@"
  '') runtime ];
}
