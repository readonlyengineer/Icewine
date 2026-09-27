{ self, nixpkgs }:
let
  pkgs = nixpkgs.legacyPackages.x86_64-linux;
  example = handheld: nixpkgs.lib.nixosSystem {
    system = "x86_64-linux";
    modules = [ self.nixosModules.default {
      users.users.demo.isNormalUser = true;
      nixpkgs.config.allowUnfreePredicate = pkg:
        builtins.elem (nixpkgs.lib.getName pkg) [ "steam" "steam-unwrapped" "steam-run" ];
      services.icewine = {
        enable = true;
        user = "demo";
        handheld.enable = handheld;
        hyprland.extraModules."host.lua" = ../hyprland/modules/Autostart.lua;
      };
      system.stateVersion = "26.05";
    } ];
  };
  desktopSystem = example false;
  desktop = desktopSystem.config;
  noLogin = (desktopSystem.extendModules {
    modules = [ { services.icewine.login.enable = false; } ];
  }).config;
  disabled = (desktopSystem.extendModules {
    modules = [ { services.icewine.enable = nixpkgs.lib.mkForce false; } ];
  }).config;
  unmanaged = (desktopSystem.extendModules {
    modules = [ {
      services.icewine.browser.enable = false;
      services.icewine.applications.browser = [ "custom-browser" ];
    } ];
  }).config;
  steamDesktop = (desktopSystem.extendModules {
    modules = [ {
      services.icewine.steam.enable = true;
      services.icewine.applications.steam = [ "flatpak" "run" "com.valvesoftware.Steam" ];
    } ];
  }).config;
  steamOptOut = (handheldSystem.extendModules {
    modules = [ { services.icewine.steam.enable = false; } ];
  }).config;
  nativeBrowserMatches = c:
    c.programs.firefox.enable
    && c.services.icewine.applications.browser == [ "firefox" ]
    && (home c).xdg.mimeApps.enable
    && nixpkgs.lib.all (mime:
      (home c).xdg.mimeApps.defaultApplications.${mime} == [ "firefox.desktop" ]
    ) [ "x-scheme-handler/http" "x-scheme-handler/https" "text/html" "application/xhtml+xml" "application/pdf" ];
  handheldSystem = example true;
  handheld = handheldSystem.config;
  home = c: c.home-manager.users.demo;
  quickshell = pkgs.quickshell.overrideAttrs (old: {
    buildInputs = old.buildInputs ++ [ pkgs.qt6.qtvirtualkeyboard ];
  });
