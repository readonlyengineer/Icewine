{ pkgs }:
pkgs.writeShellScriptBin "icewine-steam-shortcuts" ''
  exec ${(pkgs.python3.withPackages (python: [ python.vdf ]))}/bin/python3 ${./steam-shortcuts} "$@"
''
