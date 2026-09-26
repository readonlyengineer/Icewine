{ config, lib, pkgs, ... }:
{
  options.services.icewine.login.enable = lib.mkEnableOption "Icewine's SDDM login screen" // {
    default = true;
  };

  config = lib.mkIf (config.services.icewine.enable && config.services.icewine.login.enable) {
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
