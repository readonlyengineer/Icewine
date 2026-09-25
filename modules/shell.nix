{ config, lib, pkgs, osConfig, nixpkgsLastModified ? 0, ... }:
let
  cfg = osConfig.services.icewine.shell;
  palette = import ../theme/palette.nix;
  highlightSgr = builtins.replaceStrings [ ", " ] [ ";" ] palette.highlightRgb;
  fastfetchKernelCommand = ''
    k=$(uname -r)
    if [ "$(readlink /run/booted-system/kernel)" = "$(readlink /run/current-system/kernel)" ]; then
      printf 'Linux %s' "$k"
    else
      printf 'Linux %s  \033[33m⚠ Restart Required\033[0m' "$k"
    fi
  '';
  fastfetchNixpkgsCommand = ''
    m=${toString nixpkgsLastModified}
    [ "$m" -gt 0 ] 2>/dev/null || { printf 'unknown'; exit 0; }
    d=$(( ($(date +%s) - m) / 86400 ))
    if [ "$d" -gt 7 ]; then
      printf '%sd old  \033[33m⚠ Update Overdue\033[0m' "$d"
    else
      printf '%sd old' "$d"
    fi
  '';
in {
  config = lib.mkIf cfg.enable {
    home.sessionVariables.LS_COLORS = lib.mkDefault "di=01;39:ex=00;39:ln=38;2;${builtins.replaceStrings [ ", " ] [ ";" ] palette.mutedRgb}:or=01;31:mi=01;31";
    home.packages = lib.optional cfg.blesh.enable pkgs.blesh;
    programs.bash = {
      enable = true;
      enableCompletion = lib.mkDefault true;
      shellAliases = {
        ls = lib.mkDefault "ls --color=auto";
        grep = lib.mkDefault "grep --color=auto";
      };
      # Home Manager places initExtra after its interactive-shell guard.
      # No SSH/TTY exclusions: interactive sessions get the same setup.
      initExtra = lib.mkAfter (
        lib.optionalString cfg.fastfetch.enable "${lib.getExe config.programs.fastfetch.package}\n"
        + lib.optionalString cfg.blesh.enable ''
          source -- ${pkgs.blesh}/share/blesh/ble.sh 2>/dev/null
          bleopt exec_errexit_mark=
          bleopt exec_elapsed_mark=
          bleopt complete_menu_style=desc
        ''
      );
    };
    programs.fastfetch = lib.mkIf cfg.fastfetch.enable {
      enable = true;
      settings = lib.mapAttrsRecursive (_: lib.mkDefault) {
        "$schema" = "https://github.com/fastfetch-cli/fastfetch/raw/master/doc/json_schema.json";
        logo = {
          type = "auto";
          color = {
            "1" = "#${palette.highlight}";
            "2" = "#${palette.secondaryHighlight}";
          };
          padding = {
            top = 1;
            right = 3;
          };
        };
        display = {
          separator = "   ";
          key.width = 20;
        };
        modules = [
          "break"
          { type = "custom"; format = "{#38;2;${highlightSgr}}󰟀   System{#}"; }
          { type = "os"; key = "├─   OS"; keyColor = "#${palette.muted}"; }
          { type = "host"; key = "├─ 󰌢  Host"; keyColor = "#${palette.muted}"; }
          {
            type = "command";
            key = "├─ 󰌽  Kernel";
            keyColor = "#${palette.muted}";
            shell = "/bin/sh";
            text = fastfetchKernelCommand;
          }
          {
            type = "command";
            key = "├─   Nixpkgs";
            keyColor = "#${palette.muted}";
            shell = "/bin/sh";
            text = fastfetchNixpkgsCommand;
          }
          { type = "uptime"; key = "└─ 󰔛  Uptime"; keyColor = "#${palette.muted}"; }
          "break"

          { type = "custom"; format = "{#38;2;${highlightSgr}}󰢮   Hardware{#}"; }
          {
            type = "cpu";
            key = "├─ 󰍛  CPU";
            keyColor = "#${palette.muted}";
            temp = {
              green = 70;
              yellow = 85;
            };
            format = "{name}{?temperature} · {temperature}{?}";
          }
          { type = "memory"; key = "├─ 󰘚  Memory"; keyColor = "#${palette.muted}"; }
          { type = "swap"; key = "├─ 󰓡  Swap"; keyColor = "#${palette.muted}"; }
          { type = "disk"; key = "├─ 󰋊  Disk"; keyColor = "#${palette.muted}"; }
          {
            type = "display";
            key = "├─ 󰍹  Display(s)";
            keyColor = "#${palette.muted}";
            format = "{name} · {width}x{height} @ {refresh-rate}Hz";
          }
          { type = "battery"; key = "└─ 󰂄  Battery"; keyColor = "#${palette.muted}"; }
          "break"

          { type = "custom"; format = "{#38;2;${highlightSgr}}󰖟   Network{#}"; }
          { type = "localip"; key = "├─ 󰩠  Local IP"; keyColor = "#${palette.muted}"; }
          { type = "wifi"; key = "└─ 󰖩  WiFi"; keyColor = "#${palette.muted}"; format = "{ssid} ({signal-quality})"; }
          "break"
        ];
      };
    };

    programs.starship = lib.mkIf cfg.starship.enable {
      enable = true;
      enableBashIntegration = true;
      settings = lib.mapAttrsRecursive (_: lib.mkDefault) {
        command_timeout = 100;
        format = lib.concatStrings [
          "$time"
          "$directory"
          (lib.optionalString cfg.starship.git.enable
            "$git_branch$git_commit$git_state$git_metrics$git_status")
          "$cmd_duration"
          "$character"
        ];
        add_newline = true;
        git_branch.disabled = !cfg.starship.git.enable;
        git_commit.disabled = !cfg.starship.git.enable;
        git_state.disabled = !cfg.starship.git.enable;
        git_status.disabled = !cfg.starship.git.enable;
        # Starship's Git metrics module is disabled by default.
        git_metrics.disabled = true;
        directory = {
          truncation_length = 3;
          truncate_to_repo = false;
          style = "bold #${palette.highlight}";
        };
        cmd_duration = {
          min_time = 2000;
          style = "bold #${palette.muted}";
          format = "[took $duration ]($style)";
        };
        time = {
          disabled = false;
          time_format = "%I:%M:%S %p";
          style = "bold #${palette.muted}";
          format = "[$time]($style) ";
        };
        character = {
          success_symbol = "[⮐](bold #${palette.highlight})\n[➜](bold #${palette.highlight})";
          error_symbol = "[⮐](bold #${palette.error})\n[➜](bold #${palette.error})";
        };
      };
    };

  };
}
