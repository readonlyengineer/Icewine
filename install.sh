#!/bin/sh
# Experimental source bootstrap; run as the desktop user from a terminal.
# Parse the entire compound command before replacing the piped script input.
{
set -eu
fail() { printf '%s\n' "Icewine: $*" >&2; exit 1; }
revision=${1:-}
[ "$#" -le 1 ] || fail 'Usage: sh install.sh [FULL_COMMIT_ID]'
if [ -n "$revision" ]; then
    case $revision in *[!0-9a-f]*) fail 'Expected a lowercase full Git commit ID' ;; esac
    [ "${#revision}" = 40 ] || fail 'Expected a full 40-character Git commit ID'
fi
[ "$(id -u)" != 0 ] || fail 'Run as your desktop user, never root'
ID=$(sed -n 's/^ID=//p' /etc/os-release) || fail 'Cannot identify the platform'
ID=$(printf '%s' "$ID" | tr -d '"')
case ${ID:-} in
    arch|cachyos) ;;
    nixos) fail 'NixOS: import the Icewine module in your host configuration, rebuild, then icewine' ;;
    *) fail 'Experimental bootstrap supports only Arch/CachyOS x86_64' ;;
esac
[ "$(uname -m)" = x86_64 ] || fail 'Experimental bootstrap supports only x86_64'
# Reopen the controlling terminal: stdin may still be the curl script pipe.
exec </dev/tty >/dev/tty 2>&1 || exit 1
for tool in pacman sudo tar sha256sum mktemp sed tr loginctl; do
    command -v "$tool" >/dev/null || fail "Missing base-system tool: $tool"
done
[ -z "${WAYLAND_DISPLAY:-}${DISPLAY:-}${HYPRLAND_INSTANCE_SIGNATURE:-}" ] || fail 'Start onboarding from a local TTY outside any desktop session'
[ "$(loginctl show-session self -p Type --value)" = tty ] || fail 'A local TTY login is required'
[ "$(loginctl show-session self -p Remote --value)" = no ] || fail 'Remote onboarding is unsupported'
[ "$(loginctl show-session self -p Active --value)" = yes ] || fail 'Switch to this TTY before onboarding'
sessions=$(loginctl list-sessions --no-legend --no-pager) || fail 'Cannot check existing sessions'
printf '%s\n' "$sessions" | while read -r session rest; do
    [ -n "$session" ] || continue
    kind=$(loginctl show-session "$session" -p Type --value) || fail 'Cannot inspect an existing session'
    case $kind in
        wayland|x11) fail 'Preserve existing graphical sessions; log out before onboarding' ;;
    esac
done
printf '%s\n' 'Experimental Icewine onboarding (Arch/CachyOS x86_64).' \
    'A full distro upgrade (pacman -Syu) precedes prerequisite installation and source builds.' \
    'Build/session prerequisites: base-devel git python go hyprland kitty and a pacman Rust provider.' \
    'Then: install icewine, icewine-session and icewine-hyprmon with their runtime dependencies.' \
    'Core runtime includes Quickshell/Qt, theme/fonts, bindings, UWSM, audio and portals.' \
    'Pacman shows every dependency and asks before both prerequisite transactions.' \
    'Prepare missing core Hyprland/Quickshell/wallpaper defaults and the saved/default theme.' \
    'Personal files are preserved; these prerequisite/default writes remain after cancellation.' \
    'Then automatically start the Icewine onboarding session and its full TUI.' \
    'Optional utilities wait for session-stage Apply; successful Apply leaves the desktop running.' \
    'Keep a recovery TTY (Ctrl+Alt+F2). No login service changes until final Apply; no automatic reboot.' \
    'Accept prerequisite installation and core-default preparation? Type yes to continue:'
read -r answer || exit 1
[ "$answer" = yes ] || exit 0
for package in hyprmon hyprmon-bin; do
    if pacman -Qq "$package" >/dev/null 2>&1; then
        fail "Preserve installed $package; resolve its Lua compatibility before source onboarding"
    fi
done
if command -v hyprmon >/dev/null; then
    owner=$(pacman -Qqo "$(command -v hyprmon)") || fail 'Preserve existing unowned HyprMon'
    [ "$owner" = icewine-hyprmon ] || fail "Preserve HyprMon owned by $owner"
