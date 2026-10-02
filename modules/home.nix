{ config, lib, pkgs, osConfig, nixpkgsLastModified ? 0, ... }:
let
  cfg = osConfig.services.icewine;
  themeAssets = import ../theme/bundle.nix { inherit pkgs; };
  hostThemeFiles =
    lib.optional (config.programs.fastfetch.settings != { }) "fastfetch/config.jsonc"
    ++ lib.optional (config.programs.starship.settings != { }) "starship.toml"
    ++ lib.optional (config.programs.yazi.theme != { }) "yazi/theme.toml"
    ++ lib.optional (config.programs.yazi.keymap != { }) "yazi/keymap.toml";
  quickshell = pkgs.quickshell.overrideAttrs (old: {
    buildInputs = old.buildInputs ++ [ pkgs.qt6.qtvirtualkeyboard ];
  });
  wallpaperSelector = pkgs.writeShellApplication {
    name = "icewine-wallpaper";
    runtimeInputs = [ pkgs.coreutils quickshell ];
    text = ''
      export ICEWINE_WALLPAPER_VALIDATOR=${../quickshell/modules}/WallpaperValidator.qml
      export ICEWINE_WALLPAPER_DATA_HOME=''${ICEWINE_WALLPAPER_DATA_HOME:-''${XDG_DATA_HOME:-${config.xdg.dataHome}}}
      ${builtins.readFile ../scripts/wallpaper}
    '';
  };
  themeCli = pkgs.writeShellApplication {
    name = "icewine-theme";
    runtimeInputs = [ pkgs.python3 pkgs.hyprland pkgs.systemd ];
    text = ''
      export ICEWINE_THEME_ASSETS=${themeAssets}/share/icewine
      export ICEWINE_THEME_POLICY=${lib.escapeShellArg (if cfg.theme == null then "" else cfg.theme)}
      export ICEWINE_THEME_SKIP=${lib.escapeShellArg (lib.concatStringsSep ":" hostThemeFiles)}
      export ICEWINE_THEME_GIT_ENABLE=${if cfg.shell.starship.git.enable then "true" else "false"}
      export ICEWINE_NIXPKGS_LAST_MODIFIED=${toString nixpkgsLastModified}
      export XDG_CONFIG_HOME=''${XDG_CONFIG_HOME:-${config.xdg.configHome}}
      export XDG_STATE_HOME=''${XDG_STATE_HOME:-${config.xdg.stateHome}}
      exec python3 ${../scripts/theme} "$@"
    '';
  };
  icewineCli = pkgs.writeShellApplication {
    name = "icewine";
    runtimeInputs = [ wallpaperSelector themeCli ];
    text = builtins.readFile ../scripts/icewine;
  };
  monitorCapabilities = pkgs.writeShellApplication {
    name = "icewine-monitor-capabilities";
    runtimeInputs = [ pkgs.edid-decode ];
    text = builtins.readFile ../quickshell/tools/probe-monitor-capabilities;
  };
  monitorBrightness = pkgs.writeShellApplication {
    name = "icewine-monitor-brightness";
    runtimeInputs = [ pkgs.coreutils pkgs.brightnessctl pkgs.ddcutil ];
    text = builtins.readFile ../quickshell/tools/monitor-brightness;
  };
  hyprTree = pkgs.runCommand "icewine-hyprland" { } ''
    mkdir -p $out
    cp -r ${../hyprland}/hyprland.lua ${../hyprland}/modules $out/
    chmod -R u+w $out
    ln -s ${config.xdg.configHome}/icewine/current/Theme.lua $out/modules/Theme.lua
    ${lib.optionalString cfg.handheld.enable ''
      cp ${../hyprland/deck/Deck.lua} $out/modules/Deck.lua
    ''}
    ${lib.concatStringsSep "\n" (lib.mapAttrsToList (name: source:
      "cp ${lib.escapeShellArg "${source}"} \"$out/modules/\"${lib.escapeShellArg name}"
    ) cfg.hyprland.extraModules)}
  '';
