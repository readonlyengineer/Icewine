{ config, lib, pkgs, osConfig, ... }:
let
  theme = "${config.xdg.configHome}/icewine/current/kitty.conf";
in {
  config = lib.mkIf (osConfig.services.icewine.terminal.preset == "kitty") {
    programs.kitty = {
      enable = true;
      shellIntegration = {
        mode = lib.mkDefault null;
        enableBashIntegration = lib.mkDefault false;
        enableFishIntegration = lib.mkDefault false;
        enableZshIntegration = lib.mkDefault false;
      };
      # Home Manager emits settings at order 540; host colour overrides win.
      extraConfig = lib.mkOrder 520 ''
        include ${config.xdg.configHome}/icewine/current/kitty-base.conf
        include ${theme}
      '';
    };
  };
}