fi
work=$(mktemp -d "${TMPDIR:-/tmp}/icewine-install.XXXXXXXX")
stage=prerequisites
# Retain partial work for diagnosis/retry; never remove user files or old packages.
trap 'code=$?; printf "Stage: %s; exit: %s; preparation retained at %s\n" "$stage" "$code" "$work"; if [ "$code" != 0 ]; then printf "%s\n" "Earlier packages may have changed. Resolve the stage error and rerun the bootstrap; keep this directory for diagnosis."; fi' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
printf 'Preparation directory: %s\n' "$work"
rust_package=
if ! pacman -T cargo >/dev/null 2>&1; then
    if command -v cargo >/dev/null && command -v rustc >/dev/null \
        && cargo --version >/dev/null 2>&1 && rustc --version >/dev/null 2>&1; then
        fail 'Working Rust toolchain is outside pacman; preserve it and install a pacman Cargo provider before retrying'
    fi
    if command -v rustup >/dev/null; then rust_package=rustup; else rust_package=rust; fi
fi
sudo pacman -Syu --needed base-devel git python go hyprland kitty $rust_package
for tool in git makepkg cargo rustc python3 go; do
    command -v "$tool" >/dev/null || fail "Prerequisite installation did not provide $tool"
done
stage=acquisition
if [ -z "$revision" ]; then
    remote=$(git ls-remote https://github.com/readonlyengineer/Icewine.git HEAD) || fail 'Cannot resolve latest source'
    read -r revision ref <<EOF
$remote
EOF
    case $revision in *[!0-9a-f]*|'') fail 'Invalid latest source revision' ;; esac
    [ "${#revision}" = 40 ] && [ "$ref" = HEAD ] || fail 'Invalid latest source revision'
fi
printf 'Icewine source commit: %s\n' "$revision"
git init --quiet "$work/source"
git -C "$work/source" -c fetch.fsckObjects=true fetch --quiet --depth=1 \
    https://github.com/readonlyengineer/Icewine.git "$revision"
[ "$(git -C "$work/source" rev-parse FETCH_HEAD)" = "$revision" ] || fail 'Fetched revision mismatch'
git -C "$work/source" fsck --strict
mkdir "$work/build"
git -C "$work/source" archive --format=tar.gz --prefix=icewine/ "$revision" > "$work/build/icewine.tar.gz"
git -C "$work/source" show "$revision:packaging/arch/PKGBUILD" > "$work/build/PKGBUILD"
printf '%s\n' "$revision" > "$work/build/source-revision"
stage=toolchain
cd "$work/build"
if ! cargo --version >/dev/null 2>&1 || ! rustc --version >/dev/null 2>&1; then
    command -v rustup >/dev/null || fail 'Rust toolchain is unusable and no rustup is available'
    # A private toolchain fixes an unconfigured proxy without changing user defaults.
    export RUSTUP_HOME="$work/rustup" RUSTUP_TOOLCHAIN=stable
    rustup toolchain install stable --profile minimal --no-self-update
    cargo --version && rustc --version || fail 'Stable Rust toolchain is unusable'
fi
stage=build
(cd "$work/build"; sha256sum icewine.tar.gz > source-archive.sha256; makepkg --nosign)
stage=hyprmon
mkdir "$work/hyprmon"
cp "$work/build/src/icewine/packaging/arch/hyprmon/"* "$work/hyprmon/"
(cd "$work/hyprmon"; makepkg --nosign)
# Install the real desktop/TUI runtime together with compatible HyprMon.
# Login and optional utility archives remain for explicit session-stage Apply.
set -- "$work/build"/icewine-[0-9]*.pkg.tar.* \
    "$work/build"/icewine-session-[0-9]*.pkg.tar.* \
    "$work/hyprmon"/icewine-hyprmon-[0-9]*.pkg.tar.*
[ "$#" = 3 ] || fail 'Expected core, session and HyprMon archives'
for archive in "$@"; do
    [ -f "$archive" ] && [ ! -L "$archive" ] || fail "Expected regular archive: $archive"
done
stage=core-install
sudo pacman -U "$@"
cp "$work/build/src/icewine/packaging/arch/onboard" "$work/onboard"
stage=session
printf 'Retry without rebuilding: sh "%s/onboard" "%s/build" "%s"\n' "$work" "$work" "$revision"
# makepkg owns source validation and the locked Rust build; launch only on success.
sh "$work/onboard" "$work/build" "$revision"

exit
}
