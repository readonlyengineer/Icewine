{ config, lib, pkgs, ... }:
let
  cfg = config.services.icewine;
  command = description: default: lib.mkOption {
    type = lib.types.listOf lib.types.str;
    inherit description default;
  };
  commands = {
    terminal = cfg.applications.terminal;
    terminal-exec = cfg.applications.terminalExecute;
    editor = cfg.applications.editor;
    browser = cfg.applications.browser;
    file-manager = cfg.applications.fileManager;
    steam = cfg.applications.steam;
  };
  launchers = lib.mapAttrsToList (name: argv: pkgs.writeShellScriptBin "icewine-${name}" ''
    exec ${lib.escapeShellArgs argv} "$@"
  '') commands;
  screenshot = pkgs.writeShellApplication {
    name = "icewine-screenshot";
    runtimeInputs = with pkgs; [ coreutils grim grimblast wl-clipboard libnotify xdg-user-dirs ];
    text = builtins.readFile ../scripts/screenshot;
  };
  quickshell = pkgs.callPackage ../quickshell/package.nix { };
  browserDefaults = pkgs.writeTextDir "share/applications/mimeapps.list" ''
    [Default Applications]
    x-scheme-handler/http=firefox.desktop;
    x-scheme-handler/https=firefox.desktop;
    text/html=firefox.desktop;
    application/xhtml+xml=firefox.desktop;
    application/pdf=firefox.desktop;
  '';
