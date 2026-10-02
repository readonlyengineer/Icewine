{ lib, pkgs, osConfig, ... }:
let
  theme = pkgs.stdenvNoCC.mkDerivation {
    pname = "tokyonight-gtk-theme";
    version = "0-unstable-2025-10-23";

    src = pkgs.fetchFromGitHub {
      owner = "Fausto-Korpsvart";
      repo = "Tokyonight-GTK-Theme";
      rev = "6c340e058e84c1975a038a8e5d1e384477225dc0";
      hash = "sha256-7H2n9wTaW8Db1RejWK071ITV1j5KIuzfql0Tx9WT6zM=";
    };

    nativeBuildInputs = [ pkgs.sassc ];
    buildInputs = [ pkgs.gnome-themes-extra ];

    postPatch = "patchShebangs themes/install.sh";
    installPhase = ''
      mkdir -p $out/share/themes
      themes/install.sh \
        --name Tokyonight \
        --color dark \
        --size standard \
        --theme default \
        --dest $out/share/themes
      rm -r $out/share/themes/Tokyonight-Dark/gtk-2.0
    '';
  };
in {
  config = lib.mkIf osConfig.services.icewine.gtk.enable {
    # The CLI owns settings.ini and gtk.css; GTK theme assets remain installed.
    gtk.theme.package = lib.mkDefault theme;
    home.packages = [ theme ];
  };
}
