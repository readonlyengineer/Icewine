{ config, lib, pkgs, ... }:
let
  cfg = config.services.icewine;
  sddmTheme = pkgs.callPackage ../sddm { theme = cfg.theme; };
in
{
  options.services.icewine.login.enable = lib.mkEnableOption "KDE Breeze SDDM with Icewine colours";

  config = lib.mkIf (cfg.enable && cfg.login.enable) {
    assertions = [{
      assertion = config.services.displayManager.sddm.enable;
      message = "Icewine login styling requires host-owned services.displayManager.sddm.enable = true.";
    }];
    systemd.tmpfiles.rules = [
      "d /var/lib/icewine 0755 root root - -"
      "d /var/lib/icewine/sddm 0755 ${cfg.user} root - -"
    ];
    services.xserver.enable = true;
    services.xserver.excludePackages = [ pkgs.xterm ];
    services.displayManager = {
      defaultSession = lib.mkIf cfg.desktop.enable (lib.mkDefault "hyprland-uwsm");
      logToJournal = true;
      sddm = {
        theme = "breeze";
        # SDDM filters daemon environment; configure the existing Qt wrappers
        # instead, preserving the host's General.GreeterEnvironment setting.
        package = pkgs.kdePackages.sddm.overrideAttrs (old: {
          qtWrapperArgs = (old.qtWrapperArgs or [ ]) ++ [
            "--set" "QT_QPA_PLATFORMTHEME" "kde"
            "--set" "QT_QUICK_CONTROLS_STYLE" "org.kde.breeze"
            "--set" "KIRIGAMI_PLATFORM_THEME" "org.kde.breeze"
            "--set" "XDG_CONFIG_HOME" (if cfg.theme == null
              then "/var/lib/icewine/sddm" else "/etc/icewine/sddm")
            "--prefix" "XDG_CONFIG_DIRS" ":" "/etc/icewine/sddm"
          ];
        });
        extraPackages = with pkgs.kdePackages; [
          breeze breeze-icons kirigami libplasma plasma-workspace
          qqc2-breeze-style plasma-integration qtsvg qt5compat qtvirtualkeyboard
        ];
        settings.General.InputMethod = "qtvirtualkeyboard";
      };
    };
    environment.systemPackages = [ sddmTheme ];
    # KConfig layers this default below the public user-owned kdeglobals.
    environment.etc."icewine/sddm/kdeglobals".source =
      "${sddmTheme}/share/icewine/sddm/kdeglobals";
  };
}
