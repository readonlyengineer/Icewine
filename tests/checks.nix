{ self, nixpkgs }:
let
  pkgs = nixpkgs.legacyPackages.x86_64-linux;
  lib = nixpkgs.lib;
  example = handheld: nixpkgs.lib.nixosSystem {
    system = "x86_64-linux";
    modules = [ self.nixosModules.default {
      users.users.demo.isNormalUser = true;
      users.users.other.isNormalUser = true;
      nixpkgs.config.allowUnfreePredicate = pkg:
        builtins.elem (nixpkgs.lib.getName pkg) [ "steam" "steam-unwrapped" "steam-run" ];
      services.icewine = {
        enable = true;
        user = "demo";
        handheld.enable = handheld;
        defaultFiles.config."hypr/modules/host.lua" = ../hyprland/modules/Autostart.lua;
        defaultFiles.config."hypr/modules/Autostart.lua" = ../hyprland/modules/Baseline.lua;
      };
      system.stateVersion = "26.05";
    } ];
  };
  desktopSystem = example false;
  handheldSystem = example true;
  desktop = desktopSystem.config;
  handheld = handheldSystem.config;
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
  binaryFirefox = (desktopSystem.extendModules {
    modules = [ {
      programs.firefox.package = (import nixpkgs {
        system = "x86_64-linux";
        config.allowUnfreePredicate = package:
          lib.removeSuffix "-unwrapped" (lib.getName package) == "firefox-bin";
      }).firefox-bin;
    } ];
  }).config;
  unpatchedFirefox = (desktopSystem.extendModules {
    modules = [ { programs.firefox.package = pkgs.firefox.override { hasMozSystemDirPatch = false; }; } ];
  }).config;
  steamOptOut = (handheldSystem.extendModules {
    modules = [ { services.icewine.steam.enable = false; } ];
  }).config;
  quickshell = pkgs.quickshell.overrideAttrs (old: {
    buildInputs = old.buildInputs ++ [ pkgs.qt6.qtvirtualkeyboard ];
  });
  sddmTheme = pkgs.callPackage ../sddm { };
  icewineCli = builtins.head (lib.filter
    (package: lib.getName package == "icewine") desktop.users.users.demo.packages);
  handheldCli = builtins.head (lib.filter
    (package: lib.getName package == "icewine") handheld.users.users.demo.packages);
  steamEntryPackage = builtins.head (lib.filter
    (package: lib.getName package == "icewine-steam-desktop-entries") handheld.users.users.demo.packages);
  mimePackage = builtins.head (lib.filter
    (package: lib.getName package == "mimeapps.list") desktop.users.users.demo.packages);
  hasPackage = name: packages: lib.any (package: lib.getName package == name) packages;
  browserHost = import ../theme/browser.nix { inherit pkgs; };
  steamShortcuts = import ../quickshell/tools/steam-shortcuts.nix { inherit pkgs; };
