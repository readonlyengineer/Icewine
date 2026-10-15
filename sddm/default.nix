{ runCommand, kdePackages, python3, theme ? null }:
runCommand "icewine-breeze-sddm-theme" { } ''
  ${python3}/bin/python3 ${./package.py} \
    ${kdePackages.plasma-desktop}/share/sddm/themes/breeze \
    "$out/share/sddm/themes/breeze" "$out/share/icewine/sddm/kdeglobals" \
    ${../scripts/theme} ${../theme/assets} ${if theme == null then "''" else theme}
''
