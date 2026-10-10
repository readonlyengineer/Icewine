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
        desktop.enable = lib.mkDefault handheld;
        steam = lib.mkDefault (if handheld then "native" else "none");
      };
      system.stateVersion = "26.05";
    } ];
  };
  desktopSystem = example false;
  handheldSystem = example true;
  desktop = desktopSystem.config;
  handheld = handheldSystem.config;
  optIn = (desktopSystem.extendModules { modules = [{ services.icewine = {
    desktop.enable = true;
    terminal.enable = true;
    filemanager.enable = true;
    steam = "flatpak";
    login.enable = true;
    shellExtras.enable = true;
  }; services.displayManager.sddm.enable = true; }]; }).config;
  nativeGaming = (desktopSystem.extendModules { modules = [{ services.icewine.steam = "native"; }]; }).config;
  flatpakOnly = (desktopSystem.extendModules { modules = [{ services.icewine = { steam = "flatpak"; gamescope.enable = false; }; }]; }).config;
  loginOnly = (desktopSystem.extendModules { modules = [{
    boot.isContainer = true; # Evaluation fixture has no disk/bootloader configuration.
    services.icewine.login.enable = true;
    services.displayManager.sddm.enable = true;
  }]; }).config;
  loginOff = (desktopSystem.extendModules { modules = [{ services.displayManager.sddm.enable = true; }]; }).config;
  quickshell = pkgs.callPackage ../quickshell/package.nix { };
  sddmTheme = pkgs.callPackage ../sddm { };
  icewineCli = builtins.head (lib.filter
    (package: lib.getName package == "icewine") optIn.users.users.demo.packages);
  handheldCli = builtins.head (lib.filter
    (package: lib.getName package == "icewine") handheld.users.users.demo.packages);
  hasPackage = name: packages: lib.any (package: lib.getName package == name) packages;
