{ config, lib, pkgs, ... }:
let
  cfg = config.services.icewine;
  steamEntries = (pkgs.writeTextDir "share/applications/steam-gamescope.desktop" ''
    [Desktop Entry]
    Type=Application
    Name=Steam (Gamescope)
    Comment=Launch Steam inside monitor-aware Gamescope
    Exec=${pkgs.quickshell}/bin/qs ipc call gameLauncher launchSteamGamescope
    Icon=${if builtins.elem "com.valvesoftware.Steam" cfg.applications.steam then "com.valvesoftware.Steam" else "steam"}
    Categories=Game;
    Terminal=false
  '').overrideAttrs { name = "icewine-steam-desktop-entries"; };
in {
  config = lib.mkIf cfg.enable {
    services.icewine.defaultFiles.data = {
      "applications/uuctl.desktop" = pkgs.writeText "uuctl-hidden.desktop" ''
        [Desktop Entry]
        Type=Application
        Name=uuctl
        NoDisplay=true
        Hidden=true
      '';
    };
    users.users.${cfg.user}.packages = lib.optionals (cfg.fileManager.preset == "yazi")
      [ pkgs.yazi pkgs.ffmpegthumbnailer pkgs._7zz ] ++ lib.optional (cfg.steam != "none") steamEntries;
    services.icewine.defaultFiles.config = lib.mkIf cfg.idle.enable {
      "hypr/hypridle.conf" = pkgs.writeText "icewine-hypridle.conf" ''
        # Shared idle defaults first; add your general settings below.
        # Listener blocks append; edit a local full copy to replace shipped timers.
        source = hypridle-icewine/defaults.conf
      '';
    };
    systemd.user.services.hypridle = lib.mkIf cfg.idle.enable {
      description = "Icewine idle locking and suspend";
      partOf = [ "graphical-session.target" ];
      after = [ "graphical-session.target" ];
      wantedBy = [ "graphical-session.target" ];
      unitConfig.ConditionUser = cfg.user;
      serviceConfig = {
        ExecStart = "${pkgs.hypridle}/bin/hypridle -c %h/.config/hypr/hypridle.conf";
        Restart = "on-failure";
        RestartSec = "100ms";
      };
    };
  };
}
