{ config, lib, pkgs, icewineNixpkgsLastModified ? 0, ... }:
let
  cfg = config.services.icewine;
  userHome = config.users.users.${cfg.user}.home;
  configHome = "${userHome}/.config";
  dataHome = "${userHome}/.local/share";
  stateHome = "${userHome}/.local/state";
  steamMask = pkgs.writeText "icewine-steam-mask.desktop" ''
    [Desktop Entry]
    Type=Application
    Name=Steam
    NoDisplay=true
    Hidden=true
  '';
  themeIds = map (name: lib.removeSuffix ".json" name)
    (builtins.filter (name: lib.hasSuffix ".json" name)
      (builtins.attrNames (builtins.readDir ../theme/assets/themes)));
  themeConsumers = builtins.fromJSON (builtins.readFile ../theme/assets/consumers.json);
  enabledConsumers = {
    gtk = cfg.gtk.enable;
    yazi = cfg.filemanager.enable;
    fastfetch = cfg.shellExtras.enable;
    starship = cfg.shellExtras.enable;
  };
  skippedThemeFiles = lib.concatLists (lib.mapAttrsToList (name: files:
    lib.optionals (!enabledConsumers.${name}) (builtins.attrNames files)
  ) themeConsumers);
  implementation = pkgs.runCommand "icewine-implementation" { } ''
    mkdir -p $out/quickshell/deck $out/hyprland/modules $out/kitty $out/uwsm $out/hypridle $out/gtk
    cp -r ${../quickshell}/adapters ${../quickshell}/modules ${../quickshell}/theme $out/quickshell/
    cp ${../quickshell}/deck/DeckOverlay.qml ${../quickshell}/deck/DeckMenu.js $out/quickshell/deck/
    cp ${../quickshell}/Desktop.qml ${../quickshell}/Handheld.qml $out/quickshell/
    cp ${../hyprland}/icewine.lua $out/hyprland/
    ${lib.optionalString cfg.handheld.enable ''
      chmod u+w $out/hyprland/icewine.lua
      printf '\nrequire("icewine.modules.Deck")\n' >> $out/hyprland/icewine.lua
    ''}
    cp ${../theme/assets/templates}/kitty-base.conf $out/kitty/defaults.conf
    cp ${../session}/env $out/uwsm/env
    cp ${../hypridle}/defaults.conf $out/hypridle/defaults.conf
    cp ${../gtk}/defaults.css $out/gtk/defaults.css
    ${lib.concatMapStringsSep "\n" (name:
      "cp ${../hyprland}/modules/${name}.lua $out/hyprland/modules/"
    ) [ "Baseline" "LookAndFeel" "WindowPolicy" "DefaultApps" "Docking" "Binds" ]}
    cp ${../hyprland}/deck/Deck.lua $out/hyprland/modules/
  '';
  defaults = pkgs.runCommand "icewine-default-files" { } ''
    mkdir -p $out/config/hypr/modules $out/config/quickshell/config $out/config/uwsm $out/data
    ${lib.optionalString (cfg.steam != "none" && cfg.gamescope.enable) ''
      mkdir -p $out/data/applications
      ln -s ${steamMask} $out/data/applications/steam.desktop
      ln -s ${steamMask} $out/data/applications/com.valvesoftware.Steam.desktop
    ''}
    install -Dm644 ${../theme/assets/flower-branch.png} $out/data/wallpapers/default.jpg
    cp ${../hyprland/hyprland.lua} $out/config/hypr/hyprland.lua
    printf '%s\n' '# Shared session defaults first; add your overrides below.' '. "''${XDG_CONFIG_HOME:-$HOME/.config}/uwsm/icewine/env"' > $out/config/uwsm/env
    ${lib.optionalString cfg.gtk.enable ''
      for version in 3 4; do
        mkdir -p $out/config/gtk-$version.0
        printf '%s\n' '@import url("icewine/defaults.css");' "@import url(\"../icewine/current/gtk$version.css\");" '/* Add your overrides below. */' > $out/config/gtk-$version.0/gtk.css
      done
      substituteInPlace $out/config/gtk-3.0/gtk.css --replace-fail gtk3.css gtk.css
    ''}
    ${lib.optionalString (cfg.terminal.enable) ''
      mkdir -p $out/config/kitty
      cp ${../kitty/kitty.conf} $out/config/kitty/kitty.conf
      ${lib.optionalString (builtins.hasAttr "kitty/host.conf" cfg.defaultFiles.config) "printf '%s\\n' 'include host.conf' >> $out/config/kitty/kitty.conf"}
    ''}
    ${lib.optionalString (cfg.filemanager.enable) ''
      mkdir -p $out/config/yazi/plugins/mount.yazi
      cp -r ${pkgs.yaziPlugins.mount}/. $out/config/yazi/plugins/mount.yazi/
    ''}
    cp ${if cfg.handheld.enable then ../quickshell/deck/shell.qml else ../quickshell/shell.qml} $out/config/quickshell/shell.qml
    cp ${../quickshell/config/qmldir} $out/config/quickshell/config/qmldir
    cp ${../quickshell/config/Settings.qml} $out/config/quickshell/config/Settings.qml
    chmod -R u+w $out
    ${lib.concatStringsSep "\n" (lib.mapAttrsToList (name: source:
      "mkdir -p $out/config/${lib.escapeShellArg (builtins.dirOf name)}; cp ${lib.escapeShellArg "${source}"} $out/config/${lib.escapeShellArg name}"
    ) cfg.defaultFiles.config)}
    ${lib.concatStringsSep "\n" (lib.mapAttrsToList (name: source:
      "mkdir -p $out/data/${lib.escapeShellArg (builtins.dirOf name)}; cp ${lib.escapeShellArg "${source}"} $out/data/${lib.escapeShellArg name}"
    ) cfg.defaultFiles.data)}
    ln -s ${implementation}/quickshell $out/config/quickshell/icewine
    ln -s ${implementation}/hyprland $out/config/hypr/icewine
    ${lib.optionalString cfg.idle.enable "ln -s ${implementation}/hypridle $out/config/hypr/hypridle-icewine"}
    ln -s ${implementation}/uwsm $out/config/uwsm/icewine
    ${lib.optionalString cfg.gtk.enable ''
      ln -s ${implementation}/gtk $out/config/gtk-3.0/icewine
      ln -s ${implementation}/gtk $out/config/gtk-4.0/icewine
    ''}
    ${lib.optionalString (cfg.terminal.enable) "ln -s ${implementation}/kitty $out/config/kitty/icewine"}
  '';
  quickshell = pkgs.callPackage ../quickshell/package.nix { };
  wallpaperSelector = pkgs.writeShellApplication {
    name = "icewine-wallpaper";
    runtimeInputs = [ pkgs.coreutils quickshell ];
    text = ''
      export ICEWINE_WALLPAPER_VALIDATOR=${../quickshell/modules}/WallpaperValidator.qml
      export ICEWINE_WALLPAPER_DATA_HOME=''${ICEWINE_WALLPAPER_DATA_HOME:-''${XDG_DATA_HOME:-${dataHome}}}
      ${builtins.readFile ../scripts/wallpaper}
    '';
  };
  themeCli = pkgs.writeShellApplication {
    name = "icewine-theme";
    runtimeInputs = [ pkgs.python3 pkgs.systemd pkgs.glib quickshell ]
      ++ lib.optional cfg.desktop.enable pkgs.hyprland
      ++ lib.optional (cfg.terminal.enable) pkgs.kitty
      ++ lib.optional (cfg.filemanager.enable) pkgs.yazi
      ++ lib.optional config.services.flatpak.enable pkgs.flatpak;
    text = ''
      export XDG_DATA_DIRS="${pkgs.gsettings-desktop-schemas}/share/gsettings-schemas/${pkgs.gsettings-desktop-schemas.name}:''${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
      export ICEWINE_GTK_ENABLE=${if cfg.gtk.enable then "true" else "false"}
      export ICEWINE_THEME_ASSETS=${../theme/assets}
      ${lib.optionalString cfg.login.enable "export ICEWINE_SDDM_THEME_FILE=/var/lib/icewine/sddm/theme.ini"}
      export ICEWINE_DEFAULT_FILES=${defaults}
      export ICEWINE_THEME_POLICY=${lib.escapeShellArg (if cfg.theme == null then "" else cfg.theme)}
      export ICEWINE_THEME_SKIP=${lib.escapeShellArg (lib.concatStringsSep ":" skippedThemeFiles)}
      export ICEWINE_THEME_GIT_ENABLE=${if cfg.shellExtras.git.enable then "true" else "false"}
      export ICEWINE_NIXPKGS_LAST_MODIFIED=${toString icewineNixpkgsLastModified}
      export XDG_CONFIG_HOME=''${XDG_CONFIG_HOME:-${configHome}}
      export XDG_DATA_HOME=''${XDG_DATA_HOME:-${dataHome}}
      export XDG_STATE_HOME=''${XDG_STATE_HOME:-${stateHome}}
      exec python3 ${../scripts/theme} "$@"
    '';
  };
  manager = pkgs.callPackage ../manager/package.nix { };
  managerBackend = pkgs.writeShellApplication {
    name = "icewine-manage-backend";
    runtimeInputs = [ pkgs.python3 ];
    text = ''
      export ICEWINE_THEME_SCRIPT=${../scripts/theme}
      export ICEWINE_THEME_ASSETS=${../theme/assets}
      export ICEWINE_DEFAULT_FILES=${defaults}
      export ICEWINE_GTK_ENABLE=${if cfg.gtk.enable then "true" else "false"}
      export ICEWINE_THEME_SKIP=${lib.escapeShellArg (lib.concatStringsSep ":" skippedThemeFiles)}
      export ICEWINE_MANAGE_SELECTIONS=${lib.escapeShellArg (builtins.toJSON ((lib.genAttrs
        [ "desktop" "terminal" "filemanager" "handheld" "login" "shellExtras" ]
        (name: cfg.${name}.enable)) // {
          steam = cfg.steam;
          gamescope = cfg.steam != "none" && cfg.gamescope.enable;
        }))}
      export ICEWINE_THEME_POLICY=${lib.escapeShellArg (if cfg.theme == null then "" else cfg.theme)}
      export ICEWINE_NIXPKGS_LAST_MODIFIED=${toString icewineNixpkgsLastModified}
      export ICEWINE_THEME_GIT_ENABLE=${if cfg.shellExtras.git.enable then "true" else "false"}
      exec python3 ${../scripts/manage} "$@"
    '';
  };
  icewineDispatcher = pkgs.writeShellApplication {
    name = "icewine";
    runtimeInputs = [ wallpaperSelector themeCli manager managerBackend ];
    text = builtins.readFile ../scripts/icewine;
  };
  icewineCli = pkgs.symlinkJoin {
    name = "icewine";
    paths = [ icewineDispatcher manager managerBackend themeCli wallpaperSelector ];
  };
  monitorCapabilities = pkgs.writeShellApplication {
    name = "icewine-monitor-capabilities";
    runtimeInputs = [ pkgs.edid-decode ];
    text = builtins.readFile ../quickshell/tools/probe-monitor-capabilities;
  };
  steamShortcuts = import ../quickshell/tools/steam-shortcuts.nix { inherit pkgs; };
  monitorBrightness = pkgs.writeShellApplication {
    name = "icewine-monitor-brightness";
    runtimeInputs = [ pkgs.coreutils pkgs.brightnessctl pkgs.ddcutil pkgs.hyprland pkgs.jq pkgs.util-linux ];
    text = builtins.readFile ../quickshell/tools/monitor-brightness;
  };
