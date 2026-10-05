{ self, nixpkgs }:
let
  lib = nixpkgs.lib;
  pkgs = nixpkgs.legacyPackages.x86_64-linux;
  example = extra: (lib.nixosSystem {
    system = "x86_64-linux";
    modules = [ self.nixosModules.default {
      users.users.demo.isNormalUser = true;
      services.icewine = { enable = true; user = "demo"; };
      system.stateVersion = "26.05";
    } extra ];
  }).config;
  defaults = example { };
  unmanaged = example {
    services.icewine = {
      gtk.enable = false;
      idle.enable = false;
      battery.enable = false;
      fileManager.preset = null;
      terminal.preset = null;
      shell.enable = false;
      applications.terminal = [ "custom-terminal" ];
    };
  };
  bareShell = example {
    services.icewine.shell = {
      fastfetch.enable = false;
      blesh.enable = false;
      starship.enable = false;
    };
  };
  cli = builtins.head (lib.filter (pkg: lib.getName pkg == "icewine") defaults.users.users.demo.packages);
in
assert defaults.systemd.user.services.hypridle.unitConfig.ConditionUser == "demo";
assert defaults.systemd.user.services.hyprpolkitagent.unitConfig.ConditionUser == "demo";
assert lib.elem "icewine-init.service" defaults.systemd.services.display-manager.wants;
assert !(lib.elem "icewine-init.service" defaults.systemd.services.display-manager.requires);
assert lib.elem "icewine-init.service" defaults.systemd.services.display-manager.after;
assert defaults.environment.sessionVariables.ICEWINE_KITTY_PRESET == "true";
assert unmanaged.environment.sessionVariables.ICEWINE_KITTY_PRESET == "false";
assert defaults.systemd.services.icewine-init.serviceConfig.User == "demo";
assert lib.elem pkgs.yazi defaults.users.users.demo.packages;
assert lib.elem pkgs.kitty defaults.users.users.demo.packages;
assert lib.elem pkgs.fastfetch defaults.users.users.demo.packages;
assert lib.elem pkgs.blesh defaults.users.users.demo.packages;
assert lib.elem pkgs.starship defaults.users.users.demo.packages;
assert defaults.services.gvfs.enable;
assert defaults.services.icewine.applications.fileManager == [ "icewine-terminal-exec" "yazi" ];
assert defaults.services.icewine.applications.editor == [ "nano" ];
assert defaults.environment.sessionVariables.EDITOR == "nano";
assert defaults.services.icewine.defaultFiles.config ? "icewine/shell/bashrc";
assert defaults.services.icewine.defaultFiles.config ? "hypr/hypridle.conf";
assert !(unmanaged.services.icewine.defaultFiles.config ? "icewine/shell/bashrc");
assert !(unmanaged.systemd.user.services ? hypridle);
assert !(lib.elem pkgs.yazi unmanaged.users.users.demo.packages);
assert !(lib.elem pkgs.kitty unmanaged.users.users.demo.packages);
assert bareShell.services.icewine.defaultFiles.config ? "icewine/shell/bashrc";
assert !(lib.elem pkgs.fastfetch bareShell.users.users.demo.packages);
assert !(lib.elem pkgs.blesh bareShell.users.users.demo.packages);
assert !(lib.elem pkgs.starship bareShell.users.users.demo.packages);
pkgs.runCommand "icewine-terminal-checks" {
  nativeBuildInputs = [ pkgs.bashInteractive pkgs.coreutils pkgs.python3 pkgs.git pkgs.starship ];
} ''
  export HOME="$TMPDIR/home" XDG_CONFIG_HOME="$TMPDIR/home/.config" XDG_DATA_HOME="$TMPDIR/home/.local/share" XDG_STATE_HOME="$TMPDIR/home/.local/state"
  mkdir -p "$HOME" "$TMPDIR/fake-bin"
  printf '#!/bin/sh\ntest "$#" -eq 0 && echo ICEWINE_FASTFETCH\n' > "$TMPDIR/fake-bin/fastfetch"
  chmod +x "$TMPDIR/fake-bin/fastfetch"
  export PATH="$TMPDIR/fake-bin:$PATH"
  ${cli}/bin/icewine init
  test -L "$HOME/.bashrc" && test -L "$HOME/.bash_profile" && test -L "$HOME/.profile"
  output=$(BASH_ENV="$HOME/.bashrc" bash --noprofile --norc -c 'echo COMMAND_OK')
  test "$output" = COMMAND_OK
  output=$(SSH_CONNECTION='127.0.0.1 1000 127.0.0.1 22' BASH_ENV="$HOME/.bashrc" bash --noprofile --norc -c 'echo COMMAND_OK')
  test "$output" = COMMAND_OK
  output=$(ICEWINE_SHELL_ENABLED=true ICEWINE_FASTFETCH_ENABLED=true ICEWINE_BLESH_ENABLED=false ICEWINE_STARSHIP_ENABLED=false bash --noprofile --rcfile "$HOME/.bashrc" -ic 'unset HISTFILE' 2>/dev/null)
  test "$output" = ICEWINE_FASTFETCH
  output=$(ICEWINE_SHELL_ENABLED=true ICEWINE_FASTFETCH_ENABLED=false ICEWINE_BLESH_ENABLED=false ICEWINE_STARSHIP_ENABLED=false bash --noprofile --rcfile "$HOME/.bashrc" -ic 'unset HISTFILE' 2>/dev/null)
  test -z "$output"
  output=$(ICEWINE_SHELL_ENABLED=false ICEWINE_FASTFETCH_ENABLED=true bash --noprofile --rcfile "$HOME/.bashrc" -ic 'unset HISTFILE' 2>/dev/null)
  test -z "$output"
  printf '\nHISTSIZE=123\n' >> "$XDG_CONFIG_HOME/icewine/shell/bashrc"
  output=$(ICEWINE_SHELL_ENABLED=true ICEWINE_FASTFETCH_ENABLED=false ICEWINE_BLESH_ENABLED=false ICEWINE_STARSHIP_ENABLED=false bash --noprofile --rcfile "$HOME/.bashrc" -ic 'echo "$HISTSIZE"; unset HISTFILE' 2>/dev/null)
  test "$output" = 123
  output=$(ICEWINE_SHELL_ENABLED=true ICEWINE_FASTFETCH_ENABLED=false ICEWINE_BLESH_ENABLED=false ICEWINE_STARSHIP_ENABLED=true bash --noprofile --rcfile "$HOME/.bashrc" -ic 'echo "$STARSHIP_CONFIG"; unset HISTFILE' 2>/dev/null)
  test "$output" = "$XDG_CONFIG_HOME/starship.toml"
  output=$(STARSHIP_CONFIG="$TMPDIR/my-starship.toml" ICEWINE_SHELL_ENABLED=true ICEWINE_FASTFETCH_ENABLED=false ICEWINE_BLESH_ENABLED=false ICEWINE_STARSHIP_ENABLED=true bash --noprofile --rcfile "$HOME/.bashrc" -ic 'echo "$STARSHIP_CONFIG"; unset HISTFILE' 2>/dev/null)
  test "$output" = "$TMPDIR/my-starship.toml"
  printf '# user edit\n' >> "$XDG_CONFIG_HOME/icewine/shell/bashrc"
  ${cli}/bin/icewine init bash
  tail -n 1 "$XDG_CONFIG_HOME/icewine/shell/bashrc" | grep -Fx '# user edit'
  ${cli}/bin/icewine reset bash
  test -f "$XDG_STATE_HOME/icewine/$(ls "$XDG_STATE_HOME/icewine" | grep '^defaults-reset-' | tail -n 1)/config/icewine/shell/bashrc"
  export STARSHIP_CACHE="$TMPDIR/starship" ICEWINE_THEME_ASSETS=${../theme/assets}
  mkdir -p "$STARSHIP_CACHE"
  git init -q --initial-branch=icewine-check repo
  cd repo
  touch tracked
  git add tracked
  git -c user.name=Test -c user.email=test@example.invalid -c commit.gpgsign=false commit -qm initial
  touch untracked
  python3 ${../scripts/theme} init
  prompt=$(STARSHIP_CONFIG="$XDG_CONFIG_HOME/icewine/current/starship.toml" starship prompt)
  case "$prompt" in *icewine-check*) ;; *) exit 1 ;; esac
  export ICEWINE_THEME_GIT_ENABLE=false
  python3 ${../scripts/theme} init
  prompt=$(STARSHIP_CONFIG="$XDG_CONFIG_HOME/icewine/current/starship.toml" starship prompt)
  case "$prompt" in *icewine-check*|*'?'*) exit 1 ;; esac
  touch "$out"
''
