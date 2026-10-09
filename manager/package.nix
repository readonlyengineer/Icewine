{ rustPlatform }:
rustPlatform.buildRustPackage {
  pname = "icewine-manage";
  version = "0.1.0";
  src = ./.;
  cargoLock.lockFile = ./Cargo.lock;
}