in {
  imports = [ ./home.nix ./desktop.nix ./shell.nix ./handheld.nix ./login.nix ];

  options.services.icewine = {
    enable = lib.mkEnableOption "Icewine desktop environment";
    user = lib.mkOption {
      type = lib.types.str;
      default = "";
      description = "Existing user who receives Icewine configuration and services.";
    };
    handheld.enable = lib.mkEnableOption "handheld shell, controller routing and on-screen keyboard";
    browser.enable = lib.mkEnableOption "Icewine's native Firefox browser" // { default = true; };
    steam.enable = lib.mkEnableOption "Steam (Gamescope) launcher and ordinary Steam entry hiding" // {
      default = cfg.handheld.enable;
    };
    authenticationRequired = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Require PAM authentication to unlock the session.";
    };
    gtk.enable = lib.mkEnableOption "Icewine GTK styling" // { default = true; };
    theme = lib.mkOption {
      type = lib.types.nullOr (lib.types.enum [ "tokyo-night" "dracula" "nord" "gruvbox-light" "gruvbox-dark"
        "catppuccin-latte" "catppuccin-frappe" "catppuccin-macchiato" "catppuccin-mocha" ]);
      default = null;
      description = "Optional Icewine theme policy. Null lets the user's CLI selection win; Catppuccin Mocha is the fallback.";
    };
    idle.enable = lib.mkEnableOption "Icewine idle locking and suspend" // { default = true; };
    battery.enable = lib.mkEnableOption "Icewine Quickshell battery warnings and sleep" // { default = true; };
    fileManager.preset = lib.mkOption {
      type = lib.types.nullOr (lib.types.enum [ "yazi" ]);
      default = "yazi";
      description = "File manager to install and configure; null leaves it to the host.";
    };
    terminal.preset = lib.mkOption {
      type = lib.types.nullOr (lib.types.enum [ "kitty" ]);
      default = "kitty";
      description = "Terminal to install and configure; null leaves terminal management to the host.";
    };
    shell = {
      enable = lib.mkEnableOption "Icewine's interactive Bash configuration" // { default = true; };
      fastfetch.enable = lib.mkEnableOption "the Icewine Fastfetch report at interactive Bash startup" // { default = true; };
      blesh.enable = lib.mkEnableOption "ble.sh interactive Bash editing" // { default = true; };
      starship.enable = lib.mkEnableOption "the Icewine Starship prompt" // { default = true; };
      starship.git.enable = lib.mkEnableOption "Starship's default Git prompt modules" // { default = true; };
    };
    applications = {
      browser = command "Browser command; supplied by Firefox, or specified by the host." (lib.optional cfg.browser.enable "firefox");
      terminal = command "Terminal command; supplied by the preset, or installed and specified by the host." (lib.optional (cfg.terminal.preset == "kitty") "kitty");
      terminalExecute = command "Terminal command prefix for running an application." (cfg.applications.terminal ++ [ "-e" ]);
      editor = command "Editor command used by compositor bindings." [ "nano" ];
      fileManager = command "File manager command." (if cfg.fileManager.preset == "yazi" then [ "icewine-terminal-exec" "yazi" ] else [ "xdg-open" "." ]);
      steam = command "Steam command used inside Gamescope; installed by handheld mode or the host." ([ "steam" ] ++ lib.optional cfg.handheld.enable "-gamepadui");
    };
    defaultFiles = {
      config = lib.mkOption {
        type = lib.types.attrsOf lib.types.path;
        default = { };
        description = "Host-owned editable defaults under XDG_CONFIG_HOME.";
      };
      data = lib.mkOption {
        type = lib.types.attrsOf lib.types.path;
        default = { };
        description = "Host-owned editable defaults under XDG_DATA_HOME.";
      };
    };
  };

  config = lib.mkIf cfg.enable {
    assertions = [
      { assertion = cfg.user != "" && builtins.hasAttr cfg.user config.users.users;
        message = "Icewine requires services.icewine.user to name an existing user."; }
      { assertion = lib.all (argv: argv != [ ] && builtins.head argv != "") (builtins.attrValues commands);
        message = "Icewine application commands must be nonempty; set the corresponding applications command when disabling its managed preset."; }
      { assertion = lib.all (name: name != "" && lib.all (part: part != "" && part != "." && part != "..") (lib.splitString "/" name))
          (builtins.attrNames cfg.defaultFiles.config ++ builtins.attrNames cfg.defaultFiles.data);
        message = "Icewine defaultFiles keys must be relative paths without . or .. components."; }
      { assertion = lib.all (name: !(builtins.elem name [ "gtk-3.0/icewine" "gtk-4.0/icewine" "hypr/icewine" "hypr/hypridle-icewine" "nvim/icewine" "kitty/icewine" "uwsm/icewine" "icewine/shell/icewine" "quickshell/icewine" "quickshell/modules" "quickshell/adapters" "quickshell/theme" "quickshell/DeckOverlay.qml" "quickshell/DeckMenu.js" ] || lib.hasPrefix "quickshell/icewine/" name
          || lib.any (link: lib.hasPrefix (link + "/") name) [ "gtk-3.0/icewine" "gtk-4.0/icewine" "hypr/icewine" "hypr/hypridle-icewine" "nvim/icewine" "kitty/icewine" "uwsm/icewine" "icewine/shell/icewine" ]
          || lib.hasPrefix "quickshell/modules/" name || lib.hasPrefix "quickshell/adapters/" name
          || lib.hasPrefix "quickshell/theme/" name
          || builtins.elem name (map (module: "hypr/modules/${module}.lua")
            [ "Baseline" "LookAndFeel" "WindowPolicy" "DefaultApps" "Docking" "Deck" ])))
          (builtins.attrNames cfg.defaultFiles.config);
        message = "Icewine implementation is packaged; use Settings.qml, Binds.lua, Autostart.lua or entry-point/host hooks for customization."; }
    ];

    programs.hyprland = { enable = true; withUWSM = true; };
    programs.dconf.enable = lib.mkIf cfg.gtk.enable (lib.mkDefault true);
    xdg.portal = lib.mkIf cfg.gtk.enable {
      extraPortals = [ pkgs.xdg-desktop-portal-gtk ];
      config.hyprland."org.freedesktop.impl.portal.Settings" = [ "gtk" ];
    };
    programs.firefox.enable = lib.mkDefault cfg.browser.enable;
    security.pam.services.icewine = { };
    security.polkit.enable = true;
    services.pipewire = {
      enable = true;
      alsa.enable = true;
      pulse.enable = true;
    };
    hardware.i2c.enable = lib.mkDefault true;
    services.upower.enable = lib.mkDefault true;
    services.power-profiles-daemon.enable = lib.mkDefault true;

    services.gvfs.enable = lib.mkIf (cfg.fileManager.preset == "yazi") (lib.mkDefault true);

    fonts.packages = with pkgs; [ dejavu_fonts nerd-fonts.jetbrains-mono noto-fonts-color-emoji rubik ];
    environment.systemPackages = (with pkgs; [
      quickshell hyprshutdown hyprpolkitagent glib jq nano systemd
      grim slurp wl-clipboard libnotify libcanberra-gtk3
      adwaita-icon-theme papirus-icon-theme brightnessctl
      bluetui impala wiremix btop xdg-utils gamescope
    ]) ++ launchers ++ [ screenshot ] ++ lib.optional cfg.gtk.enable pkgs.gsettings-desktop-schemas;
    users.users.${cfg.user}.packages = lib.optional cfg.browser.enable browserDefaults
      ++ lib.optional (cfg.terminal.preset == "kitty") pkgs.kitty;
  };
}
