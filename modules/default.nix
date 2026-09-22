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
    browser = cfg.applications.browser;
    browser-home = cfg.applications.browserHome;
    editor = cfg.applications.editor;
    file-manager = cfg.applications.fileManager;
    steam = cfg.applications.steam;
  };
  launchers = lib.mapAttrsToList (name: argv: pkgs.writeShellScriptBin "icewine-${name}" ''
    exec ${lib.escapeShellArgs argv} "$@"
  '') commands;
  screenshot = pkgs.writeShellApplication {
    name = "icewine-screenshot";
    runtimeInputs = with pkgs; [ coreutils grim slurp wl-clipboard libnotify xdg-user-dirs ];
    text = builtins.readFile ../scripts/screenshot;
  };
  bookmarks = pkgs.writeShellScriptBin "icewine-bookmarks" (
    if cfg.handheld.bookmarksCommand == [ ] then "printf '[]\\n'"
    else ''exec ${lib.escapeShellArgs cfg.handheld.bookmarksCommand} "$@"''
  );
in {
  imports = [ ./handheld.nix ];

  options.services.icewine = {
    enable = lib.mkEnableOption "Icewine desktop environment";
    user = lib.mkOption {
      type = lib.types.str;
      default = "";
      description = "Existing user whose Home Manager configuration receives Icewine.";
    };
    handheld.enable = lib.mkEnableOption "handheld shell, controller routing and on-screen keyboard";
    handheld.bookmarksCommand = command "Optional command returning a JSON array of {label, url, iconSource?} bookmarks." [ ];
    authenticationRequired = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Require PAM authentication to unlock the session.";
    };
    gtk.enable = lib.mkEnableOption "Icewine GTK styling" // { default = true; };
    idle.enable = lib.mkEnableOption "Icewine idle locking and suspend" // { default = true; };
    battery.enable = lib.mkEnableOption "Icewine battery warnings and critical suspend" // { default = true; };
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
      terminal = command "Terminal command; supplied by the preset, or installed and specified by the host." (lib.optional (cfg.terminal.preset == "kitty") "kitty");
      terminalExecute = command "Terminal command prefix for running an application." (cfg.applications.terminal ++ [ "-e" ]);
      browser = command "Browser command; URLs are appended as a single argument." [ "xdg-open" ];
      browserHome = command "Browser command for opening the home page without a URL." cfg.applications.browser;
      editor = command "Editor command used by compositor bindings." [ "vi" ];
      fileManager = command "File manager command." (if cfg.fileManager.preset == "yazi" then [ "icewine-terminal-exec" "yazi" ] else [ "xdg-open" "." ]);
      steam = command "Steam command used inside Gamescope; installed by the host." [ "steam" ];
    };
    hyprland.extraModules = lib.mkOption {
      type = lib.types.attrsOf lib.types.path;
      default = { };
      description = "Host Lua files overlaid into Hyprland's modules directory, keyed by filename.";
    };
  };

  config = lib.mkIf cfg.enable {
    assertions = [
      { assertion = cfg.user != "" && builtins.hasAttr cfg.user config.users.users;
        message = "Icewine requires services.icewine.user to name an existing user."; }
      { assertion = lib.all (argv: argv != [ ] && builtins.head argv != "") (builtins.attrValues commands);
        message = "Icewine application commands must be nonempty; set applications.terminal and install it downstream."; }
      { assertion = lib.all (name: builtins.match "[A-Za-z0-9_-]+\\.lua" name != null) (builtins.attrNames cfg.hyprland.extraModules);
        message = "Icewine extraModules keys must be Lua filenames without directory components."; }
    ];

    programs.hyprland = { enable = true; withUWSM = true; };
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
      quickshell hyprshutdown hyprpolkitagent glib jq procps systemd
      grim slurp wl-clipboard libnotify libcanberra-gtk3
      adwaita-icon-theme papirus-icon-theme brightnessctl playerctl
      bluetui impala wiremix btop xdg-utils
    ]) ++ launchers ++ [ bookmarks screenshot ]
      ++ lib.optionals cfg.gtk.enable (lib.optional (config.home-manager.users.${cfg.user}.gtk.theme.package != null) config.home-manager.users.${cfg.user}.gtk.theme.package);

    home-manager.users.${cfg.user}.imports = [ ./home.nix ];
  };
}
