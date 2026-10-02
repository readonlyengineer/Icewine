{ pkgs }:
pkgs.runCommand "icewine-theme-assets" { } ''
  mkdir -p "$out/share/icewine"
  cp -r ${./assets}/. "$out/share/icewine/"
''
