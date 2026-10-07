#!/usr/bin/env bash
set -euo pipefail

if [[ $(id -u) == 0 ]]; then
    echo "Run this script as your desktop user, without sudo." >&2
    exit 1
fi
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
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
        icewine-sddm-*|*-debug-*) ;;
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
icewine init
printf '\nInstalled. From a TTY, run: icewine-session\n'