in {
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
  theme = pkgs.runCommand "icewine-live-theme-checks" {
    nativeBuildInputs = [ pkgs.python3 quickshell ];
  } ''
    python3 ${./theme-live.py} ${self}
    touch "$out"
  '';
  native = import ../packaging/arch/integration.nix { inherit pkgs; src = self; };
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
    assert lib.all (name: !desktop.services.icewine.${name}.enable)
      [ "desktop" "terminal" "filemanager" "login" "shellExtras" ];
    assert desktop.services.icewine.steam == "none";
    assert !desktop.programs.hyprland.enable;
    assert !desktop.programs.steam.enable;
    assert !desktop.services.flatpak.enable;
    assert !desktop.services.displayManager.sddm.enable;
    assert !desktop.programs.firefox.enable;
    assert desktop.programs.firefox.nativeMessagingHosts.packages == [ ];
    assert desktop.xdg.mime.defaultApplications == { };
    assert !desktop.networking.networkmanager.enable;
    assert !desktop.services.openssh.enable;
    assert !(desktop.systemd.services ? icewine-init);
    assert !(optIn.systemd.services ? icewine-init);
    assert !(optIn.systemd.user.services.icewine.serviceConfig ? ExecStartPre);
    assert !(optIn.system.userActivationScripts ? icewine);
    assert !(hasPackage "kitty" desktop.users.users.demo.packages);
    assert hasPackage "xdg-terminal-exec" optIn.environment.systemPackages;
    assert !(hasPackage "nano" desktop.users.users.demo.packages);
    assert !(hasPackage "yazi" desktop.users.users.demo.packages);
    assert !(hasPackage "gamescope" desktop.environment.systemPackages);
    assert optIn.programs.hyprland.enable && optIn.programs.hyprland.withUWSM;
    assert !optIn.programs.steam.enable;
    assert optIn.services.flatpak.enable;
    assert map (package: package.appId) optIn.services.flatpak.packages == [ "com.valvesoftware.Steam" ];
    assert !optIn.services.flatpak.uninstallUnmanaged;
    assert optIn.services.icewine.applications.steam == [ "flatpak" "run" "com.valvesoftware.Steam" ];
    assert hasPackage "kitty" optIn.users.users.demo.packages;
    assert !(hasPackage "nano" optIn.users.users.demo.packages);
    assert hasPackage "yazi" optIn.users.users.demo.packages;
    assert hasPackage "fastfetch" optIn.users.users.demo.packages;
    assert hasPackage "starship" optIn.users.users.demo.packages;
    assert hasPackage "gamescope" optIn.environment.systemPackages;
    assert !(hasPackage "bazaar" optIn.environment.systemPackages);
    assert optIn.services.displayManager.sddm.theme == "icewine";
    assert loginOnly.services.displayManager.sddm.enable;
    assert loginOnly.services.displayManager.sddm.theme == "icewine";
    assert !loginOnly.programs.hyprland.enable;
    assert loginOnly.services.displayManager.defaultSession == null;
    assert lib.all (assertion: assertion.assertion) loginOnly.assertions;
    assert loginOff.services.displayManager.sddm.enable;
    assert loginOff.services.displayManager.sddm.theme != "icewine";
    assert nativeGaming.programs.steam.enable;
    assert !nativeGaming.services.flatpak.enable;
    assert nativeGaming.nixpkgs.config.allowUnfreePackages == [ "steam" "steam-unwrapped" ];
    assert flatpakOnly.services.flatpak.enable;
    assert map (package: package.appId) flatpakOnly.services.flatpak.packages == [ "com.valvesoftware.Steam" ];
    assert !(hasPackage "gamescope" flatpakOnly.environment.systemPackages);
    assert builtins.elem "icewine.service" handheld.systemd.user.services.icewine-inputplumber-hyprland.before;
    assert handheld.services.inputplumber.enable && handheld.programs.steam.enable;
    assert handheld.services.icewine.applications.steam == [ "steam" "-gamepadui" ];
    pkgs.runCommand "icewine-module-checks" { nativeBuildInputs = [ pkgs.lua pkgs.python3 ]; } ''
      export HOME=$TMPDIR/home XDG_CONFIG_HOME=$TMPDIR/home/.config XDG_DATA_HOME=$TMPDIR/home/.local/share XDG_STATE_HOME=$TMPDIR/home/.local/state
      mkdir -p "$HOME"
      grep -F 'Before=icewine.service' ${handheld.systemd.user.units."icewine-inputplumber-hyprland.service".unit}/icewine-inputplumber-hyprland.service
      grep -F 'ExecStart=' ${handheld.systemd.user.units."icewine-keyboard.service".unit}/icewine-keyboard.service
      grep -F 'ExecStart=' ${handheld.systemd.user.units."icewine-controller-idle.service".unit}/icewine-controller-idle.service
      grep -F 'ExecStopPost=' ${handheld.systemd.user.units."icewine-inputplumber-hyprland.service".unit}/icewine-inputplumber-hyprland.service
      grep -F 'ExecStart=' ${optIn.systemd.user.units."icewine.service".unit}/icewine.service
      ! grep -q 'icewine init' ${optIn.systemd.user.units."icewine.service".unit}/icewine.service
      grep -F 'ExecStart=' ${optIn.systemd.user.units."hypridle.service".unit}/hypridle.service
      read -ra fields <<< "$(${icewineCli}/bin/icewine-manage-backend state)"
      selections=()
      for field in "''${fields[@]}"; do
        if [[ "$field" != readonly=* ]]; then selections+=("$field"); fi
      done
      [[ " ''${fields[*]} " = *" readonly=true "* ]]
      for selection in "''${selections[@]}"; do
        [[ "$selection" = *=true || "$selection" = steam=flatpak || "$selection" = handheld=false ]]
      done
      test ! -e "$XDG_CONFIG_HOME"
      ${icewineCli}/bin/icewine-manage-backend apply "''${selections[@]}" overwrite=false
      test -L "$XDG_CONFIG_HOME/quickshell/icewine"
      test -L "$XDG_CONFIG_HOME/hypr/icewine"
      test -f "$XDG_CONFIG_HOME/quickshell/icewine/Desktop.qml"
      test ! -e "$XDG_CONFIG_HOME/quickshell/modules"
      test ! -e "$XDG_CONFIG_HOME/hypr/modules/Theme.lua"
      grep -Fx 'Hidden=true' "$XDG_DATA_HOME/applications/steam.desktop"
      implementation=$(dirname "$(readlink "$XDG_CONFIG_HOME/quickshell/icewine")")
      for name in adapters/Hyprland.qml modules/Topbar.qml theme/qmldir theme/Palette.qml Desktop.qml Handheld.qml deck/DeckOverlay.qml deck/DeckMenu.js; do
        cmp ${../quickshell}/"$name" "$implementation/quickshell/$name"
      done
      test ! -e "$XDG_CONFIG_HOME/nano/nanorc"
      test ! -e "$XDG_CONFIG_HOME/nvim"
      cp -r "$(readlink "$XDG_CONFIG_HOME/hypr/icewine")" "$TMPDIR/portable-hyprland"
      ln -sfn "$TMPDIR/portable-hyprland" "$XDG_CONFIG_HOME/hypr/icewine"
      lua ${../hyprland/tests/startup.lua} "$XDG_CONFIG_HOME/hypr/hyprland.lua" desktop
      printf '# user changes\n' >> "$XDG_CONFIG_HOME/kitty/kitty.conf"
      ${icewineCli}/bin/icewine-manage-backend apply "''${selections[@]}" overwrite=false
      grep -Fx '# user changes' "$XDG_CONFIG_HOME/kitty/kitty.conf"
      ${icewineCli}/bin/icewine-manage-backend apply "''${selections[@]}" overwrite=true
      ! grep -q '# user changes' "$XDG_CONFIG_HOME/kitty/kitty.conf"
      export HOME=$TMPDIR/handheld XDG_CONFIG_HOME=$TMPDIR/handheld/.config XDG_DATA_HOME=$TMPDIR/handheld/.local/share XDG_STATE_HOME=$TMPDIR/handheld/.local/state
      mkdir -p "$HOME"
      read -ra fields <<< "$(${handheldCli}/bin/icewine-manage-backend state)"
      selections=()
      for field in "''${fields[@]}"; do
        if [[ "$field" != readonly=* ]]; then selections+=("$field"); fi
      done
      ${handheldCli}/bin/icewine-manage-backend apply "''${selections[@]}" overwrite=false
      cmp ${../quickshell/deck/shell.qml} "$XDG_CONFIG_HOME/quickshell/shell.qml"
      cp -r "$(readlink "$XDG_CONFIG_HOME/hypr/icewine")" "$TMPDIR/portable-handheld-hyprland"
      ln -sfn "$TMPDIR/portable-handheld-hyprland" "$XDG_CONFIG_HOME/hypr/icewine"
      lua ${../hyprland/tests/startup.lua} "$XDG_CONFIG_HOME/hypr/hyprland.lua" handheld
      touch "$out"
    '';
}
