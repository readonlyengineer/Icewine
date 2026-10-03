{ self, nixpkgs }:
let
  lib = nixpkgs.lib;
  pkgs = nixpkgs.legacyPackages.x86_64-linux;
  example = extra: (nixpkgs.lib.nixosSystem {
    system = "x86_64-linux";
    modules = [ self.nixosModules.default {
      users.users.demo.isNormalUser = true;
      services.icewine = { enable = true; user = "demo"; };
      system.stateVersion = "26.05";
    } extra ];
  }).config;
  home = c: c.home-manager.users.demo;
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
  externalGtk = example { home-manager.users.demo.gtk.theme.package = null; };
  noGit = example { services.icewine.shell.starship.git.enable = false; };
  ownTerminal = example {
    services.icewine.terminal.preset = null;
    services.icewine.applications.terminal = [ "custom-terminal" ];
    home-manager.backupFileExtension = "hm-bak";
    home-manager.users.demo.programs.kitty = {
      enable = true;
      settings.background = "#abcdef";
    };
  };
  ownShell = example { services.icewine.shell.enable = false; };
  customised = example {
    home-manager.users.demo.services.hypridle.settings.listener = [ { timeout = 42; on-timeout = "true"; } ];
    home-manager.users.demo.services.batsignal.extraArgs = [ "-w" "25" ];
    home-manager.users.demo.programs.yazi.theme.mode.normal_main.fg = "#112233";
    home-manager.users.demo.programs.fastfetch.settings.display.separator = "HOST";
    home-manager.users.demo.programs.starship.settings.format = "HOST";
    home-manager.users.demo.programs.kitty = {
      font = { name = "JetBrains Mono"; size = 12; };
      settings.background = "#112233";
      keybindings."ctrl+shift+t" = "new_tab";
      extraConfig = "foreground #445566";
    };
  };
  # Only replace the report executable; exercise Home Manager's real bashrc.
  startup = example {
    services.icewine.shell = { blesh.enable = false; starship.enable = false; };
    home-manager.users.demo.programs = {
      bash.enableCompletion = false;
      fastfetch.package = pkgs.writeShellScriptBin "fastfetch" "echo ICEWINE_FASTFETCH";
    };
  };
  bashrc = (home startup).home.file.".bashrc".source;
  themeAssets = import ../theme/bundle.nix { inherit pkgs; };
in
assert lib.all (package: lib.isDerivation package) externalGtk.environment.systemPackages;
assert !(home defaults).gtk.enable;
assert (home defaults).services.hypridle.enable;
assert (home defaults).services.batsignal.enable;
assert (home defaults).programs.yazi.enable;
assert (home defaults).programs.yazi.plugins ? mount;
assert lib.elem pkgs.ffmpegthumbnailer (home defaults).programs.yazi.extraPackages;
assert lib.elem pkgs._7zz (home defaults).programs.yazi.extraPackages;
assert defaults.services.gvfs.enable;
assert defaults.services.icewine.applications.fileManager == [ "icewine-terminal-exec" "yazi" ];
assert defaults.services.icewine.applications.editor == [ "nano" ];
assert lib.elem pkgs.nano defaults.environment.systemPackages;
assert (home defaults).home.sessionVariables.EDITOR == "nano";
assert !((home defaults).home.sessionVariables ? LS_COLORS);
assert (home defaults).xdg.dataFile ? "applications/uuctl.desktop";
assert !((home defaults).systemd.user.services ? waybar);
assert !(home unmanaged).gtk.enable;
assert !(home unmanaged).services.hypridle.enable;
assert !(home unmanaged).services.batsignal.enable;
assert !(home unmanaged).programs.yazi.enable;
assert !unmanaged.services.gvfs.enable;
assert !((home unmanaged).home.sessionVariables ? STARSHIP_CONFIG);
assert (home customised).programs.yazi.theme.mode.normal_main.fg == "#112233";
assert !(lib.hasInfix "fastfetch.jsonc" (home customised).programs.bash.initExtra);
assert (home customised).home.sessionVariables.STARSHIP_CONFIG != "${(home customised).xdg.configHome}/icewine/current/starship.toml";
assert (home customised).services.batsignal.extraArgs == [ "-w" "25" ];
assert (builtins.head (home customised).services.hypridle.settings.listener).timeout == 42;
assert (home defaults).programs.kitty.enable;
assert !((home defaults).home.sessionVariables ? ICEWINE_KITTY_PRESET);
assert (home defaults).programs.kitty.package != null;
assert (home defaults).xdg.configFile."kitty/kitty.conf".target
  == lib.removePrefix "${(home defaults).home.homeDirectory}/" "${(home defaults).xdg.configHome}/kitty/host.conf";
