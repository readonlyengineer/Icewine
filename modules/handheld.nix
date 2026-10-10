{ config, lib, pkgs, ... }:
let
  cfg = config.services.icewine;
  icewineInputplumberIntercept = pkgs.writeShellApplication {
    name = "icewine-inputplumber-intercept";
    runtimeInputs = [ pkgs.inputplumber pkgs.systemd pkgs.coreutils pkgs.glib pkgs.jq ];
    text = builtins.readFile ../scripts/inputplumber-intercept.sh;
  };
  icewineInputplumberHyprland = pkgs.writeShellApplication {
    name = "icewine-inputplumber-hyprland";
    runtimeInputs = [ pkgs.inputplumber pkgs.coreutils icewineInputplumberIntercept ];
    text = builtins.readFile ../scripts/inputplumber-hyprland.sh;
  };
  icewineInputplumberRestore = pkgs.writeShellApplication {
    name = "icewine-inputplumber-restore";
    runtimeInputs = [ pkgs.inputplumber icewineInputplumberIntercept ];
    text = builtins.readFile ../scripts/inputplumber-restore.sh;
  };
  icewineKeyboardToggle = pkgs.writeShellApplication {
    name = "icewine-keyboard-toggle";
    runtimeInputs = [ pkgs.systemd pkgs.quickshell ];
    text = builtins.readFile ../scripts/keyboard-toggle.sh;
  };

in {
  config = lib.mkIf (cfg.enable && cfg.handheld.enable) {
  nixpkgs.overlays = lib.mkAfter [
    (_final: prev: {
      squeekboard = prev.squeekboard.overrideAttrs (old: {
        # Draw above fullscreen applications without changing their window state.
        patches = (old.patches or []) ++ [
          ../packaging/arch/dependencies/squeekboard-overlay.patch
          ../packaging/arch/dependencies/squeekboard-rust.patch
        ];
      });
    })
  ];


    assertions = [ {
      assertion = cfg.desktop.enable && cfg.steam == "native" && cfg.gamescope.enable;
      message = "Icewine handheld integration requires desktop, native Steam and Gamescope enabled.";
    } ];
    services.inputplumber.enable = true;
    services.pipewire.alsa.support32Bit = true;
    environment.systemPackages = [ pkgs.squeekboard
      icewineInputplumberIntercept icewineKeyboardToggle ];
  environment.etc."inputplumber/profiles/icewine-hyprland.yaml".source =
    ../inputplumber/inputplumber-hyprland.yaml;
  environment.etc."inputplumber/profiles/icewine-desktop.yaml".source =
    ../inputplumber/inputplumber-desktop.yaml;

  security.polkit.extraConfig = builtins.replaceStrings [ "@user@" ]
    [ (builtins.toJSON cfg.user) ] (builtins.readFile ../inputplumber/polkit.rules.in);


      systemd.user.services.icewine-controller-idle = lib.mkIf cfg.idle.enable {
        description = "Keep Icewine awake during controller activity";
        partOf = [ "graphical-session.target" ];
        after = [ "graphical-session.target" ];
        unitConfig.ConditionUser = cfg.user;
        serviceConfig = {
          ExecStart = "${pkgs.wljoywake}/bin/wljoywake -t 5";
          Restart = "on-failure";
          RestartSec = "2s";
        };
        wantedBy = [ "graphical-session.target" ];
      };

      systemd.user.services.icewine-inputplumber-hyprland = {
        description = "Steam Deck InputPlumber profile for Hyprland";
        before = [ "icewine.service" ];
        partOf = [ "graphical-session.target" ];
        after = [ "graphical-session.target" ];
        unitConfig.ConditionUser = cfg.user;
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          Restart = "on-failure";
          RestartSec = "2s";
          ExecStart = "${icewineInputplumberHyprland}/bin/icewine-inputplumber-hyprland";
          ExecStopPost = "${icewineInputplumberRestore}/bin/icewine-inputplumber-restore";
          Environment = "ICEWINE_INPUTPLUMBER_DEFAULT_PROFILE=${pkgs.inputplumber}/share/inputplumber/profiles/default.yaml";
        };
        wantedBy = [ "graphical-session.target" ];
      };

      systemd.user.services.icewine-keyboard = {
        description = "Icewine on-screen keyboard";
        partOf = [ "graphical-session.target" ];
        after = [ "graphical-session.target" ];
        unitConfig.ConditionUser = cfg.user;
        serviceConfig = {
          Type = "dbus";
          BusName = "sm.puri.OSK0";
          ExecStart = "${pkgs.squeekboard}/bin/squeekboard";
          Restart = "on-failure";
        };
        wantedBy = [ "graphical-session.target" ];
      };

      # Normal exits and crashes both leave the gamepad muted, while native
      # trackpads and the keyboard-mapped R5 remain usable for recovery.
      systemd.user.services.icewine.serviceConfig.ExecStopPost =
        "-${icewineInputplumberIntercept}/bin/icewine-inputplumber-intercept overlay";
  };
}
