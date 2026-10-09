{ config, lib, pkgs, ... }:
let
  cfg = config.services.icewine;
  icewineInputplumberHyprland = pkgs.writeShellScript "icewine-inputplumber-hyprland" ''
    set -eu

    ${pkgs.inputplumber}/bin/inputplumber devices manage-all --enable

    device=
    for _ in $(${pkgs.coreutils}/bin/seq 1 40); do
      if device=$(${icewineInputplumberIntercept}/bin/icewine-inputplumber-intercept device); then
        break
      fi
      ${pkgs.coreutils}/bin/sleep 0.25
    done

    if [ -z "$device" ]; then
      echo "No InputPlumber composite device appeared after manage-all" >&2
      exit 1
    fi

    ${pkgs.inputplumber}/bin/inputplumber device "$device" targets set xbox-elite keyboard mouse touchpad
    ${pkgs.inputplumber}/bin/inputplumber device "$device" profile load /etc/inputplumber/profiles/icewine-hyprland.yaml
    # Fail closed until QuickShell observes Gamescope taking focus.
    ${icewineInputplumberIntercept}/bin/icewine-inputplumber-intercept overlay
  '';

  icewineInputplumberRestore = pkgs.writeShellScript "icewine-inputplumber-restore" ''
    set -u

    if id=$(${icewineInputplumberIntercept}/bin/icewine-inputplumber-intercept device); then
      ${pkgs.inputplumber}/bin/inputplumber device "$id" targets set xbox-elite mouse keyboard touchpad || true
      ${pkgs.inputplumber}/bin/inputplumber device "$id" profile load /run/current-system/sw/share/inputplumber/profiles/default.yaml || true
      ${pkgs.inputplumber}/bin/inputplumber device "$id" intercept set pass || true
    fi
  '';

  icewineInputplumberIntercept = pkgs.writeShellApplication {
    name = "icewine-inputplumber-intercept";
    runtimeInputs = [ pkgs.inputplumber pkgs.systemd pkgs.coreutils pkgs.glib pkgs.jq ];
    text = builtins.readFile ../scripts/inputplumber-intercept.sh;
  };

  icewineKeyboardToggle = pkgs.writeShellApplication {
    name = "icewine-keyboard-toggle";
    runtimeInputs = [ pkgs.systemd pkgs.quickshell ];
    text = ''
      systemctl --user start icewine-keyboard.service

      case "$(busctl --user --timeout=2 get-property sm.puri.OSK0 /sm/puri/OSK0 sm.puri.OSK0 Visible)" in
        'b true') visible=false ;;
        'b false') visible=true ;;
        *) echo "Could not read on-screen keyboard visibility" >&2; exit 1 ;;
      esac

      busctl --user --timeout=2 call sm.puri.OSK0 /sm/puri/OSK0 sm.puri.OSK0 SetVisible b "$visible"
      ${pkgs.quickshell}/bin/qs ipc call topbar osk "$visible" || true
    '';
  };

in {
  config = lib.mkIf (cfg.enable && cfg.handheld.enable) {
  nixpkgs.overlays = lib.mkAfter [
    (_final: prev: {
      squeekboard = prev.squeekboard.overrideAttrs (old: {
        # Draw above fullscreen applications without changing their window state.
        postPatch = (old.postPatch or "") + ''
          substituteInPlace src/panel.c \
            --replace-fail ZWLR_LAYER_SHELL_V1_LAYER_TOP ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY
        '';
      });
    })
  ];


    assertions = [ {
      assertion = cfg.desktop.enable && cfg.gaming.enable && !cfg.flatpak.enable;
      message = "Icewine handheld integration requires desktop and gaming enabled with flatpak disabled.";
    } ];
    services.inputplumber.enable = true;
    services.pipewire.alsa.support32Bit = true;
    environment.systemPackages = [ pkgs.squeekboard
      icewineInputplumberIntercept icewineKeyboardToggle ];
  environment.etc."inputplumber/profiles/icewine-hyprland.yaml".source =
    ../inputplumber/inputplumber-hyprland.yaml;
  environment.etc."inputplumber/profiles/icewine-desktop.yaml".source =
    ../inputplumber/inputplumber-desktop.yaml;

  security.polkit.extraConfig = ''
    polkit.addRule(function(action, subject) {
      var allowed = [
        "org.shadowblip.InputPlumber.SetManageAllDevices",
        "org.shadowblip.Input.CompositeDevice.LoadProfilePath",
        "org.shadowblip.Input.CompositeDevice.SetInterceptMode",
        "org.shadowblip.Input.CompositeDevice.SetTargetDevices"
      ];

      if (subject.user == ${builtins.toJSON cfg.user} && allowed.indexOf(action.id) >= 0) {
        return polkit.Result.YES;
      }
    });
  '';


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
        partOf = [ "graphical-session.target" ];
        after = [ "graphical-session.target" ];
        unitConfig.ConditionUser = cfg.user;
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          Restart = "on-failure";
          RestartSec = "2s";
          ExecStart = "${icewineInputplumberHyprland}";
          ExecStop = "${icewineInputplumberRestore}";
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
