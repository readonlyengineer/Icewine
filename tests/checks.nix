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
  }; }]; }).config;
  screenshotOnly = (desktopSystem.extendModules { modules = [{ services.icewine = { desktop.enable = true; steam = "none"; }; }]; }).config;
  screenshotNone = (desktopSystem.extendModules { modules = [{ services.icewine = { desktop.enable = true; screenshot = false; }; }]; }).config;
  editorEnabled = (desktopSystem.extendModules { modules = [{ services.icewine.texteditor.enable = true; }]; }).config;
  monitorsOnly = (desktopSystem.extendModules { modules = [{ services.icewine.monitors = { enable = true; package = pkgs.hello; }; }]; }).config;
  nativeGaming = (desktopSystem.extendModules { modules = [{ services.icewine.steam = "native"; }]; }).config;
  flatpakOnly = (desktopSystem.extendModules { modules = [{ services.icewine = { steam = "flatpak"; gamescope.enable = false; }; }]; }).config;
  loginOnly = (desktopSystem.extendModules { modules = [{
    boot.isContainer = true; # Evaluation fixture has no disk/bootloader configuration.
    services.icewine.login.enable = true;
  }]; }).config;
  barPolicy = (desktopSystem.extendModules { modules = [{
    services.icewine.widgets = { barBehaviour = "always"; barLocation = "bottom"; barWidth = 99; barStyle = "floating"; };
  }]; }).config;
  loginOff = desktop;
  greeterSystem = desktopSystem.extendModules { modules = [{
    boot.isContainer = true;
    services.icewine = { desktop.enable = true; login.greeter.enable = true; };
  }]; };
  greeter = greeterSystem.config;
  hostGreeterSystem = greeterSystem.extendModules { modules = [{
    services.greetd.settings = {
      default_session = { user = "host-greeter"; command = "host-greeter --session host-session"; };
      initial_session = { user = "other"; command = "host-autologin"; };
    };
  }]; };
  hostGreeter = hostGreeterSystem.config;
  greeterOff = (hostGreeterSystem.extendModules { modules = [{
    services.icewine.login.greeter.enable = lib.mkForce false;
    services.greetd.enable = true;
  }]; }).config;
  greeterUnstyled = (greeterSystem.extendModules { modules = [{ services.icewine.login.enable = false; }]; }).config;
  greeterOnlyOff = (greeterSystem.extendModules { modules = [{ services.icewine.login.greeter.enable = lib.mkForce false; }]; }).config;
  greeterWithoutDesktop = (desktopSystem.extendModules { modules = [{ services.icewine.login.greeter.enable = true; }]; }).config;
  greeterConflict = (greeterSystem.extendModules { modules = [{
    services.displayManager.sddm = { enable = true; wayland.enable = true; };
  }]; }).config;
  greeterAliasConflict = (greeterSystem.extendModules { modules = [{
    systemd.services.host-login = { aliases = [ "display-manager.service" ]; serviceConfig.ExecStart = "/host-login"; };
  }]; }).config;
  icewineOff = (greeterSystem.extendModules { modules = [{ services.icewine.enable = lib.mkForce false; }]; }).config;
  valid = config: lib.all (entry: entry.assertion) config.assertions;
  rejects = message: config: lib.any (entry: entry.message == message && !entry.assertion) config.assertions;
  contains = needle: lib.hasInfix (builtins.unsafeDiscardStringContext needle);
  greeterCommand = greeter.services.greetd.settings.default_session.command;
  quickshell = pkgs.callPackage ../quickshell/package.nix { };
  optionalEditor = builtins.head (lib.filter (package: lib.getName package == "icewine-editor") editorEnabled.users.users.demo.packages);
  icewineCli = builtins.head (lib.filter
    (package: lib.getName package == "icewine") optIn.users.users.demo.packages);
  handheldCli = builtins.head (lib.filter
    (package: lib.getName package == "icewine") handheld.users.users.demo.packages);
  directoryDefault = builtins.head (lib.filter
    (package: lib.getName package == "mimeapps.list") optIn.users.users.demo.packages);
  hasPackage = name: packages: lib.any (package: lib.getName package == name) packages;
