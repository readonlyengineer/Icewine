{ config, lib, pkgs, icewineNixpkgsLastModified ? 0, ... }:
let
  cfg = config.services.icewine;
  userHome = config.users.users.${cfg.user}.home;
  configHome = "${userHome}/.config";
  dataHome = "${userHome}/.local/share";
  stateHome = "${userHome}/.local/state";
  themeAssets = import ../theme/bundle.nix { inherit pkgs; };
  themeIds = map (name: lib.removeSuffix ".json" name)
    (builtins.filter (name: lib.hasSuffix ".json" name)
      (builtins.attrNames (builtins.readDir ../theme/assets/themes)));
  skippedThemeFiles =
    lib.optionals (!cfg.gtk.enable) [ "gtk-3.0/settings.ini" "gtk-3.0/gtk.css" "gtk-4.0/settings.ini" "gtk-4.0/gtk.css" ]
    ++ lib.optionals (cfg.fileManager.preset == null) [ "yazi/theme.toml" "yazi/keymap.toml" ]
    ++ lib.optionals (!cfg.shell.enable || !cfg.shell.fastfetch.enable) [ "fastfetch/config.jsonc" ]
    ++ lib.optionals (!cfg.shell.enable || !cfg.shell.starship.enable) [ "starship.toml" ];
  defaults = pkgs.runCommand "icewine-default-files" { } ''
    mkdir -p $out/config/hypr/modules $out/config/quickshell/config $out/config/uwsm $out/config/nvim $out/data
    cp -r ${../hyprland}/modules/. $out/config/hypr/modules/
    cp ${../hyprland}/hyprland.lua $out/config/hypr/hyprland.lua
    cp ${../session/env} $out/config/uwsm/env
    cp ${../nvim/init.lua} $out/config/nvim/init.lua
    ${lib.optionalString (cfg.terminal.preset == "kitty") ''
      mkdir -p $out/config/kitty
      cp ${../kitty/kitty.conf} $out/config/kitty/kitty.conf
      touch $out/config/kitty/host.conf
    ''}
    ${lib.optionalString (cfg.fileManager.preset == "yazi") ''
      mkdir -p $out/config/yazi/plugins/mount.yazi
      cp -r ${pkgs.yaziPlugins.mount}/. $out/config/yazi/plugins/mount.yazi/
    ''}
    ${lib.optionalString cfg.shell.enable ''
      mkdir -p $out/home
      ln -s icewine/shell/bashrc $out/home/.bashrc
      ln -s icewine/shell/profile $out/home/.profile
      ln -s icewine/shell/bash_profile $out/home/.bash_profile
    ''}
    cp ${if cfg.handheld.enable then ../quickshell/deck/shell.qml else ../quickshell/shell.qml} $out/config/quickshell/shell.qml
    cp -r ${../quickshell/adapters} $out/config/quickshell/adapters
    cp -r ${../quickshell/modules} $out/config/quickshell/modules
    cp -r ${../quickshell/theme} $out/config/quickshell/theme
    cp ${../quickshell/config/qmldir} $out/config/quickshell/config/qmldir
    cp ${../quickshell/config/Settings.qml} $out/config/quickshell/config/Settings.qml
    ${lib.optionalString cfg.handheld.enable ''
      cp ${../hyprland/deck/Deck.lua} $out/config/hypr/modules/Deck.lua
      chmod u+w $out/config/hypr/hyprland.lua
      printf '\nrequire("modules.Deck")\n' >> $out/config/hypr/hyprland.lua
      cp ${../quickshell/deck/DeckOverlay.qml} $out/config/quickshell/DeckOverlay.qml
      cp ${../quickshell/deck/DeckMenu.js} $out/config/quickshell/DeckMenu.js
    ''}
    chmod -R u+w $out
    ${lib.concatStringsSep "\n" (lib.mapAttrsToList (name: source:
      "mkdir -p $out/config/${lib.escapeShellArg (builtins.dirOf name)}; cp ${lib.escapeShellArg "${source}"} $out/config/${lib.escapeShellArg name}"
    ) cfg.defaultFiles.config)}
    ${lib.concatStringsSep "\n" (lib.mapAttrsToList (name: source:
      "mkdir -p $out/data/${lib.escapeShellArg (builtins.dirOf name)}; cp ${lib.escapeShellArg "${source}"} $out/data/${lib.escapeShellArg name}"
    ) cfg.defaultFiles.data)}
  '';
  quickshell = pkgs.quickshell.overrideAttrs (old: {
    buildInputs = old.buildInputs ++ [ pkgs.qt6.qtvirtualkeyboard ];
  });
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
    runtimeInputs = [ pkgs.python3 pkgs.hyprland pkgs.systemd pkgs.glib quickshell pkgs.neovim ]
      ++ lib.optional (cfg.terminal.preset == "kitty") pkgs.kitty
      ++ lib.optional (cfg.fileManager.preset == "yazi") pkgs.yazi
      ++ lib.optional config.services.flatpak.enable pkgs.flatpak;
    text = ''
      export XDG_DATA_DIRS="${pkgs.gsettings-desktop-schemas}/share/gsettings-schemas/${pkgs.gsettings-desktop-schemas.name}:''${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
      export ICEWINE_GTK_ENABLE=${if cfg.gtk.enable then "true" else "false"}
      export ICEWINE_THEME_ASSETS=${themeAssets}/share/icewine
      export ICEWINE_DEFAULT_FILES=${defaults}
      export ICEWINE_THEME_POLICY=${lib.escapeShellArg (if cfg.theme == null then "" else cfg.theme)}
      export ICEWINE_THEME_SKIP=${lib.escapeShellArg (lib.concatStringsSep ":" skippedThemeFiles)}
      export ICEWINE_THEME_GIT_ENABLE=${if cfg.shell.starship.git.enable then "true" else "false"}
      export ICEWINE_NIXPKGS_LAST_MODIFIED=${toString icewineNixpkgsLastModified}
      export XDG_CONFIG_HOME=''${XDG_CONFIG_HOME:-${configHome}}
      export XDG_DATA_HOME=''${XDG_DATA_HOME:-${dataHome}}
      export XDG_STATE_HOME=''${XDG_STATE_HOME:-${stateHome}}
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
    runtimeInputs = [ pkgs.coreutils pkgs.brightnessctl pkgs.ddcutil pkgs.hyprland pkgs.jq pkgs.util-linux ];
    text = builtins.readFile ../quickshell/tools/monitor-brightness;
  };