assert defaults.services.icewine.applications.terminal == [ "kitty" ];
assert (home defaults).programs.bash.enable;
assert (home defaults).programs.fastfetch.enable;
assert (home defaults).programs.fastfetch.package != null;
assert lib.elem pkgs.blesh (home defaults).home.packages;
assert (home defaults).programs.starship.enable;
assert (home defaults).home.sessionVariables.STARSHIP_CONFIG == "${(home defaults).xdg.configHome}/icewine/current/starship.toml";
assert !(home unmanaged).programs.kitty.enable;
assert (home unmanaged).home.sessionVariables.ICEWINE_KITTY_PRESET == "false";
assert !(home unmanaged).programs.bash.enable;
assert !(home unmanaged).programs.fastfetch.enable;
assert !(home unmanaged).programs.starship.enable;
assert !(lib.elem pkgs.blesh (home unmanaged).home.packages);
assert (home ownTerminal).programs.kitty.enable;
assert (home ownTerminal).programs.kitty.settings.background == "#abcdef";
assert ownTerminal.home-manager.backupFileExtension == "hm-bak";
assert (home ownTerminal).xdg.configFile."kitty/kitty.conf".target
  == lib.removePrefix "${(home ownTerminal).home.homeDirectory}/" "${(home ownTerminal).xdg.configHome}/kitty/kitty.conf";
assert (home ownTerminal).programs.bash.enable;
assert (home ownShell).programs.kitty.enable && !(home ownShell).programs.bash.enable;
assert (home bareShell).programs.bash.enable;
assert !(home bareShell).programs.fastfetch.enable;
assert !(home bareShell).programs.starship.enable;
assert !(lib.elem pkgs.blesh (home bareShell).home.packages);
assert (home customised).programs.kitty.font.size == 12;
assert (home customised).programs.kitty.settings.background == "#112233";
assert (home customised).xdg.configFile."kitty/kitty.conf".target
  == lib.removePrefix "${(home customised).home.homeDirectory}/" "${(home customised).xdg.configHome}/kitty/host.conf";
assert lib.hasInfix "font_size 12" (home customised).xdg.configFile."kitty/kitty.conf".text;
assert lib.hasInfix "background #112233" (home customised).xdg.configFile."kitty/kitty.conf".text;
assert lib.hasInfix "map ctrl+shift+t new_tab" (home customised).xdg.configFile."kitty/kitty.conf".text;
assert lib.hasInfix "foreground #445566" (home customised).xdg.configFile."kitty/kitty.conf".text;
pkgs.runCommand "icewine-terminal-checks" {
  nativeBuildInputs = [ pkgs.bashInteractive pkgs.git pkgs.starship pkgs.python3 ];
} ''
  # No interactive output in ordinary commands, including the SSH environment.
  output=$(BASH_ENV=${bashrc} bash --noprofile --norc -c 'echo COMMAND_OK')
  test "$output" = COMMAND_OK
  output=$(SSH_CONNECTION="127.0.0.1 1000 127.0.0.1 22" BASH_ENV=${bashrc} bash --noprofile --norc -c 'echo COMMAND_OK')
  test "$output" = COMMAND_OK
  output=$(BASH_ENV=${(home defaults).home.file.".bashrc".source} bash --noprofile --norc -c 'echo COMMAND_OK')
  test "$output" = COMMAND_OK
  # Interactive local/TTY and SSH sessions both run the report exactly once.
  output=$(bash --noprofile --rcfile ${bashrc} -ic 'unset HISTFILE' 2>/dev/null)
  test "$output" = ICEWINE_FASTFETCH
  output=$(SSH_CONNECTION="127.0.0.1 1000 127.0.0.1 22" bash --noprofile --rcfile ${bashrc} -ic 'unset HISTFILE' 2>/dev/null)
  test "$output" = ICEWINE_FASTFETCH

  # Check native Starship modules against a disposable Git repository.
  export STARSHIP_CACHE="$TMPDIR/starship"
  mkdir -p "$STARSHIP_CACHE"
  git init -q --initial-branch=icewine-check repo
  cd repo
  touch tracked
  git add tracked
  git -c user.name=Test -c user.email=test@example.invalid -c commit.gpgsign=false commit -qm initial
  touch untracked
  export HOME="$TMPDIR/home"
  export XDG_CONFIG_HOME="$HOME/.config"
  export XDG_STATE_HOME="$HOME/.local/state"
  export ICEWINE_THEME_ASSETS=${themeAssets}/share/icewine
  python3 ${../scripts/theme} init
  test -f "$XDG_CONFIG_HOME/icewine/current/kitty-base.conf"
  test -f "$XDG_CONFIG_HOME/yazi/keymap.toml"
  . "$XDG_CONFIG_HOME/icewine/current/ls-colors.sh"
  tokyo_colors="$LS_COLORS"
  python3 ${../scripts/theme} theme dracula
  . "$XDG_CONFIG_HOME/icewine/current/ls-colors.sh"
  test "$LS_COLORS" != "$tokyo_colors"
  prompt=$(STARSHIP_CONFIG="$XDG_CONFIG_HOME/icewine/current/starship.toml" starship prompt)
  case "$prompt" in *icewine-check*) ;; *) exit 1 ;; esac
  case "$prompt" in *'?'*) ;; *) exit 1 ;; esac
  export ICEWINE_THEME_GIT_ENABLE=false
  python3 ${../scripts/theme} apply
  prompt=$(STARSHIP_CONFIG="$XDG_CONFIG_HOME/icewine/current/starship.toml" starship prompt)
  case "$prompt" in *icewine-check*|*'?'*) exit 1 ;; esac
  touch "$out"
''
