{ lib, pkgs, osConfig, ... }:
let
  cfg = osConfig.services.icewine;
  palette = import ../theme/palette.nix;
in {
  programs.yazi = lib.mkIf (cfg.fileManager.preset == "yazi") {
    enable = true;
    enableBashIntegration = lib.mkDefault false;
    extraPackages = with pkgs; [
      ffmpegthumbnailer
      _7zz
    ];
    keymap.mgr.prepend_keymap = [
      {
        on = "M";
        run = "plugin mount";
        desc = "Mount/unmount removable drives (mount.yazi)";
      }
    ];
    theme.mode = lib.mapAttrsRecursive (_: lib.mkDefault) {
      normal_main = { fg = "#${palette.highlight}"; bg = "#${palette.highlightDark}"; bold = true; };
      normal_alt = { fg = "#${palette.highlight}"; bg = "#${palette.highlightDark}"; };
    };
    plugins.mount = pkgs.yaziPlugins.mount;
  };
  services.hypridle = lib.mkIf cfg.idle.enable {
    enable = true;
    settings = {
      general = lib.mapAttrs (_: lib.mkDefault) {
        before_sleep_cmd = "qs ipc call session lock";
        inhibit_sleep = 3;
        ignore_dbus_inhibit = false;
        ignore_systemd_inhibit = false;
        ignore_wayland_inhibit = false;
      };
      listener = lib.mkDefault [
        { timeout = 600; on-timeout = "loginctl lock-session"; }
        { timeout = 1200;
          on-timeout = "hyprctl dispatch 'hl.dsp.dpms({ action = \"disable\" })'";
          on-resume = "hyprctl dispatch 'hl.dsp.dpms({ action = \"enable\" })'"; }
        { timeout = 1800; on-timeout = "systemctl suspend"; }
      ];
    };
  };
  # Warn notification at 20% / Critical notification 10% / Suspend at Danger 3%
  # KDE/GNOME have native battery alerts
  services.batsignal = lib.mkIf cfg.battery.enable {
    enable = true;
    extraArgs = lib.mkDefault [
      "-w" "20" "-c" "10" "-d" "3" "-f" "0"
      "-W" "Battery Low" "-C" "Battery Critical" "-D" "systemctl suspend"
      "-I" "battery-low"
    ];
  };
  systemd.user.services.batsignal = lib.mkIf cfg.battery.enable { Service.Restart = lib.mkForce "no"; };
  # uuctl is bundled with UWSM, so mask only its unwanted launcher entry.
  xdg.dataFile."applications/uuctl.desktop".text = ''
    [Desktop Entry]
    Type=Application
    Name=uuctl
    NoDisplay=true
    Hidden=true
  '';
  systemd.user.services.hypridle = lib.mkIf cfg.idle.enable {
    Service = {
      Restart = lib.mkForce "on-failure";
      RestartSec = lib.mkForce "100ms";
    };
  };
}
