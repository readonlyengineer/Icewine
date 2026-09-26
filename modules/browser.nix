{ config, lib, ... }:
let
  cfg = config.services.icewine;
in {
  options.services.icewine.browser.flatpak = lib.mkOption {
    type = lib.types.nullOr lib.types.nonEmptyStr;
    default = "org.mozilla.firefox";
    description = "Browser Flatpak to install from Flathub and use for web links and PDFs; null leaves browser management to the host.";
  };

  config = lib.mkIf (cfg.enable && cfg.browser.flatpak != null) {
    services.flatpak = {
      enable = true;
      remotes = [
        { name = "flathub"; location = "https://dl.flathub.org/repo/flathub.flatpakrepo"; }
      ];
      packages = [ cfg.browser.flatpak ];
    };
    home-manager.users.${cfg.user}.xdg.mimeApps = {
      enable = true;
      defaultApplications = lib.genAttrs [
        "x-scheme-handler/http"
        "x-scheme-handler/https"
        "text/html"
        "application/xhtml+xml"
        "application/pdf"
      ] (_: lib.mkDefault [ "${cfg.browser.flatpak}.desktop" ]);
    };
  };
}