in {
  imports = [ ./terminal.nix ./shell.nix ./gtk.nix ./desktop.nix ];

  home.sessionVariables = {
    EDITOR = lib.mkDefault (lib.escapeShellArgs cfg.applications.editor);
    XDG_DATA_HOME = lib.mkDefault config.xdg.dataHome;
    XDG_CONFIG_HOME = lib.mkDefault config.xdg.configHome;
    XDG_STATE_HOME = lib.mkDefault config.xdg.stateHome;
    ICEWINE_AUTHENTICATION_REQUIRED = if cfg.authenticationRequired then "true" else "false";
  } // lib.optionalAttrs (cfg.terminal.preset == null) {
    ICEWINE_KITTY_PRESET = "false";
  };
  programs.starship.configPath = lib.mkIf (cfg.shell.enable && cfg.shell.starship.enable && config.programs.starship.settings == { })
    (lib.mkDefault "${config.xdg.configHome}/icewine/current/starship.toml");
  home.packages = [ icewineCli ];

  home.activation.icewineThemeInit = lib.hm.dag.entryBefore [ "linkGeneration" ] ''
    ${icewineCli}/bin/icewine init
  '';
  home.activation.icewineThemeApply = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
    if ! ${themeCli}/bin/icewine-theme apply; then
      echo "Icewine: theme selection is saved; a running consumer needs a restart." >&2
    fi
  '';

  home.activation.icewineWallpaperMigration = lib.hm.dag.entryBefore [ "linkGeneration" ] ''
    if ! ${icewineCli}/bin/icewine wallpaper --migrate \
      ${lib.escapeShellArg "${config.xdg.dataHome}/wallpapers/current.jpg"} \
      ${lib.escapeShellArg config.xdg.dataHome}; then
      echo "Icewine: legacy wallpaper could not be migrated; it was left unchanged." >&2
    fi
  '';

  xdg.configFile = {
    "hypr" = { source = hyprTree; recursive = true; };
    "uwsm/env".source = ../session/env;
    "quickshell/shell.qml".source = if cfg.handheld.enable
      then ../quickshell/deck/shell.qml else ../quickshell/shell.qml;
    "quickshell/adapters".source = ../quickshell/adapters;
    "quickshell/modules".source = ../quickshell/modules;
    "quickshell/DeckOverlay.qml" = lib.mkIf cfg.handheld.enable { source = ../quickshell/deck/DeckOverlay.qml; };
    "quickshell/DeckMenu.js" = lib.mkIf cfg.handheld.enable { source = ../quickshell/deck/DeckMenu.js; };
    "quickshell/config/qmldir".source = ../quickshell/config/qmldir;
    "quickshell/config/Settings.qml".source = ../quickshell/config/Settings.qml;
  };

  systemd.user.services.icewine = {
    Unit = {
      Description = "Icewine desktop shell";
      PartOf = [ "graphical-session.target" ];
      After = [ "graphical-session.target" ];
      Conflicts = [ "mako.service" ];
    };
    Service = {
      ExecStartPre = "${icewineCli}/bin/icewine init";
      ExecStart = "${quickshell}/bin/qs";
      Environment = [
        "XDG_DATA_HOME=${config.xdg.dataHome}"
        "ICEWINE_AUTHENTICATION_REQUIRED=${if cfg.authenticationRequired then "true" else "false"}"
        "PATH=${config.home.profileDirectory}/bin:/run/current-system/sw/bin:${lib.makeBinPath [ pkgs.glib pkgs.hyprland pkgs.systemd monitorCapabilities monitorBrightness ]}"
        "QT_IM_MODULE=qtvirtualkeyboard"
      ];
      Restart = "on-failure";
    };
    Install.WantedBy = [ "graphical-session.target" ];
  };
  systemd.user.paths.icewine-refresh-flatpak-icons = {
    Unit = {
      Description = "Refresh Icewine when Flatpak's icon cache changes";
      PartOf = [ "graphical-session.target" ];
      After = [ "graphical-session.target" ];
    };
    Path.PathChanged = [
      "/var/lib/flatpak/exports/share/icons/hicolor/icon-theme.cache"
      "${config.home.homeDirectory}/.local/share/flatpak/exports/share/icons/hicolor/icon-theme.cache"
    ];
    Install.WantedBy = [ "graphical-session.target" ];
  };
  systemd.user.services.icewine-refresh-flatpak-icons = {
    Unit = {
      Description = "Refresh Icewine's Flatpak icon cache";
      After = [ "icewine.service" ];
    };
    Service = {
      Type = "oneshot";
      ExecStart = "${pkgs.systemd}/bin/systemctl --user try-restart icewine.service";
    };
  };
  services.hyprpolkitagent.enable = true;
  systemd.user.services.hyprpolkitagent.Service.Restart = "on-failure";
}
