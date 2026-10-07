{ self, nixpkgs }:
let
  pkgs = nixpkgs.legacyPackages.x86_64-linux;
  lib = nixpkgs.lib;
  example = handheld: nixpkgs.lib.nixosSystem {
    system = "x86_64-linux";
    modules = [ self.nixosModules.default {
      users.users.demo.isNormalUser = true;
      users.users.other.isNormalUser = true;
      services.icewine = {
        enable = true;
        user = "demo";
        handheld.enable = handheld;
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
      services.icewine.steam = "flatpak";
    } ];
  }).config;
  steamOptOut = (desktopSystem.extendModules {
    modules = [ { services.icewine.steam = "none"; } ];
  }).config;
  incompatibleHandheld = method: (handheldSystem.extendModules {
    modules = [ { services.icewine.steam = method; } ];
  }).config;
  hostPolicySystem = desktopSystem.extendModules {
    modules = [ {
      nixpkgs.config.allowUnfreePredicate = pkg: lib.getName pkg == "host-proprietary";
      nixpkgs.config.allowUnfreePackages = [ "host-listed" ];
    } ];
  };
  independent = (desktopSystem.extendModules {
    modules = [ {
      services.icewine.steam = "none";
      programs.steam.enable = true;
      nixpkgs.config.allowUnfreePackages = [ "steam" "steam-unwrapped" ];
      services.flatpak = {
        enable = true;
        packages = [ "com.valvesoftware.Steam" "org.videolan.VLC" ];
      };
    } ];
  }).config;
  quickshell = pkgs.callPackage ../quickshell/package.nix { };
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
    bash ${./monitor-capabilities.sh} ${../quickshell/tools/probe-monitor-capabilities}
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
    assert hasPackage "icewine-steam-desktop-entries" desktop.users.users.demo.packages;
    assert !(hasPackage "icewine-steam-desktop-entries" steamOptOut.users.users.demo.packages);
    assert hasPackage "icewine-steam-desktop-entries" steamDesktop.users.users.demo.packages;
    assert hasPackage "icewine-steam-desktop-entries" handheld.users.users.demo.packages;
    assert !steamDesktop.programs.steam.enable;
    assert desktop.services.icewine.steam == "native";
    assert lib.all desktopSystem.options.services.icewine.steam.type.check [ "native" "flatpak" "none" ];
    assert !desktopSystem.options.services.icewine.steam.type.check "invalid";
    assert lib.elem "ICEWINE_STEAM_ENABLED=false" steamOptOut.systemd.user.services.icewine.serviceConfig.Environment;
    assert lib.elem "ICEWINE_STEAM_ENABLED=true" desktop.systemd.user.services.icewine.serviceConfig.Environment;
    assert desktop.nixpkgs.config.allowUnfreePackages == [ "steam" "steam-unwrapped" ];
    assert !(desktop.nixpkgs.config.allowUnfree or false);
    assert steamDesktop.services.flatpak.enable;
    assert map (package: package.appId) steamDesktop.services.flatpak.packages == [ "com.valvesoftware.Steam" ];
    assert lib.any (remote: remote.name == "flathub") steamDesktop.services.flatpak.remotes;
    assert !steamDesktop.services.flatpak.uninstallUnmanaged;
    assert (steamDesktop.nixpkgs.config.allowUnfreePackages or [ ]) == [ ];
    assert steamOptOut.services.icewine.applications.steam == [ ];
    assert !steamOptOut.programs.steam.enable;
    assert !steamOptOut.services.flatpak.enable;
    assert (steamOptOut.nixpkgs.config.allowUnfreePackages or [ ]) == [ ];
    assert (disabled.nixpkgs.config.allowUnfreePackages or [ ]) == [ ];
    assert !(hasPackage "icewine-steam" steamOptOut.environment.systemPackages);
    assert !(hasPackage "icewine-steam" disabled.environment.systemPackages);
    assert hasPackage "icewine-steam" desktop.environment.systemPackages;
    assert hostPolicySystem.config.nixpkgs.config.allowUnfreePredicate { name = "host-proprietary"; };
    assert lib.elem "host-listed" hostPolicySystem.config.nixpkgs.config.allowUnfreePackages;
    assert lib.elem "steam" hostPolicySystem.config.nixpkgs.config.allowUnfreePackages;
    assert builtins.isString hostPolicySystem.pkgs.steam.drvPath;
    assert independent.programs.steam.enable;
    assert map (package: package.appId) independent.services.flatpak.packages == [ "com.valvesoftware.Steam" "org.videolan.VLC" ];
    assert lib.all (method: lib.any (a: !a.assertion && lib.hasInfix "handheld integration requires" a.message)
      (incompatibleHandheld method).assertions) [ "flatpak" "none" ];
    assert desktop.programs.firefox.enable;
    assert desktop.programs.firefox.nativeMessagingHosts.packages == [ ];
    assert unmanaged.programs.firefox.nativeMessagingHosts.packages == [ ];
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
    assert desktop.programs.steam.enable;
    assert !desktop.services.inputplumber.enable;
    assert !disabled.programs.steam.enable;
    assert !disabled.services.inputplumber.enable;
    assert !handheld.services.openssh.enable;
    assert !desktop.networking.networkmanager.enable;
    pkgs.runCommand "icewine-module-checks" { nativeBuildInputs = [ pkgs.lua ]; } ''
      export HOME=$TMPDIR/home XDG_CONFIG_HOME=$TMPDIR/home/.config XDG_DATA_HOME=$TMPDIR/home/.local/share XDG_STATE_HOME=$TMPDIR/home/.local/state
      mkdir -p "$HOME"
      ${icewineCli}/bin/icewine init
      test "$(${steamShortcuts}/bin/icewine-steam-shortcuts)" = '[]'
      test ! -e "$XDG_CONFIG_HOME/hypr/modules/Deck.lua"
      test -L "$XDG_CONFIG_HOME/quickshell/icewine"
      test -f "$XDG_CONFIG_HOME/quickshell/icewine/Desktop.qml"
      test ! -e "$XDG_CONFIG_HOME/quickshell/modules"
      cmp ${../hyprland/hyprland.lua} "$XDG_CONFIG_HOME/hypr/hyprland.lua"
      test ! -e "$XDG_CONFIG_HOME/hypr/modules/Theme.lua"
      test ! -e "$XDG_CONFIG_HOME/hypr/tests"
      implementation=$(dirname "$(readlink "$XDG_CONFIG_HOME/quickshell/icewine")")
      # Compare actual installed paths: individually interpolated Nix files or
      # directories copied into a directory retain their store-prefixed basename.
      for name in adapters/Hyprland.qml modules/Topbar.qml theme/qmldir theme/Palette.qml Desktop.qml Handheld.qml deck/DeckOverlay.qml deck/DeckMenu.js; do
        cmp ${../quickshell}/"$name" "$implementation/quickshell/$name"
      done
      cmp ${../nvim}/defaults.lua "$XDG_CONFIG_HOME/nvim/icewine/defaults.lua"
      cmp ${../bash}/bashrc "$XDG_CONFIG_HOME/icewine/shell/icewine/bashrc"
      cmp ${../session}/env "$XDG_CONFIG_HOME/uwsm/icewine/env"
      cmp ${../hypridle}/defaults.conf "$XDG_CONFIG_HOME/hypr/hypridle-icewine/defaults.conf"
      cmp ${../gtk}/defaults.css "$XDG_CONFIG_HOME/gtk-3.0/icewine/defaults.css"
      cmp ${../gtk}/defaults.css "$XDG_CONFIG_HOME/gtk-4.0/icewine/defaults.css"
      cmp ${../theme/assets/templates}/kitty-base.conf "$XDG_CONFIG_HOME/kitty/icewine/defaults.conf"
      grep -Fx 'include icewine/defaults.conf' "$XDG_CONFIG_HOME/kitty/kitty.conf"
      test ! -e "$XDG_CONFIG_HOME/kitty/host.conf"
      grep -Fx '@import url("../icewine/current/gtk.css");' "$XDG_CONFIG_HOME/gtk-3.0/gtk.css"
      grep -Fx '@import url("../icewine/current/gtk4.css");' "$XDG_CONFIG_HOME/gtk-4.0/gtk.css"
      cmp ${../hyprland}/icewine.lua "$implementation/hyprland/icewine.lua"
      for name in Baseline LookAndFeel WindowPolicy DefaultApps Docking Binds; do
        cmp ${../hyprland}/modules/"$name.lua" "$implementation/hyprland/modules/$name.lua"
      done
      cmp ${../hyprland}/deck/Deck.lua "$implementation/hyprland/modules/Deck.lua"
      # Runtime loaders accept an ordinary implementation root as well as Nix store paths.
      cp -r "$implementation" "$TMPDIR/portable-implementation"
      ln -sfn "$TMPDIR/portable-implementation/hyprland" "$XDG_CONFIG_HOME/hypr/icewine"
      unset ICEWINE_IMPLEMENTATION
      lua ${../hyprland/tests/startup.lua} "$XDG_CONFIG_HOME/hypr/hyprland.lua" desktop
      export HOME=$TMPDIR/handheld XDG_CONFIG_HOME=$TMPDIR/handheld/.config XDG_DATA_HOME=$TMPDIR/handheld/.local/share XDG_STATE_HOME=$TMPDIR/handheld/.local/state
      mkdir -p "$HOME"
      ${handheldCli}/bin/icewine init
      grep -Fx 'Icon=steam' ${steamEntryPackage}/share/applications/steam-gamescope.desktop
      grep -Fx 'Hidden=true' "$XDG_DATA_HOME/applications/steam.desktop"
      grep -Fx 'Hidden=true' "$XDG_DATA_HOME/applications/com.valvesoftware.Steam.desktop"
      test ! -e ${steamEntryPackage}/share/applications/steam.desktop
      grep -Fx 'application/pdf=firefox.desktop;' ${mimePackage}/share/applications/mimeapps.list
      test ! -e "$XDG_DATA_HOME/applications/steam-gamescope.desktop"
      test ! -e "$XDG_CONFIG_HOME/hypr/modules/Deck.lua"
      test -L "$XDG_CONFIG_HOME/quickshell/icewine"
      test -f "$XDG_CONFIG_HOME/quickshell/icewine/Handheld.qml"
      test ! -e "$XDG_CONFIG_HOME/quickshell/modules"
      cmp ${../hyprland/hyprland.lua} "$XDG_CONFIG_HOME/hypr/hyprland.lua"
      cmp ${../quickshell/deck/shell.qml} "$XDG_CONFIG_HOME/quickshell/shell.qml"
      cp -r "$(readlink "$XDG_CONFIG_HOME/hypr/icewine")" "$TMPDIR/portable-handheld-hyprland"
      ln -sfn "$TMPDIR/portable-handheld-hyprland" "$XDG_CONFIG_HOME/hypr/icewine"
      unset ICEWINE_IMPLEMENTATION
      lua ${../hyprland/tests/startup.lua} "$XDG_CONFIG_HOME/hypr/hyprland.lua" handheld
      touch "$out"
    '';
}
