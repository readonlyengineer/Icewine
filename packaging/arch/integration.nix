# Developer integration target: produces real makepkg archives, without a host install.
{ pkgs, src }:
let
  plugins = pkgs.fetchurl {
    url = "https://codeload.github.com/yazi-rs/plugins/tar.gz/4dc7f1b6458c2578f4494f10d468c68c1082214f";
    sha256 = "0e65f2858d06c0889a652be1c400c2df02f0cbda782dc452da52dd0cd6e27867";
  };
in pkgs.stdenv.mkDerivation {
  pname = "icewine-native-packages";
  version = "0.1";
  inherit src;
  cargoRoot = "manager";
  cargoDeps = pkgs.rustPlatform.importCargoLock { lockFile = ../../manager/Cargo.lock; };
  dontConfigure = true;
  dontInstall = true;
  dontWrapQtApps = true;
  nativeBuildInputs = [ pkgs.pacman pkgs.libarchive pkgs.fakeroot
    (pkgs.python3.withPackages (python: [ python.vdf ])) pkgs.fish pkgs.lua pkgs.zstd
    pkgs.qt6.qtdeclarative pkgs.cargo pkgs.rustc pkgs.rustPlatform.cargoSetupHook ];
  buildPhase = ''
  export HOME="$TMPDIR/home"
  export CARGO_NET_OFFLINE=true
  mkdir -p "$HOME" work/icewine $out
  cp -r ${src}/. work/icewine/
  chmod -R u+w work
  tar -czf work/icewine.tar.gz -C work icewine
  cp work/icewine/packaging/arch/PKGBUILD work/
  cp ${plugins} work/yazi-plugins-4dc7f1b6458c2578f4494f10d468c68c1082214f.tar.gz
  cat > work/makepkg.conf <<'EOF'
  CARCH=x86_64
  CHOST=x86_64-pc-linux-gnu
  BUILDENV=(!distcc !color !ccache !check !sign)
  OPTIONS=(!strip docs !libtool !staticlibs emptydirs !zipman !purge !debug !lto)
  INTEGRITY_CHECK=(sha256)
  PKGEXT=.pkg.tar.zst
  SRCEXT=.src.tar.gz
  COMPRESSZST=(zstd -c -T1)
  EOF
  # This Nix toolchain has no installed Arch packages. Query an honest empty DB
  # for .BUILDINFO rather than the host's absent /etc/pacman.conf or fake packages.
  mkdir -p work/pacman-db/local
  printf '[options]\nArchitecture=auto\n' > work/pacman.conf
  cat > work/pacman-query <<EOF
  #!${pkgs.runtimeShell}
  exec ${pkgs.pacman}/bin/pacman --config "$PWD/work/pacman.conf" --dbpath "$PWD/work/pacman-db" "\$@"
  EOF
  chmod +x work/pacman-query
  export PACMAN="$PWD/work/pacman-query"
  printf '%s\n' "$PATH" > "$out/nix-toolchain-path"
  cd work
  # --nodeps verifies package production only; target pacman transactions are separate.
  makepkg --nodeps --nosign --config "$PWD/makepkg.conf"
  for archive in *.pkg.tar.zst; do
    bsdtar -tf "$archive" > "$out/$archive.files"
    bsdtar -xOf "$archive" .PKGINFO > "$out/$archive.PKGINFO"
    cp "$archive" "$out/"
  done
  # These copies are test inputs; leave the native /usr/bin/env shebangs in archives.
  patchShebangs icewine/packaging/arch/command icewine/packaging/arch/session
  python icewine/tests/arch-package.py "$PWD/icewine" "$PWD/pkg/icewine" "$PWD/pkg/icewine-session" "$PWD/pkg/icewine-sddm"
  python icewine/tests/sddm-palette.py "$PWD/pkg/icewine-sddm/usr/share/sddm/themes/icewine/theme/Palette.qml" \
    ${pkgs.qt6.qtdeclarative}/bin/qml ${pkgs.qt6.qtdeclarative}/lib/qt-6/qml
'';
}
