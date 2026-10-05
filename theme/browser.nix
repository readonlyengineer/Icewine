{ pkgs }:
let
  executable = pkgs.writeShellScriptBin "icewine-pywalfox" ''
    export XDG_CACHE_HOME="''${XDG_CONFIG_HOME:-$HOME/.config}/icewine"
    exec ${pkgs.lib.getExe pkgs.pywalfox-native} "$@"
  '';
  manifest = pkgs.writeTextDir "lib/mozilla/native-messaging-hosts/pywalfox.json" (builtins.toJSON {
    name = "pywalfox";
    description = "Upstream Pywalfox using Icewine's published palette";
    path = "${executable}/bin/icewine-pywalfox";
    type = "stdio";
    allowed_extensions = [ "pywalfox@frewacom.org" ];
  });
in pkgs.symlinkJoin {
  name = "icewine-pywalfox";
  paths = [ executable manifest ];
}
