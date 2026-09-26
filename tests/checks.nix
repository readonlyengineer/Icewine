{ self, nixpkgs }:
let
  pkgs = nixpkgs.legacyPackages.x86_64-linux;
  example = handheld: nixpkgs.lib.nixosSystem {
    system = "x86_64-linux";
    modules = [ self.nixosModules.default {
      users.users.demo.isNormalUser = true;
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
  handheldSystem = example true;
  handheld = handheldSystem.config;
  home = c: c.home-manager.users.demo;
  quickshell = pkgs.quickshell.overrideAttrs (old: {
    buildInputs = old.buildInputs ++ [ pkgs.qt6.qtvirtualkeyboard ];
  });
in {
  gamescope-focus =
    assert pkgs.lib.all (system:
      pkgs.lib.count (patch:
        toString patch == toString ../patches/gamescope/preserve-keyboard-focus-state.patch
        || toString patch == toString ../patches/gamescope/dynamic-resolution.patch
      ) system.pkgs.gamescope.patches == 2
    ) [ desktopSystem handheldSystem ];
    pkgs.runCommand "icewine-gamescope-focus-check" {
      nativeBuildInputs = [ pkgs.python3 pkgs.stdenv.cc pkgs.patch ];
    } ''
      ${pkgs.lib.concatStringsSep "\n" (pkgs.lib.mapAttrsToList (name: system:
        let gamescope = system.pkgs.gamescope;
        in ''
          cp -R ${gamescope.src} ${name}
          chmod -R u+w ${name}
          cd ${name}
          ${pkgs.lib.concatMapStringsSep "\n" (patch: "patch -p1 < ${patch}") gamescope.patches}
          python3 ${../patches/gamescope/check-focus.py} .
          python3 ${../patches/gamescope/check-dynamic-resolution.py} .
          test -x ${gamescope}/bin/gamescope
          cd ..
        ''
      ) { desktop = desktopSystem; handheld = handheldSystem; })}
      touch "$out"
    '';
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
