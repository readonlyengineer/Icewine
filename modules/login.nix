{ config, lib, pkgs, ... }:
let
  cfg = config.services.icewine;
  palette = builtins.fromJSON (builtins.readFile
    (../theme/assets/themes + "/${if cfg.theme == null then "catppuccin-mocha" else cfg.theme}.json"));
in {
  options.services.icewine.login = {
    enable = lib.mkEnableOption "minimal Icewine tuigreet styling";
    greeter.enable = lib.mkEnableOption "the optional NixOS Icewine greetd/tuigreet login service (requires desktop.enable)";
    args = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      readOnly = true;
      default = lib.optionals cfg.login.enable [
        "--width" "60"
        "--theme" "text=#${palette.foreground};border=#${palette.border};prompt=#${palette.highlight};input=#${palette.foreground};action=#${palette.muted};button=#${palette.highlight};container=#${palette.background}"
      ];
      description = "Native tuigreet styling arguments; login and session policy belong to the host.";
    };
  };

  config = lib.mkIf (cfg.enable && cfg.login.greeter.enable) {
    assertions = [
      { assertion = cfg.desktop.enable;
        message = "Icewine greeter requires services.icewine.desktop.enable for its Hyprland UWSM session."; }
      { assertion = lib.all (name:
          let service = config.systemd.services.${name}; in
          name == "greetd" || !service.enable ||
          (name != "display-manager" && !(lib.elem "display-manager.service" service.aliases)))
          (builtins.attrNames config.systemd.services);
        message = "Icewine greeter conflicts with another display manager; disable it explicitly before opting in."; }
    ];
    services.greetd = {
      enable = lib.mkDefault true;
      useTextGreeter = lib.mkDefault true;
      settings.default_session.command = lib.mkDefault (lib.escapeShellArgs (
        [ "${pkgs.tuigreet}/bin/tuigreet"
          "--cmd" "${pkgs.uwsm}/bin/uwsm start hyprland-uwsm.desktop"
          "--sessions" "${config.services.displayManager.sessionData.desktops}/share/wayland-sessions" ]));
    };
  };
}
