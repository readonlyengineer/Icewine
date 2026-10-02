{ pkgs, lib, gitEnable, nixpkgsLastModified ? 0 }:
let
  palettes = {
    tokyo-night = import ./palette.nix;
    dracula = import ./dracula.nix;
  };
  render = palette: template: builtins.replaceStrings
    (map (name: "@${name}@") (builtins.attrNames palette))
    (builtins.attrValues palette)
    (builtins.readFile template);
  toml = pkgs.formats.toml { };
  files = lib.mapAttrs (themeId: palette:
    let
      shell = import ./shell-settings.nix { inherit palette gitEnable nixpkgsLastModified; };
      gtkName = if themeId == "tokyo-night" then "Tokyonight-Dark" else "Adwaita-dark";
      gtkSettings = pkgs.writeText "${themeId}-gtk-settings.ini" ''
        [Settings]
        gtk-theme-name=${gtkName}
        gtk-application-prefer-dark-theme=1
      '';
    in {
      "Palette.qml" = pkgs.writeText "${themeId}-Palette.qml" (render palette ../quickshell/theme/Palette.qml.in);
      "Theme.lua" = pkgs.writeText "${themeId}-Theme.lua" ''
        hl.config({ general = { col = {
          active_border = { colors = { "rgba(${palette.highlight}ee)", "rgba(${palette.secondaryHighlight}ee)" }, angle = 45 },
          inactive_border = "rgba(${palette.background}aa)",
        } } })
      '';
      "kitty.conf" = pkgs.writeText "${themeId}-kitty.conf" (render palette ./kitty.conf.in);
      "gtk.css" = pkgs.writeText "${themeId}-gtk.css" (render palette ./gtk.css.in);
      "gtk-settings.ini" = gtkSettings;
      "yazi-theme.toml" = toml.generate "${themeId}-yazi-theme.toml" {
        mode = {
          normal_main = { fg = "#${palette.highlight}"; bg = "#${palette.highlightDark}"; bold = true; };
          normal_alt = { fg = "#${palette.highlight}"; bg = "#${palette.highlightDark}"; };
        };
      };
      "fastfetch.jsonc" = pkgs.writeText "${themeId}-fastfetch.jsonc" (builtins.toJSON shell.fastfetch);
      "starship.toml" = toml.generate "${themeId}-starship.toml" shell.starship;
      "ls-colors.sh" = pkgs.writeText "${themeId}-ls-colors.sh" ''
        export LS_COLORS='di=01;39:ex=00;39:ln=38;2;${builtins.replaceStrings [ ", " ] [ ";" ] palette.mutedRgb}:or=01;31:mi=01;31'
      '';
    }
  ) palettes;
  installTheme = themeId: themeFiles:
    let destination = "$out/share/icewine/themes/${themeId}";
    in ''
      mkdir -p ${destination}
      ${lib.concatStringsSep "\n" (lib.mapAttrsToList (name: source:
        "ln -s ${source} ${destination}/${name}") themeFiles)}
    '';
in pkgs.runCommand "icewine-theme-assets" { } ''
  ${lib.concatStringsSep "\n" (lib.mapAttrsToList installTheme files)}
''