in {
  screenshot = pkgs.runCommand "icewine-screenshot-checks" {
    nativeBuildInputs = [ pkgs.bash pkgs.coreutils ];
  } ''
    bash ${./screenshot.sh} ${../scripts/screenshot}
    touch "$out"
  '';
  brightness = pkgs.runCommand "icewine-brightness-checks" {
    nativeBuildInputs = [ pkgs.bash pkgs.coreutils pkgs.python3 pkgs.shellcheck pkgs.jq pkgs.util-linux ];
  } ''
    shellcheck ${../quickshell/tools/monitor-brightness}
    python3 ${./brightness.py} ${../quickshell/tools/monitor-brightness}
    touch "$out"
  '';
  controls = pkgs.runCommand "icewine-control-checks" {
    nativeBuildInputs = [ pkgs.nodejs pkgs.python3 quickshell pkgs.qt6.qtdeclarative ];
  } ''
    python3 ${./controls.py} ${self}
    python3 ${./render-ready.py} ${self}
    python3 ${./theme-live.py} ${self}
    python3 ${./sddm-palette.py} ${sddmTheme}/share/sddm/themes/icewine/theme/Palette.qml \
      ${pkgs.qt6.qtdeclarative}/bin/qml ${pkgs.qt6.qtdeclarative}/lib/qt-6/qml
    touch "$out"
  '';
  terminal = import ./terminal.nix { inherit self nixpkgs; };
  logic = pkgs.runCommand "icewine-logic-checks" {
    nativeBuildInputs = [ pkgs.nodejs pkgs.lua (pkgs.python3.withPackages (python: [ python.vdf ])) ];
  } ''
    cd ${self}
    for test in quickshell/tests/*.js quickshell/deck/test-demo.js; do node "$test"; done
    lua hyprland/tests/docking.lua hyprland/modules/Docking.lua
    lua hyprland/tests/workspace-navigation.lua hyprland/modules/Binds.lua
    lua hyprland/tests/steam.lua
    lua hyprland/tests/window-policy.lua hyprland/modules/WindowPolicy.lua
    python3 tests/theme-cli.py scripts/theme scripts/icewine theme/assets
    touch "$out"
  '';
  wallpaper = pkgs.runCommand "icewine-wallpaper-checks" {
    nativeBuildInputs = [ pkgs.bash pkgs.coreutils pkgs.nodejs quickshell icewineCli ];
  } ''
    cd ${self}
    node quickshell/tests/wallpaper.js
    bash tests/wallpaper-selector.sh ${icewineCli}/bin/icewine
    touch "$out"
  '';
  modules =
    assert desktop.services.icewine.applications.steam == [ "steam" ];
    assert handheld.services.icewine.applications.steam == [ "steam" "-gamepadui" ];
    assert steamDesktop.services.icewine.applications.steam == [ "flatpak" "run" "com.valvesoftware.Steam" ];
    assert !(hasPackage "icewine-steam-desktop-entries" desktop.users.users.demo.packages);
    assert !(hasPackage "icewine-steam-desktop-entries" steamOptOut.users.users.demo.packages);
    assert hasPackage "icewine-steam-desktop-entries" steamDesktop.users.users.demo.packages;
    assert hasPackage "icewine-steam-desktop-entries" handheld.users.users.demo.packages;
    assert !steamDesktop.programs.steam.enable;
    assert desktop.programs.firefox.enable;
    assert hasPackage "icewine-pywalfox" desktop.users.users.demo.packages;
    assert hasPackage "icewine-pywalfox" desktop.programs.firefox.nativeMessagingHosts.packages;
    assert !(hasPackage "icewine-pywalfox" desktop.users.users.other.packages);
    assert !(hasPackage "icewine-pywalfox" unmanaged.users.users.demo.packages);
    assert !(hasPackage "icewine-pywalfox" disabled.users.users.demo.packages);
    assert unmanaged.programs.firefox.nativeMessagingHosts.packages == [ ];
    assert binaryFirefox.programs.firefox.nativeMessagingHosts.packages == [ ];
    assert unpatchedFirefox.programs.firefox.nativeMessagingHosts.packages == [ ];
    assert hasPackage "icewine-pywalfox" binaryFirefox.users.users.demo.packages;
    assert hasPackage "icewine-pywalfox" unpatchedFirefox.users.users.demo.packages;
    assert desktop.xdg.mime.defaultApplications == { };
    assert hasPackage "mimeapps.list" desktop.users.users.demo.packages;
    assert !(hasPackage "mimeapps.list" desktop.users.users.other.packages);
    assert !desktop.services.flatpak.enable;
    assert !unmanaged.programs.firefox.enable;
    assert !unmanaged.services.flatpak.enable;
    assert !(hasPackage "mimeapps.list" unmanaged.users.users.demo.packages);
    assert unmanaged.services.icewine.applications.browser == [ "custom-browser" ];
    assert !disabled.services.flatpak.enable;
    assert lib.all (c:
      c.services.displayManager.sddm.enable
      && c.services.xserver.enable
      && !c.services.displayManager.sddm.wayland.enable
      && c.services.displayManager.sddm.theme == "icewine"
      && c.services.displayManager.defaultSession == "hyprland-uwsm"
      && !c.services.displayManager.autoLogin.enable
    ) [ desktop handheld ];
    assert !noLogin.services.displayManager.sddm.enable;
    assert !noLogin.services.xserver.enable;
    assert !disabled.services.displayManager.sddm.enable;
    assert !disabled.services.xserver.enable;
    assert lib.elem pkgs.btop desktop.environment.systemPackages;
    assert lib.elem desktopSystem.pkgs.gamescope desktop.environment.systemPackages;
    assert lib.elem handheldSystem.pkgs.gamescope handheld.environment.systemPackages;
    assert desktop.systemd.user.services ? icewine;
    assert desktop.systemd.user.services.icewine.unitConfig.ConditionUser == "demo";
    assert lib.elem "QT_IM_MODULE=qtvirtualkeyboard" desktop.systemd.user.services.icewine.serviceConfig.Environment;
    assert !(desktop.systemd.user.services ? icewine-inputplumber-hyprland);
    assert handheld.systemd.user.services ? icewine-inputplumber-hyprland;
    assert handheld.systemd.user.services ? icewine-keyboard;
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
      export HOME=$TMPDIR/home XDG_CONFIG_HOME=$TMPDIR/home/.config XDG_DATA_HOME=$TMPDIR/home/.local/share XDG_STATE_HOME=$TMPDIR/home/.local/state
      mkdir -p "$HOME"
      ${icewineCli}/bin/icewine init
      test "$(${steamShortcuts}/bin/icewine-steam-shortcuts)" = '[]'
      PYTHONPATH=${pkgs.pywalfox-native}/${pkgs.python3.sitePackages} ${pkgs.python3}/bin/python3 ${./browser-upstream.py} ${browserHost}/lib/mozilla/native-messaging-hosts/pywalfox.json
      cmp ${../hyprland/modules/Autostart.lua} "$XDG_CONFIG_HOME/hypr/modules/host.lua"
      cmp ${../hyprland/modules/Baseline.lua} "$XDG_CONFIG_HOME/hypr/modules/Autostart.lua"
      test ! -e "$XDG_CONFIG_HOME/hypr/modules/Deck.lua"
      cmp ${../hyprland/hyprland.lua} "$XDG_CONFIG_HOME/hypr/hyprland.lua"
      test -L "$XDG_CONFIG_HOME/hypr/modules/Theme.lua"
      test ! -e "$XDG_CONFIG_HOME/hypr/tests"
      export HOME=$TMPDIR/handheld XDG_CONFIG_HOME=$TMPDIR/handheld/.config XDG_DATA_HOME=$TMPDIR/handheld/.local/share XDG_STATE_HOME=$TMPDIR/handheld/.local/state
      mkdir -p "$HOME"
      ${handheldCli}/bin/icewine init
      grep -Fx 'Icon=steam' ${steamEntryPackage}/share/applications/steam-gamescope.desktop
      grep -Fx 'Hidden=true' "$XDG_DATA_HOME/applications/steam.desktop"
      grep -Fx 'Hidden=true' "$XDG_DATA_HOME/applications/com.valvesoftware.Steam.desktop"
      test ! -e ${steamEntryPackage}/share/applications/steam.desktop
      grep -Fx 'application/pdf=firefox.desktop;' ${mimePackage}/share/applications/mimeapps.list
      test ! -e "$XDG_DATA_HOME/applications/steam-gamescope.desktop"
      test -f "$XDG_CONFIG_HOME/hypr/modules/Deck.lua"
      { cat ${../hyprland/hyprland.lua}; printf '\nrequire("modules.Deck")\n'; } > "$TMPDIR/handheld-hyprland.lua"
      cmp "$TMPDIR/handheld-hyprland.lua" "$XDG_CONFIG_HOME/hypr/hyprland.lua"
      cmp ${../hyprland/modules/Autostart.lua} "$XDG_CONFIG_HOME/hypr/modules/host.lua"
      cmp ${../hyprland/modules/Baseline.lua} "$XDG_CONFIG_HOME/hypr/modules/Autostart.lua"
      cmp ${../quickshell/deck/shell.qml} "$XDG_CONFIG_HOME/quickshell/shell.qml"
      touch "$out"
    '';
}