in {
  config = lib.mkIf cfg.enable {
    users.users.${cfg.user}.packages = [ icewineCli ];
    systemd.services.icewine-init = {
      description = "Prepare Icewine user defaults before login";
      wantedBy = [ "multi-user.target" ];
      before = [ "display-manager.service" "greetd.service" ];
      unitConfig.RequiresMountsFor = [ userHome configHome dataHome stateHome ];
      serviceConfig = {
        Type = "oneshot";
        User = cfg.user;
        WorkingDirectory = userHome;
        Environment = [
          "HOME=${userHome}"
          "XDG_CONFIG_HOME=${configHome}"
          "XDG_DATA_HOME=${dataHome}"
          "XDG_STATE_HOME=${stateHome}"
        ];
        ExecStart = "${icewineCli}/bin/icewine init";
        ExecStartPost = "-${icewineCli}/bin/icewine wallpaper --migrate ${dataHome}/wallpapers/current.jpg ${dataHome}";
      };
    };
    systemd.services.display-manager = lib.mkIf cfg.login.enable {
      requires = [ "icewine-init.service" ];
      after = [ "icewine-init.service" ];
    };
    environment.sessionVariables = {
      EDITOR = lib.mkDefault (lib.escapeShellArgs cfg.applications.editor);
      ICEWINE_AUTHENTICATION_REQUIRED = if cfg.authenticationRequired then "true" else "false";
    };
    system.userActivationScripts.icewine.text = ''
      if [ "$(${pkgs.coreutils}/bin/id -un)" = ${lib.escapeShellArg cfg.user} ]; then
        ${icewineCli}/bin/icewine init
        if ! ${icewineCli}/bin/icewine wallpaper --migrate \
          ${lib.escapeShellArg "${dataHome}/wallpapers/current.jpg"} \
          ${lib.escapeShellArg dataHome}; then
          echo "Icewine: legacy wallpaper could not be migrated; it was left unchanged." >&2
        fi
        if ! ${themeCli}/bin/icewine-theme apply; then
          echo "Icewine: theme selection is saved; check reported live-application failures." >&2
        fi
      fi
    '';

  systemd.user.services.icewine = {
    description = "Icewine desktop shell";
    partOf = [ "graphical-session.target" ];
    after = [ "graphical-session.target" "nixos-activation.service" ];
    wants = [ "nixos-activation.service" ];
    conflicts = [ "mako.service" ];
    unitConfig.ConditionUser = cfg.user;
    serviceConfig = {
      ExecStartPre = "${icewineCli}/bin/icewine init";
      ExecStart = "${quickshell}/bin/qs";
      Environment = [
        "XDG_DATA_HOME=${dataHome}"
        "XDG_CONFIG_HOME=${configHome}"
        "XDG_STATE_HOME=${stateHome}"
        "ICEWINE_THEME_IDS=${lib.concatStringsSep ":" themeIds}"
        "ICEWINE_THEME_POLICY=${if cfg.theme == null then "" else cfg.theme}"
        "ICEWINE_AUTHENTICATION_REQUIRED=${if cfg.authenticationRequired then "true" else "false"}"
        "ICEWINE_BATTERY_ENABLED=${if cfg.battery.enable then "true" else "false"}"
        "PATH=/etc/profiles/per-user/${cfg.user}/bin:/run/current-system/sw/bin:${lib.makeBinPath [ themeCli pkgs.glib pkgs.hyprland pkgs.systemd monitorCapabilities monitorBrightness ]}"
        "QT_IM_MODULE=qtvirtualkeyboard"
      ];
      Restart = "on-failure";
    };
    wantedBy = [ "graphical-session.target" ];
  };
  systemd.user.paths.icewine-refresh-flatpak-icons = {
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
  systemd.user.services.icewine-refresh-flatpak-icons = {
    description = "Refresh Icewine's Flatpak icon cache";
    after = [ "icewine.service" ];
    unitConfig.ConditionUser = cfg.user;
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${pkgs.systemd}/bin/systemctl --user try-restart icewine.service";
    };
  };
  systemd.user.services.hyprpolkitagent = {
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
