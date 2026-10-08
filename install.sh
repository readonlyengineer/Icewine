#!/usr/bin/env bash
set -euo pipefail

if [[ $(id -u) == 0 ]]; then
    echo "Run this script as your desktop user, without sudo." >&2
    exit 1
fi
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
printf 'Terminals: 1) Kitty  2) Alacritty  3) Both  4) Neither\nUnselected terminals will be removed if installed.\n'
while true; do
    read -r -p 'Choose [1]: ' choice
    case ${choice:-1} in
        1) terminals=(kitty); unwanted=(alacritty); break ;;
        2) terminals=(alacritty); unwanted=(kitty); break ;;
        3) terminals=(kitty alacritty); unwanted=(); break ;;
        4) terminals=(); unwanted=(kitty alacritty); break ;;
        *) echo 'Choose 1, 2, 3 or 4.' >&2 ;;
    esac
done
editor_file=${XDG_CONFIG_HOME:-$HOME/.config}/icewine/editor
editor=nano
if [[ -f $editor_file ]]; then editor=; IFS= read -r editor < "$editor_file" || true; fi
case $editor in
    nano) editor_choice=1 ;;
    nvim) editor_choice=2 ;;
    *) echo "Invalid editor selection in $editor_file; choose Nano or Neovim." >&2; exit 1 ;;
esac
printf 'Editors: 1) Nano  2) Neovim  3) Both\nInstalled editors will not be removed.\n'
while true; do
    read -r -p "Choose [$editor_choice]: " choice
    case ${choice:-$editor_choice} in
        1) editors=(nano); editor=nano; break ;;
        2) editors=(neovim); editor=nvim; break ;;
        3)
            editors=(nano neovim)
            while true; do
                read -r -p "Default editor: 1) Nano  2) Neovim [$editor_choice]: " choice
                case ${choice:-$editor_choice} in
                    1) editor=nano; break ;;
                    2) editor=nvim; break ;;
                    *) echo 'Choose 1 or 2.' >&2 ;;
                esac
            done
            break ;;
        *) echo 'Choose 1, 2 or 3.' >&2 ;;
    esac
done
sudo pacman -Syu --needed base-devel python
distro=$(python -c 'import platform; print(platform.freedesktop_os_release().get("ID", ""))')

build_dir=$(mktemp -d)
trap 'rm -rf -- "$build_dir"' EXIT
git archive --format=tar.gz --prefix=icewine/ HEAD -o "$build_dir/icewine.tar.gz"
tar -xzf "$build_dir/icewine.tar.gz" -C "$build_dir" --strip-components=3 icewine/packaging/arch
cd -- "$build_dir"
SRCDEST="$build_dir" makepkg -sf
package_list=$(makepkg --packagelist)
packages=()
while IFS= read -r package; do
    case "${package##*/}" in
        *-debug-*) ;;
        icewine-cachyos-fish-*)
            if [[ $distro == cachyos ]]; then packages+=("$package"); fi ;;
        icewine-*) packages+=("$package") ;;
    esac
done <<< "$package_list"
if (( ${#packages[@]} == 0 )); then
    echo "No Icewine package was produced." >&2
    exit 1
fi
sudo pacman -U "${packages[@]}"
sudo pacman -S --needed "${editors[@]}" "${terminals[@]}"
printf '%s\n' "$editor" > "$build_dir/editor"
install -Dm644 "$build_dir/editor" "$editor_file"
remove=()
for terminal in "${unwanted[@]}"; do
    if pacman -Qq "$terminal" >/dev/null 2>&1; then remove+=("$terminal"); fi
done
if (( ${#remove[@]} )); then sudo pacman -R "${remove[@]}"; fi
sudo install -d -m0755 -o "$(id -u)" -g "$(id -g)" /var/lib/icewine/sddm
cat > "$build_dir/sddm.conf" <<'EOF'
[General]
DisplayServer=x11
InputMethod=qtvirtualkeyboard
[Theme]
Current=icewine
EOF
sudo install -Dm644 "$build_dir/sddm.conf" /etc/sddm.conf.d/90-icewine.conf
icewine init
sudo systemctl enable sddm.service
sudo systemctl set-default graphical.target
printf '\nInstalled. Reboot when ready, then select Icewine in SDDM. TTY launch: icewine-session\n'
