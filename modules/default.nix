{ config, lib, pkgs, ... }:
let
  cfg = config.services.icewine;
  command = description: default: lib.mkOption {
    type = lib.types.listOf lib.types.str;
    inherit description default;
  };
  commands = {
    editor = cfg.applications.editor;
  } // lib.optionalAttrs (cfg.gaming.enable) {
    steam = cfg.applications.steam;
  };
  launchers = lib.mapAttrsToList (name: argv: pkgs.writeShellScriptBin "icewine-${name}" ''
    exec ${lib.escapeShellArgs argv} "$@"
  '') commands;
  quickshell = pkgs.callPackage ../quickshell/package.nix { };

in {
  imports = [ ./home.nix ./desktop.nix ./handheld.nix ./login.nix ];

  options.services.icewine = {
    enable = lib.mkEnableOption "Icewine desktop environment";
    user = lib.mkOption {
      type = lib.types.str;
      default = "";
      description = "Existing user who receives Icewine configuration and services.";
    };
    handheld.enable = lib.mkEnableOption "handheld shell, controller routing and on-screen keyboard";
    authenticationRequired = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Require PAM authentication to unlock the session.";
    };
    gtk.enable = lib.mkEnableOption "Icewine GTK styling" // { default = cfg.desktop.enable; };
    theme = lib.mkOption {
      type = lib.types.nullOr (lib.types.enum [ "tokyo-night" "dracula" "nord" "gruvbox-light" "gruvbox-dark"
        "catppuccin-latte" "catppuccin-frappe" "catppuccin-macchiato" "catppuccin-mocha" ]);
      default = null;
      description = "Optional Icewine theme policy. Null lets the user's CLI selection win; Catppuccin Mocha is the fallback.";
    };
    idle.enable = lib.mkEnableOption "Icewine idle locking and suspend" // { default = true; };
    battery.enable = lib.mkEnableOption "Icewine Quickshell battery warnings and sleep" // { default = true; };
    desktop.enable = lib.mkEnableOption "Hyprland desktop session with Icewine";
    terminal.enable = lib.mkEnableOption "Kitty terminal and defaults";
    texteditor.enable = lib.mkEnableOption "Nano text editor and defaults";
    filemanager.enable = lib.mkEnableOption "Yazi file manager and defaults";
    gaming.enable = lib.mkEnableOption "Steam and Gamescope (allows unfree)";
    flatpak.enable = lib.mkEnableOption "Flatpak support and Bazaar; prefer Flatpak Steam when gaming is enabled";
    shellExtras = {
      enable = lib.mkEnableOption "Starship and Fastfetch shell extras";
      git.enable = lib.mkEnableOption "Starship Git prompt modules" // { default = true; };
    };
    applications = {
      editor = command "Editor command used by compositor bindings." [ "nano" ];
      steam = command "Steam command used inside Gamescope."
        (if cfg.gaming.enable && cfg.flatpak.enable then [ "flatpak" "run" "com.valvesoftware.Steam" ]
         else if cfg.gaming.enable && !cfg.flatpak.enable then [ "steam" ] ++ lib.optional cfg.handheld.enable "-gamepadui"
         else [ ]);
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
        message = "Icewine application commands must be nonempty; supply a nonempty applications command."; }
      { assertion = lib.all (name: name != "" && lib.all (part: part != "" && part != "." && part != "..") (lib.splitString "/" name))
          (builtins.attrNames cfg.defaultFiles.config ++ builtins.attrNames cfg.defaultFiles.data);
        message = "Icewine defaultFiles keys must be relative paths without . or .. components."; }
      { assertion = lib.all (name: !(builtins.elem name [ "gtk-3.0/icewine" "gtk-4.0/icewine" "hypr/icewine" "hypr/hypridle-icewine" "kitty/icewine" "uwsm/icewine" "icewine/shell/icewine" "quickshell/icewine" "quickshell/modules" "quickshell/adapters" "quickshell/theme" "quickshell/DeckOverlay.qml" "quickshell/DeckMenu.js" ] || lib.hasPrefix "quickshell/icewine/" name
          || lib.any (link: lib.hasPrefix (link + "/") name) [ "gtk-3.0/icewine" "gtk-4.0/icewine" "hypr/icewine" "hypr/hypridle-icewine" "kitty/icewine" "uwsm/icewine" "icewine/shell/icewine" ]
          || lib.hasPrefix "quickshell/modules/" name || lib.hasPrefix "quickshell/adapters/" name
          || lib.hasPrefix "quickshell/theme/" name
          || builtins.elem name (map (module: "hypr/modules/${module}.lua")
            [ "Baseline" "LookAndFeel" "WindowPolicy" "DefaultApps" "Docking" "Deck" ])))
          (builtins.attrNames cfg.defaultFiles.config);
        message = "Icewine implementation is packaged; use Settings.qml or native entry-point overrides for customization."; }
    ];

    programs.steam.enable = lib.mkIf (cfg.gaming.enable && !cfg.flatpak.enable) true;
    nixpkgs.config.allowUnfreePackages = lib.optionals (cfg.gaming.enable && !cfg.flatpak.enable)
      [ "steam" "steam-unwrapped" ];
    services.flatpak = lib.mkIf cfg.flatpak.enable {
      enable = true;
      remotes = [ { name = "flathub"; location = "https://dl.flathub.org/repo/flathub.flatpakrepo"; } ];
      packages = lib.optional cfg.gaming.enable "com.valvesoftware.Steam";
    };

    programs.hyprland = lib.mkIf cfg.desktop.enable { enable = true; withUWSM = true; };
    programs.dconf.enable = lib.mkIf cfg.gtk.enable (lib.mkDefault true);
    environment.sessionVariables.XDG_DATA_DIRS = lib.mkIf cfg.gtk.enable [
      "${pkgs.gsettings-desktop-schemas}/share/gsettings-schemas/${pkgs.gsettings-desktop-schemas.name}"
    ];
    xdg.portal = lib.mkIf cfg.gtk.enable {
      extraPortals = [ pkgs.xdg-desktop-portal-gtk ];
      config.hyprland."org.freedesktop.impl.portal.Settings" = [ "gtk" ];
    };
    security.pam.services.icewine = lib.mkIf cfg.desktop.enable { };
    security.polkit.enable = lib.mkIf cfg.desktop.enable true;
    services.pipewire = lib.mkIf cfg.desktop.enable {
      enable = true;
      alsa.enable = true;
      pulse.enable = true;
    };
    hardware.i2c.enable = lib.mkIf cfg.desktop.enable (lib.mkDefault true);
    services.upower.enable = lib.mkIf cfg.desktop.enable (lib.mkDefault true);
    services.power-profiles-daemon.enable = lib.mkIf cfg.desktop.enable (lib.mkDefault true);

    services.gvfs.enable = lib.mkIf (cfg.filemanager.enable) (lib.mkDefault true);

    fonts.packages = with pkgs; [ dejavu_fonts nerd-fonts.jetbrains-mono noto-fonts-color-emoji ];
    environment.systemPackages = (with pkgs; [ quickshell glib jq systemd libnotify libcanberra-gtk3
      adwaita-icon-theme papirus-icon-theme brightnessctl xdg-utils gtk3 ]) ++ launchers
      ++ lib.optionals cfg.desktop.enable (with pkgs; [ hyprshutdown hyprpolkitagent hyprshot hypridle xdg-terminal-exec ])
      ++ lib.optional cfg.gaming.enable pkgs.gamescope
      ++ lib.optional cfg.flatpak.enable pkgs.bazaar
      ++ lib.optional cfg.gtk.enable pkgs.gsettings-desktop-schemas;
    users.users.${cfg.user}.packages = lib.optional cfg.terminal.enable pkgs.kitty
      ++ lib.optional cfg.texteditor.enable pkgs.nano
      ++ lib.optionals cfg.shellExtras.enable [ pkgs.starship pkgs.fastfetch ];
  };
}
