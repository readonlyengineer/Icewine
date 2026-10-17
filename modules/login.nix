{ config, lib, ... }:
let
  cfg = config.services.icewine;
  palette = builtins.fromJSON (builtins.readFile
    (../theme/assets/themes + "/${if cfg.theme == null then "catppuccin-mocha" else cfg.theme}.json"));
in {
  options.services.icewine.login = {
    enable = lib.mkEnableOption "minimal Icewine tuigreet styling";
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
}
