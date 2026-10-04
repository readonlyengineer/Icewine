{ config, lib, pkgs, ... }:
let
  cfg = config.services.icewine;
  shell = cfg.shell;
  current = "\${XDG_CONFIG_HOME:-$HOME/.config}/icewine/current";
  bashrc = pkgs.writeText "icewine-bashrc" ''
    # Icewine's editable interactive Bash defaults.
    [[ $- == *i* && ''${ICEWINE_SHELL_ENABLED:-false} == true ]] || return
    export HISTSIZE=10000 HISTFILESIZE=10000 HISTCONTROL=ignoredups:ignorespace
    shopt -s histappend
    alias ls='ls --color=auto'
    alias grep='grep --color=auto'
    if [[ -r "${current}/ls-colors.sh" ]]; then
      . "${current}/ls-colors.sh"
    fi
    if [[ ''${ICEWINE_FASTFETCH_ENABLED:-false} == true ]] && command -v fastfetch >/dev/null; then
      fastfetch --config "${current}/fastfetch.jsonc"
    fi
    if [[ ''${ICEWINE_BLESH_ENABLED:-false} == true && -r /etc/profiles/per-user/$USER/share/blesh/ble.sh ]]; then
      source -- /etc/profiles/per-user/$USER/share/blesh/ble.sh 2>/dev/null
      bleopt exec_errexit_mark=
      bleopt exec_elapsed_mark=
      bleopt complete_menu_style=desc
    fi
    if [[ ''${ICEWINE_STARSHIP_ENABLED:-false} == true ]] && command -v starship >/dev/null; then
      export STARSHIP_CONFIG="${current}/starship.toml"
      eval "$(starship init bash)"
    fi
  '';
  profile = pkgs.writeText "icewine-profile" ''
    # Editable login-shell additions. /etc/profile supplies NixOS session policy.
  '';
  bashProfile = pkgs.writeText "icewine-bash-profile" ''
    if [[ -r "$HOME/.profile" ]]; then . "$HOME/.profile"; fi
    if [[ -r "$HOME/.bashrc" ]]; then . "$HOME/.bashrc"; fi
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
