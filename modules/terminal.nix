{ lib, pkgs, osConfig, ... }:
let
  palette = import ../theme/palette.nix;
  theme = pkgs.writeText "icewine-kitty-theme.conf" (builtins.replaceStrings
    (map (name: "@${name}@") (builtins.attrNames palette))
    (builtins.attrValues palette)
    (builtins.readFile ../theme/kitty.conf.in));
in {
  config = lib.mkIf (osConfig.services.icewine.terminal.preset == "kitty") {
    programs.kitty = {
      enable = true;
      font = {
        name = lib.mkDefault "JetBrainsMono Nerd Font";
        size = lib.mkDefault 14;
      };
      settings = lib.mapAttrs (_: lib.mkDefault) {
        bold_font = "auto";
        italic_font = "auto";
        bold_italic_font = "auto";
        background_blur = 1;
      };
      shellIntegration = {
        mode = lib.mkDefault null;
        enableBashIntegration = lib.mkDefault false;
        enableFishIntegration = lib.mkDefault false;
        enableZshIntegration = lib.mkDefault false;
      };
      # Home Manager emits settings at order 540; host colour overrides win.
      extraConfig = lib.mkOrder 520 "include ${theme}";
    };
  };
}