in {
  login =
    assert greeter.services.greetd.enable && greeter.services.greetd.useTextGreeter;
    assert greeter.services.greetd.settings.default_session.user == "greeter";
    assert contains "${pkgs.tuigreet}/bin/tuigreet" greeterCommand;
    assert contains "${pkgs.uwsm}/bin/uwsm start hyprland-uwsm.desktop" greeterCommand;
    assert contains "${greeter.services.displayManager.sessionData.desktops}/share/wayland-sessions" greeterCommand;
    assert !(lib.any (flag: lib.hasInfix flag greeterCommand) [ "--remember-session" "--theme" "--width" ]);
    assert lib.elem "hyprland-uwsm" greeter.services.displayManager.sessionData.sessionNames;
    assert !(greeter.services.greetd.settings ? initial_session) && greeter.services.greetd.restart;
    assert !greeter.services.displayManager.autoLogin.enable && greeter.services.displayManager.defaultSession == null;
    assert greeter.systemd.services.greetd.serviceConfig.StandardInput == "tty";
    assert hostGreeter.services.greetd.settings.default_session == { user = "host-greeter"; command = "host-greeter --session host-session"; };
    assert hostGreeter.services.greetd.settings.initial_session == { user = "other"; command = "host-autologin"; };
    assert !hostGreeter.services.greetd.restart;
    assert greeterOff.services.greetd.enable && greeterOff.services.icewine.login.args == [ ];
    assert greeterOff.services.greetd.settings == hostGreeter.services.greetd.settings;
    assert greeterUnstyled.services.greetd.enable;
    assert !(lib.hasInfix "--theme" greeterUnstyled.services.greetd.settings.default_session.command);
    assert !loginOff.services.greetd.enable && !greeterOnlyOff.services.greetd.enable && !icewineOff.services.greetd.enable;
    assert lib.all valid [ greeter hostGreeter greeterOff greeterUnstyled ];
    assert rejects "Icewine greeter requires services.icewine.desktop.enable for its Hyprland UWSM session." greeterWithoutDesktop;
    assert lib.all (rejects "Icewine greeter conflicts with another display manager; disable it explicitly before opting in.")
      [ greeterConflict greeterAliasConflict ];
    pkgs.runCommand "icewine-login-checks" { nativeBuildInputs = [ pkgs.greetd pkgs.tuigreet ]; } ''
      greetd --help > /dev/null
      tuigreet --help > /dev/null
      test -d ${greeter.services.displayManager.sessionData.desktops}/share/wayland-sessions
      grep -F 'ExecStart=' ${greeter.systemd.units."greetd.service".unit}/greetd.service
      touch "$out"
    '';
  ssh = pkgs.runCommand "icewine-ssh-checks" {
    nativeBuildInputs = [ pkgs.python3 pkgs.openssh pkgs.util-linux ];
  } ''
    python3 ${self}/tests/ssh.py
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
    python3 ${self}/tests/controls.py ${self}
    python3 ${self}/tests/bar-geometry.py ${self}
    python3 ${self}/tests/layouts.py --qml
    python3 ${self}/tests/render-ready.py ${self}
    python3 ${self}/tests/wallpaper-layout.py ${self}
    python3 ${self}/tests/keyboard.py ${self}
    python3 ${self}/tests/breeze-lock.py ${self}
    ICEWINE_TEST_QS=quickshell ICEWINE_THEME_TRANSITION=off python3 ${self}/tests/breeze-lock.py ${self}
    python3 ${self}/tests/window-switcher.py ${self}
    python3 ${./theme-live.py} ${self}
    touch "$out"
  '';
  theme = pkgs.runCommand "icewine-live-theme-checks" {
    nativeBuildInputs = [ pkgs.python3 quickshell ];
  } ''
    python3 ${./theme-live.py} ${self}
    touch "$out"
  '';
  mime = pkgs.runCommand "icewine-mime-checks" {
    nativeBuildInputs = [ pkgs.python3 pkgs.xdg-utils pkgs.xdg-terminal-exec ];
  } ''
    python3 ${./mime.py} ${self} ${pkgs.xdg-utils}/bin/xdg-mime \
      ${pkgs.xdg-utils}/bin/xdg-open ${pkgs.xdg-terminal-exec}/bin/xdg-terminal-exec \
      ${directoryDefault}/share/applications/mimeapps.list
    touch "$out"
  '';
  native = import ../packaging/arch/integration.nix { inherit pkgs; src = self; };
  terminal = import ./terminal.nix { inherit self nixpkgs; manager = icewineCli; };
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
    python3 tests/hotkeys.py
    python3 tests/layouts.py
    python3 tests/clipboard.py
    touch "$out"
  '';
  wallpaper = pkgs.runCommand "icewine-wallpaper-checks" {
    nativeBuildInputs = [ pkgs.bash pkgs.coreutils pkgs.nodejs pkgs.python3 quickshell icewineCli ];
  } ''
    cd ${self}
    node quickshell/tests/wallpaper.js
    bash tests/wallpaper-selector.sh ${icewineCli}/bin/icewine
    touch "$out"
  '';
  modules =
    assert screenshotOnly.services.icewine.screenshot;
    assert screenshotOnly.services.flatpak.enable;
    assert map (package: package.appId) screenshotOnly.services.flatpak.packages == [ "be.alexandervanhee.gradia" ];
    assert (builtins.head screenshotOnly.services.flatpak.packages).origin == "flathub";
    assert lib.any (remote: remote.name == "flathub") screenshotOnly.services.flatpak.remotes;
    assert !screenshotOnly.services.flatpak.uninstallUnmanaged;
    assert screenshotOnly.systemd.user.paths ? icewine-refresh-flatpak-icons;
    assert !screenshotNone.services.flatpak.enable;
    assert !(screenshotNone.systemd.user.paths ? icewine-refresh-flatpak-icons);
    assert lib.all (config: lib.all (name: !(hasPackage name config.environment.systemPackages))
      [ "gradia" "hyprshot" "flameshot" ]) [ screenshotOnly screenshotNone optIn handheld ];
    assert handheld.services.icewine.screenshot && handheld.services.flatpak.enable;
    assert map (package: package.appId) handheld.services.flatpak.packages == [ "be.alexandervanhee.gradia" ];
    assert handheld.services.icewine.steam == "native";
    assert hasPackage "icewine-editor" editorEnabled.users.users.demo.packages;
    assert !(hasPackage "icewine-editor" desktop.users.users.demo.packages);
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
    assert !(hasPackage "mimeapps.list" desktop.users.users.demo.packages);
    assert hasPackage "mimeapps.list" optIn.users.users.demo.packages;
    assert !(hasPackage "mimeapps.list" optIn.users.users.other.packages);
    assert !desktop.networking.networkmanager.enable;
    assert !desktop.services.openssh.enable;
    assert !desktop.programs.ssh.startAgent; # Native agent policy belongs to the host.
    assert lib.hasInfix "icewine-ssh" (builtins.concatStringsSep ":" optIn.systemd.user.services.icewine.serviceConfig.Environment);
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
    assert map (package: package.appId) optIn.services.flatpak.packages == [ "com.valvesoftware.Steam" "be.alexandervanhee.gradia" ];
    assert !optIn.services.flatpak.uninstallUnmanaged;
    assert optIn.services.icewine.applications.steam == [ "flatpak" "run" "com.valvesoftware.Steam" ];
    assert hasPackage "kitty" optIn.users.users.demo.packages;
    assert !(hasPackage "nano" optIn.users.users.demo.packages);
    assert hasPackage "yazi" optIn.users.users.demo.packages;
    assert hasPackage "fastfetch" optIn.users.users.demo.packages;
    assert hasPackage "starship" optIn.users.users.demo.packages;
    assert hasPackage "gamescope" optIn.environment.systemPackages;
    assert !(hasPackage "bazaar" optIn.environment.systemPackages);
    assert !(hasPackage "hyprmon" desktop.users.users.demo.packages);
    assert hasPackage "hello" monitorsOnly.users.users.demo.packages;
    assert !loginOnly.services.greetd.enable && !loginOnly.services.displayManager.sddm.enable;
    assert lib.elem "--width" loginOnly.services.icewine.login.args;
    assert lib.elem "text=#cdd6f4;border=#585b70;prompt=#89b4fa;input=#cdd6f4;action=#7f849c;button=#89b4fa;container=#1e1e2e" loginOnly.services.icewine.login.args;
    assert !loginOnly.programs.hyprland.enable;
    assert loginOnly.services.displayManager.defaultSession == null;
    assert lib.all (assertion: assertion.assertion) loginOnly.assertions;
    assert loginOff.services.icewine.login.args == [ ];
    assert nativeGaming.programs.steam.enable;
    assert !nativeGaming.services.flatpak.enable;
    assert nativeGaming.nixpkgs.config.allowUnfreePackages == [ "steam" "steam-unwrapped" ];
    assert flatpakOnly.services.flatpak.enable;
    assert map (package: package.appId) flatpakOnly.services.flatpak.packages == [ "com.valvesoftware.Steam" ];
    assert !(hasPackage "gamescope" flatpakOnly.environment.systemPackages);
    assert builtins.elem "icewine.service" handheld.systemd.user.services.icewine-inputplumber-hyprland.before;
    assert handheld.services.inputplumber.enable && handheld.programs.steam.enable;
    assert desktop.services.icewine.widgets.barBehaviour == null;
    assert desktop.services.icewine.widgets.barLocation == null;
    assert desktop.services.icewine.widgets.barWidth == null;
    assert desktop.services.icewine.widgets.barStyle == null;
    assert barPolicy.services.icewine.widgets.barBehaviour == "always";
    assert barPolicy.services.icewine.widgets.barLocation == "bottom";
    assert barPolicy.services.icewine.widgets.barWidth == 99;
    assert barPolicy.services.icewine.widgets.barStyle == "floating";
    assert !(handheld.systemd.user.services ? icewine-keyboard);
    assert hasPackage "wtype" optIn.environment.systemPackages;
    assert handheld.services.icewine.applications.steam == [ "steam" "-gamepadui" ];
    pkgs.runCommand "icewine-module-checks" { nativeBuildInputs = [ pkgs.lua pkgs.python3 ]; } ''
      export HOME=$TMPDIR/home XDG_CONFIG_HOME=$TMPDIR/home/.config XDG_DATA_HOME=$TMPDIR/home/.local/share XDG_STATE_HOME=$TMPDIR/home/.local/state
      export XDG_RUNTIME_DIR=$TMPDIR/runtime XDG_CACHE_HOME=$TMPDIR/cache
      mkdir -m700 -p "$XDG_RUNTIME_DIR"
      mkdir -p "$HOME"
      mkdir -p "$XDG_CONFIG_HOME/nvim" "$XDG_DATA_HOME/nvim/lazy/personal"
      printf 'personal init\n' > "$XDG_CONFIG_HOME/nvim/init.lua"
      printf 'personal plugin\n' > "$XDG_DATA_HOME/nvim/lazy/personal/sentinel"
      EDITOR=personal-editor VISUAL=personal-visual ${optionalEditor}/bin/icewine-editor --headless -c 'luafile ${./editor.lua}' -c qa
      grep -Fx 'personal init' "$XDG_CONFIG_HOME/nvim/init.lua"
      grep -Fx 'personal plugin' "$XDG_DATA_HOME/nvim/lazy/personal/sentinel"
      # Use a separate fixture for manager/default deployment below.
      export XDG_CONFIG_HOME=$TMPDIR/manager-config XDG_DATA_HOME=$TMPDIR/manager-data
      # Compositor callers must resolve the helper without Quickshell's private PATH.
      for cli in ${icewineCli} ${handheldCli}; do
        if PATH=$cli/bin icewine-monitor-brightness ../eDP-1 2>"$TMPDIR/brightness-error"; then exit 1; fi
        grep -Fx 'Invalid monitor name' "$TMPDIR/brightness-error"
      done
      grep -F 'Before=icewine.service' ${handheld.systemd.user.units."icewine-inputplumber-hyprland.service".unit}/icewine-inputplumber-hyprland.service
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
        [[ "$selection" = *=true || "$selection" = steam=flatpak || "$selection" = handheld=false || "$selection" = texteditor=false ]]
      done
      test ! -e "$XDG_CONFIG_HOME"
      ${icewineCli}/bin/icewine-manage-backend apply "''${selections[@]}" overwrite=false
      test -L "$XDG_CONFIG_HOME/quickshell/icewine"
      test -L "$XDG_CONFIG_HOME/hypr/icewine"
      test "$(readlink "$XDG_CONFIG_HOME/quickshell/icewine")" = /etc/icewine/implementation/quickshell
      implementation=${optIn.environment.etc."icewine/implementation".source}
      grep -Fx 'window_alert_on_bell no' "$implementation/kitty/defaults.conf"
      grep -Fx 'bell_path ${pkgs.sound-theme-freedesktop}/share/sounds/freedesktop/stereo/bell.oga' "$implementation/kitty/defaults.conf"
      ! grep -q '/usr/share/sounds/' "$implementation/kitty/defaults.conf"
      test -s ${pkgs.sound-theme-freedesktop}/share/sounds/freedesktop/stereo/bell.oga
      ln -sfn "$implementation/quickshell" "$XDG_CONFIG_HOME/quickshell/icewine"
      ln -sfn "$implementation/hyprland" "$XDG_CONFIG_HOME/hypr/icewine"
      test -f "$XDG_CONFIG_HOME/quickshell/icewine/Desktop.qml"
      test ! -e "$XDG_CONFIG_HOME/quickshell/modules"
      test ! -e "$XDG_CONFIG_HOME/hypr/modules/Theme.lua"
      grep -Fx 'Hidden=true' "$XDG_DATA_HOME/applications/steam.desktop"
      for name in adapters/Hyprland.qml modules/Topbar.qml theme/qmldir theme/Palette.qml Desktop.qml Handheld.qml deck/DeckOverlay.qml deck/DeckMenu.js; do
        cmp ${../quickshell}/"$name" "$implementation/quickshell/$name"
      done
      test ! -e "$XDG_CONFIG_HOME/nano/nanorc"
      test ! -e "$XDG_CONFIG_HOME/nvim"
      cp -r "$(readlink "$XDG_CONFIG_HOME/hypr/icewine")" "$TMPDIR/portable-hyprland"
      ln -sfn "$TMPDIR/portable-hyprland" "$XDG_CONFIG_HOME/hypr/icewine"
      lua ${../hyprland/tests/startup.lua} "$XDG_CONFIG_HOME/hypr/hyprland.lua" desktop
      printf '# user changes\n' >> "$XDG_CONFIG_HOME/kitty/kitty.conf"
      printf 'color_theme = "Default"\nupdate_ms = 500\n' > "$XDG_CONFIG_HOME/btop/btop.conf"
      ${icewineCli}/bin/icewine-manage-backend apply "''${selections[@]}" overwrite=false
      grep -Fx '# user changes' "$XDG_CONFIG_HOME/kitty/kitty.conf"
      grep -Fx 'color_theme = "icewine"' "$XDG_CONFIG_HOME/btop/btop.conf"
      grep -Fx 'update_ms = 500' "$XDG_CONFIG_HOME/btop/btop.conf"
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
      cp -r ${handheld.environment.etc."icewine/implementation".source}/hyprland "$TMPDIR/portable-handheld-hyprland"
      ln -sfn "$TMPDIR/portable-handheld-hyprland" "$XDG_CONFIG_HOME/hypr/icewine"
      lua ${../hyprland/tests/startup.lua} "$XDG_CONFIG_HOME/hypr/hyprland.lua" handheld
      touch "$out"
    '';
}