in {
  config = lib.mkIf cfg.enable {
    users.users.${cfg.user}.packages = [ icewineCli ];
    environment.sessionVariables = {
      ICEWINE_AUTHENTICATION_REQUIRED = if cfg.authenticationRequired then "true" else "false";
      ICEWINE_KITTY_PRESET = if cfg.terminal.enable then "true" else "false";
    };
  systemd.user.services.icewine = lib.mkIf cfg.desktop.enable {
    description = "Icewine desktop shell";
    partOf = [ "graphical-session.target" ];
    after = [ "graphical-session.target" "nixos-activation.service" ];
    wants = [ "nixos-activation.service" ];
    conflicts = [ "mako.service" ];
    unitConfig.ConditionUser = cfg.user;
    serviceConfig = {
      ExecStart = "${quickshell}/bin/qs";
      Environment = [
        "XDG_DATA_HOME=${dataHome}"
        "XDG_CONFIG_HOME=${configHome}"
        "XDG_STATE_HOME=${stateHome}"
        "ICEWINE_THEME_IDS=${lib.concatStringsSep ":" themeIds}"
        "ICEWINE_THEME_POLICY=${if cfg.theme == null then "" else cfg.theme}"
        "ICEWINE_AUTHENTICATION_REQUIRED=${if cfg.authenticationRequired then "true" else "false"}"
        "ICEWINE_STEAM_ENABLED=${if cfg.steam != "none" then "true" else "false"}"
        "ICEWINE_GAMESCOPE_ENABLED=${if cfg.steam != "none" && cfg.gamescope.enable then "true" else "false"}"
        "ICEWINE_BATTERY_ENABLED=${if cfg.battery.enable then "true" else "false"}"
        "PATH=/run/wrappers/bin:/etc/profiles/per-user/${cfg.user}/bin:/run/current-system/sw/bin:${lib.makeBinPath [ themeCli pkgs.glib pkgs.hyprland pkgs.systemd monitorCapabilities monitorBrightness steamShortcuts ]}"
        "QT_IM_MODULE=qtvirtualkeyboard"
      ];
      Restart = "on-failure";
    };
    wantedBy = [ "graphical-session.target" ];
  };
  systemd.user.paths.icewine-refresh-flatpak-icons = lib.mkIf (cfg.desktop.enable && (cfg.steam == "flatpak")) {
    description = "Refresh Icewine when Flatpak's icon cache changes";
    partOf = [ "graphical-session.target" ];
    after = [ "graphical-session.target" ];
    unitConfig.ConditionUser = cfg.user;
    pathConfig.PathChanged = [
      "/var/lib/flatpak/exports/share/icons/hicolor/icon-theme.cache"
      "${dataHome}/flatpak/exports/share/icons/hicolor/icon-theme.cache"
    ];
    wantedBy = [ "graphical-session.target" ];
  };
  systemd.user.services.icewine-refresh-flatpak-icons = lib.mkIf (cfg.desktop.enable && (cfg.steam == "flatpak")) {
    description = "Refresh Icewine's Flatpak icon cache";
    after = [ "icewine.service" ];
    unitConfig.ConditionUser = cfg.user;
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${pkgs.systemd}/bin/systemctl --user try-restart icewine.service";
    };
  };
  systemd.user.services.hyprpolkitagent = lib.mkIf cfg.desktop.enable {
    description = "Hyprland Polkit authentication agent";
    partOf = [ "graphical-session.target" ];
    after = [ "graphical-session.target" ];
    wantedBy = [ "graphical-session.target" ];
    unitConfig.ConditionUser = cfg.user;
    serviceConfig = {
      ExecStart = "${pkgs.hyprpolkitagent}/libexec/hyprpolkitagent";
      Restart = "on-failure";
    };
  };
  };
}