in {
  screenshot = pkgs.runCommand "icewine-screenshot-checks" {
    nativeBuildInputs = [ pkgs.bash pkgs.coreutils ];
  } ''
    bash ${./screenshot.sh} ${../scripts/screenshot}
    touch "$out"
  '';
  brightness = pkgs.runCommand "icewine-brightness-checks" {
    nativeBuildInputs = [ pkgs.bash pkgs.coreutils pkgs.python3 pkgs.shellcheck ];
  } ''
    shellcheck ${../quickshell/tools/monitor-brightness}
    python3 ${./brightness.py} ${../quickshell/tools/monitor-brightness}
    touch "$out"
  '';
  controls = pkgs.runCommand "icewine-control-checks" {
    nativeBuildInputs = [ pkgs.nodejs pkgs.python3 quickshell ];
  } ''
    python3 ${./controls.py} ${self}
    python3 ${./render-ready.py} ${self}
    touch "$out"
  '';
  terminal = import ./terminal.nix { inherit self nixpkgs; };
  logic = pkgs.runCommand "icewine-logic-checks" {
    nativeBuildInputs = [ pkgs.nodejs pkgs.lua ];
  } ''
    cd ${self}
    for test in quickshell/tests/*.js quickshell/deck/test-demo.js; do node "$test"; done
    lua hyprland/tests/docking.lua hyprland/modules/Docking.lua
    lua hyprland/tests/workspace-navigation.lua hyprland/modules/Binds.lua
    lua hyprland/tests/steam.lua
    lua hyprland/tests/window-policy.lua hyprland/modules/WindowPolicy.lua
    touch "$out"
  '';
  modules =
    assert desktop.services.icewine.applications.steam == [ "steam" ];
    assert handheld.services.icewine.applications.steam == [ "steam" "-gamepadui" ];
    assert steamDesktop.services.icewine.applications.steam == [ "flatpak" "run" "com.valvesoftware.Steam" ];
    assert !((home desktop).xdg.desktopEntries ? steam-gamescope);
    assert !((home steamOptOut).xdg.desktopEntries ? steam-gamescope);
    assert !((home steamOptOut).xdg.dataFile ? "applications/steam.desktop");
    assert !steamDesktop.programs.steam.enable;
    assert (home steamDesktop).xdg.desktopEntries.steam-gamescope.icon == "com.valvesoftware.Steam";
    assert (home handheld).xdg.desktopEntries.steam-gamescope.icon == "steam";
    assert nixpkgs.lib.all (c:
      (home c).xdg.desktopEntries.steam-gamescope.exec
        == "${pkgs.quickshell}/bin/qs ipc call gameLauncher launchSteamGamescope"
      && (home c).xdg.dataFile."applications/steam.desktop".text
        == (home c).xdg.dataFile."applications/com.valvesoftware.Steam.desktop".text
      && nixpkgs.lib.hasInfix "Hidden=true" (home c).xdg.dataFile."applications/steam.desktop".text
    ) [ steamDesktop handheld ];
    assert nativeBrowserMatches desktop;
    assert !desktop.services.flatpak.enable;
    assert !unmanaged.programs.firefox.enable;
    assert !unmanaged.services.flatpak.enable;
    assert !(home unmanaged).xdg.mimeApps.enable;
    assert unmanaged.services.icewine.applications.browser == [ "custom-browser" ];
    assert !disabled.services.flatpak.enable;
    assert nixpkgs.lib.all (config:
      config.services.displayManager.sddm.enable
      && config.services.xserver.enable
      && !config.services.displayManager.sddm.wayland.enable
      && config.services.displayManager.sddm.theme == "icewine"
      && config.services.displayManager.defaultSession == "hyprland-uwsm"
      && !config.services.displayManager.autoLogin.enable
    ) [ desktop handheld ];
    assert !noLogin.services.displayManager.sddm.enable;
    assert !noLogin.services.xserver.enable;
    assert !disabled.services.displayManager.sddm.enable;
    assert !disabled.services.xserver.enable;
    assert nixpkgs.lib.elem pkgs.btop desktop.environment.systemPackages;
    assert nixpkgs.lib.elem desktopSystem.pkgs.gamescope desktop.environment.systemPackages;
    assert desktop.home-manager.users.demo.home.stateVersion == "26.05";
    assert nixpkgs.lib.elem handheldSystem.pkgs.gamescope handheld.environment.systemPackages;
    assert (home desktop).xdg.configFile."hypr".recursive;
    assert (home handheld).xdg.configFile."hypr".recursive;
    assert (home desktop).systemd.user.services ? icewine;
    assert nixpkgs.lib.elem "QT_IM_MODULE=qtvirtualkeyboard"
      (home desktop).systemd.user.services.icewine.Service.Environment;
    assert !((home desktop).systemd.user.services ? quickshell);
    assert !((home desktop).systemd.user.services ? icewine-inputplumber-hyprland);
    assert (home handheld).systemd.user.services ? icewine-inputplumber-hyprland;
    assert (home handheld).systemd.user.services ? icewine-keyboard;
    assert desktop.hardware.i2c.enable;
    assert desktop.security.pam.services ? icewine;
    assert handheld.services.icewine.authenticationRequired;
    assert handheld.programs.steam.enable;
    assert handheld.services.inputplumber.enable;
    assert !desktop.programs.steam.enable;
    assert !desktop.services.inputplumber.enable;
    assert !disabled.programs.steam.enable;
    assert !disabled.services.inputplumber.enable;
    assert !handheld.services.openssh.enable;
    assert !desktop.networking.networkmanager.enable;
    pkgs.runCommand "icewine-module-checks" { } ''
      test ! -e ${((home desktop).xdg.configFile."hypr").source}/tests
      test ! -e ${((home handheld).xdg.configFile."hypr").source}/tests
      test -f ${((home desktop).xdg.configFile."hypr").source}/modules/Theme.lua
      cmp ${../hyprland/modules/Autostart.lua} ${((home desktop).xdg.configFile."hypr").source}/modules/host.lua
      test ! -e ${((home desktop).xdg.configFile."hypr").source}/modules/Deck.lua
      test -f ${((home handheld).xdg.configFile."hypr").source}/modules/Deck.lua
      touch "$out"
    '';
}
