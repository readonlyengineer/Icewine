{
  description = "Unified Hyprland desktop for Desktop/Laptop/Handheld/HTPC; developed NixOS-first";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };
  outputs = { self, nixpkgs }: {
    nixosModules.default = {
      imports = [ ./modules/default.nix ];
      _module.args.icewineNixpkgsLastModified = nixpkgs.lastModified or 0;
    };
    lib.palette = builtins.fromJSON (builtins.readFile ./theme/assets/themes/tokyo-night.json);
    checks.x86_64-linux = import ./tests/checks.nix { inherit self nixpkgs; };
  };
}
