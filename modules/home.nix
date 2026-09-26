{ config, lib, pkgs, osConfig, ... }:
let
  cfg = osConfig.services.icewine;
  palette = import ../theme/palette.nix;
  quickshell = pkgs.quickshell.overrideAttrs (old: {
    buildInputs = old.buildInputs ++ [ pkgs.qt6.qtvirtualkeyboard ];
  });
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
  hyprTheme = pkgs.writeText "icewine-theme.lua" ''
    hl.config({ general = { col = {
      active_border = { colors = { "rgba(${palette.highlight}ee)", "rgba(${palette.secondaryHighlight}ee)" }, angle = 45 },
      inactive_border = "rgba(${palette.background}aa)",
    } } })
  '';
  quickshellPalette = pkgs.writeText "icewine-palette.qml" (
    builtins.replaceStrings
      (map (name: "@${name}@") (builtins.attrNames palette))
      (builtins.attrValues palette)
      (builtins.readFile ../quickshell/theme/Palette.qml.in)
  );
  hyprTree = pkgs.runCommand "icewine-hyprland" { } ''
    mkdir -p $out
    cp -r ${../hyprland}/hyprland.lua ${../hyprland}/modules $out/
    chmod -R u+w $out
    cp ${hyprTheme} $out/modules/Theme.lua
    ${lib.optionalString cfg.handheld.enable ''
      cp ${../hyprland/deck/Deck.lua} $out/modules/Deck.lua
    ''}
    ${lib.concatStringsSep "\n" (lib.mapAttrsToList (name: source:
      "cp ${lib.escapeShellArg "${source}"} \"$out/modules/\"${lib.escapeShellArg name}"
    ) cfg.hyprland.extraModules)}
  '';
in {
  imports = [ ./terminal.nix ./shell.nix ./gtk.nix ./desktop.nix ];

  home.sessionVariables.EDITOR = lib.mkDefault (lib.escapeShellArgs cfg.applications.editor);

  xdg.configFile = {
    "hypr" = { source = hyprTree; recursive = true; };
    "uwsm/env".source = ../session/env;
    "quickshell/shell.qml".source = if cfg.handheld.enable
      then ../quickshell/deck/shell.qml else ../quickshell/shell.qml;
    "quickshell/adapters".source = ../quickshell/adapters;
    "quickshell/modules".source = ../quickshell/modules;
    "quickshell/DeckOverlay.qml" = lib.mkIf cfg.handheld.enable { source = ../quickshell/deck/DeckOverlay.qml; };
    "quickshell/DeckMenu.js" = lib.mkIf cfg.handheld.enable { source = ../quickshell/deck/DeckMenu.js; };
    "quickshell/config/qmldir".text = "singleton Settings 1.0 Settings.qml\n";
    "quickshell/config/Settings.qml".text = ''
      pragma Singleton
      import QtQml
      QtObject {
        readonly property bool authenticationRequired: ${builtins.toJSON cfg.authenticationRequired}
      }
    '';
    "quickshell/theme/Palette.qml".source = quickshellPalette;
  };

  systemd.user.services.icewine = {
    Unit = {
      Description = "Icewine desktop shell";
      PartOf = [ "graphical-session.target" ];
      After = [ "graphical-session.target" ];
      Conflicts = [ "mako.service" ];
    };
    Service = {
      ExecStart = "${quickshell}/bin/qs";
      Environment = [
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
