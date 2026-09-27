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
    runtimeInputs = [ pkgs.systemd ];
    text = ''
      systemctl --user start icewine-keyboard.service

      case "$(busctl --user --timeout=2 get-property sm.puri.OSK0 /sm/puri/OSK0 sm.puri.OSK0 Visible)" in
        'b true') visible=false ;;
        'b false') visible=true ;;
        *) echo "Could not read on-screen keyboard visibility" >&2; exit 1 ;;
      esac

      busctl --user --timeout=2 call sm.puri.OSK0 /sm/puri/OSK0 sm.puri.OSK0 SetVisible b "$visible"
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


    programs.steam.enable = true;
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


    home-manager.users.${cfg.user} = {
      systemd.user.services.icewine-inputplumber-hyprland = {
        Unit = {
          Description = "Steam Deck InputPlumber profile for Hyprland";
          PartOf = [ "graphical-session.target" ];
          After = [ "graphical-session.target" ];
        };
        Service = {
          Type = "oneshot";
          RemainAfterExit = true;
          Restart = "on-failure";
          RestartSec = "2s";
          ExecStart = "${icewineInputplumberHyprland}";
          ExecStop = "${icewineInputplumberRestore}";
        };
        Install.WantedBy = [ "graphical-session.target" ];
      };

      systemd.user.services.icewine-keyboard = {
        Unit = {
          Description = "Icewine on-screen keyboard";
          PartOf = [ "graphical-session.target" ];
          After = [ "graphical-session.target" ];
        };
        Service = {
          Type = "dbus";
          BusName = "sm.puri.OSK0";
          ExecStart = "${pkgs.squeekboard}/bin/squeekboard";
          Restart = "on-failure";
        };
        Install.WantedBy = [ "graphical-session.target" ];
      };

      # Normal exits and crashes both leave the gamepad muted, while native
      # trackpads and the keyboard-mapped R5 remain usable for recovery.
      systemd.user.services.icewine.Service.ExecStopPost =
        "-${icewineInputplumberIntercept}/bin/icewine-inputplumber-intercept overlay";
    };
  };
}
