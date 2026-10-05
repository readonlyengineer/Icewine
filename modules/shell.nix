{ config, lib, pkgs, ... }:
let
  cfg = config.services.icewine;
  shell = cfg.shell;
  bashrc = pkgs.writeText "icewine-bashrc" ''
    # Shared interactive defaults first; add your overrides below.
    [[ $- == *i* && ''${ICEWINE_SHELL_ENABLED:-false} == true ]] || return
    . "''${XDG_CONFIG_HOME:-$HOME/.config}/icewine/shell/icewine/bashrc"
  '';
  profile = pkgs.writeText "icewine-profile" ''
    # Editable login-shell additions. /etc/profile supplies NixOS session policy.
  '';
  bashProfile = pkgs.writeText "icewine-bash-profile" ''
    if [[ -r "$HOME/.profile" ]]; then . "$HOME/.profile"; fi
    if [[ -r "$HOME/.bashrc" ]]; then . "$HOME/.bashrc"; fi
    # Add login-only overrides below.
  '';
in {
  config = lib.mkIf (cfg.enable && shell.enable) {
    programs.bash.interactiveShellInit = ''
      if [[ $USER == ${lib.escapeShellArg cfg.user} ]]; then
        export ICEWINE_SHELL_ENABLED=true
        export ICEWINE_FASTFETCH_ENABLED=${if shell.fastfetch.enable then "true" else "false"}
        export ICEWINE_BLESH_ENABLED=${if shell.blesh.enable then "true" else "false"}
        export ICEWINE_STARSHIP_ENABLED=${if shell.starship.enable then "true" else "false"}
      fi
    '';
    users.users.${cfg.user}.packages =
      lib.optional shell.fastfetch.enable pkgs.fastfetch
      ++ lib.optional shell.blesh.enable pkgs.blesh
      ++ lib.optional shell.starship.enable pkgs.starship;
    services.icewine.defaultFiles.config = {
      "icewine/shell/bashrc" = bashrc;
      "icewine/shell/profile" = profile;
      "icewine/shell/bash_profile" = bashProfile;
    };
  };
}
