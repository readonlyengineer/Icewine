{ palette, gitEnable, nixpkgsLastModified ? 0 }:
let
  highlightSgr = builtins.replaceStrings [ ", " ] [ ";" ] palette.highlightRgb;
  kernelCommand = ''
    k=$(uname -r)
    if [ "$(readlink /run/booted-system/kernel)" = "$(readlink /run/current-system/kernel)" ]; then
      printf 'Linux %s' "$k"
    else
      printf 'Linux %s  \033[33m⚠ Restart Required\033[0m' "$k"
    fi
  '';
  nixpkgsCommand = ''
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
  fastfetch = {
    "$schema" = "https://github.com/fastfetch-cli/fastfetch/raw/master/doc/json_schema.json";
    logo = {
      type = "auto";
      color = { "1" = "#${palette.highlight}"; "2" = "#${palette.secondaryHighlight}"; };
      padding = { top = 1; right = 3; };
    };
    display = { separator = "   "; key.width = 20; };
    modules = [
      "break"
      { type = "custom"; format = "{#38;2;${highlightSgr}}󰟀   System{#}"; }
      { type = "os"; key = "├─   OS"; keyColor = "#${palette.muted}"; }
      { type = "host"; key = "├─ 󰌢  Host"; keyColor = "#${palette.muted}"; }
      { type = "command"; key = "├─ 󰌽  Kernel"; keyColor = "#${palette.muted}"; shell = "/bin/sh"; text = kernelCommand; }
      { type = "command"; key = "├─   Nixpkgs"; keyColor = "#${palette.muted}"; shell = "/bin/sh"; text = nixpkgsCommand; }
      { type = "uptime"; key = "└─ 󰔛  Uptime"; keyColor = "#${palette.muted}"; }
      "break"
      { type = "custom"; format = "{#38;2;${highlightSgr}}󰢮   Hardware{#}"; }
      { type = "cpu"; key = "├─ 󰍛  CPU"; keyColor = "#${palette.muted}";
        temp = { green = 70; yellow = 85; }; format = "{name}{?temperature} · {temperature}{?}"; }
      { type = "memory"; key = "├─ 󰘚  Memory"; keyColor = "#${palette.muted}"; }
      { type = "swap"; key = "├─ 󰓡  Swap"; keyColor = "#${palette.muted}"; }
      { type = "disk"; key = "├─ 󰋊  Disk"; keyColor = "#${palette.muted}"; }
      { type = "display"; key = "├─ 󰍹  Display(s)"; keyColor = "#${palette.muted}";
        format = "{name} · {width}x{height} @ {refresh-rate}Hz"; }
      { type = "battery"; key = "└─ 󰂄  Battery"; keyColor = "#${palette.muted}"; }
      "break"
      { type = "custom"; format = "{#38;2;${highlightSgr}}󰖟   Network{#}"; }
      { type = "localip"; key = "├─ 󰩠  Local IP"; keyColor = "#${palette.muted}"; }
      { type = "wifi"; key = "└─ 󰖩  WiFi"; keyColor = "#${palette.muted}"; format = "{ssid} ({signal-quality})"; }
      "break"
    ];
  };
  starship = {
    command_timeout = 100;
    format = "$time$directory${if gitEnable then "$git_branch$git_commit$git_state$git_metrics$git_status" else ""}$cmd_duration$character";
    add_newline = true;
    git_branch.disabled = !gitEnable;
    git_commit.disabled = !gitEnable;
    git_state.disabled = !gitEnable;
    git_status.disabled = !gitEnable;
    git_metrics.disabled = true;
    directory = { truncation_length = 3; truncate_to_repo = false; style = "bold #${palette.highlight}"; };
    cmd_duration = { min_time = 2000; style = "bold #${palette.muted}"; format = "[took $duration ]($style)"; };
    time = { disabled = false; time_format = "%I:%M:%S %p";
      style = "bold #${palette.muted}"; format = "[$time]($style) "; };
    character = {
      success_symbol = "[⮐](bold #${palette.highlight})\n[➜](bold #${palette.highlight})";
      error_symbol = "[⮐](bold #${palette.error})\n[➜](bold #${palette.error})";
    };
  };
}
