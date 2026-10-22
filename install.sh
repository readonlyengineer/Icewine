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
for tool in pacman sudo tar sha256sum mktemp sed tr; do
    command -v "$tool" >/dev/null || fail "Missing base-system tool: $tool"
done
printf '%s\n' 'Experimental Icewine onboarding (Arch/CachyOS x86_64).' \
    'First: full distro upgrade and install base-devel, git, python and a Rust provider.' \
    'Then: fetch source and build packages unprivileged; configure choices in the TUI.' \
    'Package changes remain if you cancel later. Keep a recovery TTY (Ctrl+Alt+F2).' \
    'Prepare source and packages? Type yes to continue:'
read -r answer || exit 1
[ "$answer" = yes ] || exit 0
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
sudo pacman -Syu --needed base-devel git python $rust_package
for tool in git makepkg cargo rustc python3; do
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
stage=manager
# makepkg owns source validation and the locked Rust build; launch only on success.
ICEWINE_PACKAGE_DIR="$work/build" "$work/build/src/icewine/manager/target/release/icewine-manage" \
    --bootstrap "$work/build" "$revision"

exit
}
