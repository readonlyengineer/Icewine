# Developer integration target: produces real makepkg archives, without a host install.
{ pkgs, src }:
let
  plugins = pkgs.fetchurl {
    url = "https://codeload.github.com/yazi-rs/plugins/tar.gz/4dc7f1b6458c2578f4494f10d468c68c1082214f";
    sha256 = "0e65f2858d06c0889a652be1c400c2df02f0cbda782dc452da52dd0cd6e27867";
  };
  keyboardSource = pkgs.fetchurl {
    url = "https://gitlab.gnome.org/World/Phosh/squeekboard/-/archive/v1.43.1/squeekboard-v1.43.1.tar.gz";
    sha256 = "64c73636f6d8a6ffe9f1094c4084b184db3f60ac4e02bf8bff860060308c61ab";
  };
  idleSource = pkgs.fetchurl {
    url = "https://github.com/nowrep/wljoywake/archive/refs/tags/v0.3.tar.gz";
    sha256 = "d02d0d20c6b7712a17c4891b0c28e562d6f9021de28225979453242292be8230";
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
    pkgs.meson pkgs.ninja pkgs.pkg-config pkgs.glib pkgs.wayland-scanner pkgs.gettext
    pkgs.qt6.qtdeclarative pkgs.cargo pkgs.rustc pkgs.rustPlatform.cargoSetupHook ];
  buildInputs = [ pkgs.gtk3 pkgs.gnome-desktop pkgs.wayland pkgs.wayland-protocols
    pkgs.libbsd pkgs.libxml2 pkgs.libxkbcommon pkgs.feedbackd pkgs.udev ];
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
  mkdir dependencies
  cp icewine/packaging/arch/dependencies/* dependencies/
  cp ${keyboardSource} dependencies/squeekboard-v1.43.1.tar.gz
  cp ${idleSource} dependencies/wljoywake-0.3.tar.gz
  export ICEWINE_CARGO_VENDOR=${pkgs.squeekboard.cargoDeps}
  (cd dependencies; makepkg --nodeps --nosign --config "$PWD/../makepkg.conf")
  for archive in *.pkg.tar.zst dependencies/*.pkg.tar.zst; do
    bsdtar -tf "$archive" > "$out/$(basename "$archive").files"
    bsdtar -xOf "$archive" .PKGINFO > "$out/$(basename "$archive").PKGINFO"
    cp "$archive" "$out/"
  done
  # These copies are test inputs; leave the native /usr/bin/env shebangs in archives.
  patchShebangs icewine/packaging/arch/command icewine/packaging/arch/session
  python icewine/tests/handheld.py "$PWD/icewine"
  python icewine/tests/arch-package.py "$PWD/icewine" "$PWD/pkg/icewine" "$PWD/pkg/icewine-session" "$PWD/pkg/icewine-sddm" "$PWD/pkg/icewine-handheld" "$PWD/dependencies/pkg/icewine-keyboard" "$PWD/dependencies/pkg/icewine-controller-idle"
  python icewine/tests/sddm-palette.py "$PWD/pkg/icewine-sddm/usr/share/sddm/themes/icewine/theme/Palette.qml" \
    ${pkgs.qt6.qtdeclarative}/bin/qml ${pkgs.qt6.qtdeclarative}/lib/qt-6/qml
'';
}
