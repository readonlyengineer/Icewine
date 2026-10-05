{ config, lib, pkgs, ... }:
let
  cfg = config.services.icewine;
in
{
  options.services.icewine.login.enable = lib.mkEnableOption "Icewine's SDDM login screen" // {
    default = true;
  };

  config = lib.mkIf (cfg.enable && cfg.login.enable) {
    systemd.tmpfiles.rules = [
      "d /var/lib/icewine 0755 root root - -"
      "d /var/lib/icewine/sddm 0755 ${cfg.user} root - -"
    ];
    services.xserver.enable = true;
    services.xserver.excludePackages = [ pkgs.xterm ];
    services.displayManager = {
      defaultSession = lib.mkDefault "hyprland-uwsm";
      logToJournal = true;
      sddm = {
        enable = true;
        theme = "icewine";
        extraPackages = [ pkgs.qt6.qtvirtualkeyboard ];
        settings.General.InputMethod = "qtvirtualkeyboard";
      };
    };
    environment.systemPackages = [ (pkgs.callPackage ../sddm { }) ];
  };
}
