{
  description = "Unified Hyprland desktop for Desktop/Laptop/Handheld/HTPC; developed NixOS-first";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    nix-flatpak.url = "github:gmodena/nix-flatpak";
    home-manager.url = "github:nix-community/home-manager";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";
  };
  outputs = { self, nixpkgs, home-manager, nix-flatpak }: {
    nixosModules.default = {
      imports = [ home-manager.nixosModules.home-manager nix-flatpak.nixosModules.nix-flatpak ./modules/default.nix ];
      home-manager.extraSpecialArgs.nixpkgsLastModified = nixpkgs.lastModified or 0;
    };
    lib.palette = import ./theme/palette.nix;
    checks.x86_64-linux = import ./tests/checks.nix { inherit self nixpkgs; };
  };
}
