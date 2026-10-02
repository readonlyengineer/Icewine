{ config, lib, pkgs, osConfig, ... }:
let
  cfg = osConfig.services.icewine.shell;
  current = "${config.xdg.configHome}/icewine/current";
  fastfetchConfig = lib.optionalString (config.programs.fastfetch.settings == { })
    " --config ${lib.escapeShellArg "${current}/fastfetch.jsonc"}";
in {
  config = lib.mkIf cfg.enable {
    home.packages = lib.optional cfg.blesh.enable pkgs.blesh;
    programs.bash = {
      enable = true;
      enableCompletion = lib.mkDefault true;
      shellAliases = {
        ls = lib.mkDefault "ls --color=auto";
        grep = lib.mkDefault "grep --color=auto";
      };
      # Home Manager places initExtra after its interactive-shell guard.
      initExtra = lib.mkAfter (
        "source ${lib.escapeShellArg "${current}/ls-colors.sh"}\n"
        + lib.optionalString cfg.fastfetch.enable
          "${lib.getExe config.programs.fastfetch.package}${fastfetchConfig}\n"
        + lib.optionalString cfg.blesh.enable ''
          source -- ${pkgs.blesh}/share/blesh/ble.sh 2>/dev/null
          bleopt exec_errexit_mark=
          bleopt exec_elapsed_mark=
          bleopt complete_menu_style=desc
        ''
      );
    };
    programs.fastfetch.enable = cfg.fastfetch.enable;
    programs.starship = lib.mkIf cfg.starship.enable {
      enable = true;
      enableBashIntegration = true;
    };
  };
}
