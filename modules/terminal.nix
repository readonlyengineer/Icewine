{ config, lib, osConfig, ... }:
{
  config = lib.mkIf (osConfig.services.icewine.terminal.preset == "kitty") {
    programs.kitty = {
      enable = true;
      shellIntegration = {
        mode = lib.mkDefault null;
        enableBashIntegration = lib.mkDefault false;
        enableFishIntegration = lib.mkDefault false;
        enableZshIntegration = lib.mkDefault false;
      };
    };
    # Keep all Home Manager Kitty options in a separate host-owned include.
    # The editable kitty.conf remains Icewine's only owner of that path.
    xdg.configFile."kitty/kitty.conf".target = lib.mkForce "${config.xdg.configHome}/kitty/host.conf";
  };
}
