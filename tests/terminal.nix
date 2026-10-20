{ self, nixpkgs, manager }:
let
  pkgs = nixpkgs.legacyPackages.x86_64-linux;
in pkgs.runCommand "icewine-manager-contract-checks" { nativeBuildInputs = [ pkgs.python3 ]; } ''
  python3 ${./bootstrap.py} ${self}
  python3 ${./install.py} ${self}
  python3 ${./theme-cli.py} ${../scripts/theme} ${../scripts/icewine} ${self}/theme/assets
  python3 ${./manager-tty.py} ${manager}/bin/icewine-manage
  touch "$out"
''
