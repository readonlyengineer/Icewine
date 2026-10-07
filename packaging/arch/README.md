# Arch Linux and CachyOS

Native desktop packaging is experimental. Package production is checked separately
from installed Arch/CachyOS sessions; neither target is hardware-qualified yet.
Use the host's existing login manager and retain a working fallback desktop.
Icewine does not configure users, login shells, hardware permissions or host services.

On the target, enable Multilib for native Steam and install `base-devel` and
`python`. From a committed Icewine checkout, prepare and build the local package:

```sh
git archive --format=tar.gz --prefix=icewine/ HEAD -o packaging/arch/icewine.tar.gz
cd packaging/arch
makepkg -s
```

The local source archive is your chosen revision; the upstream Yazi mount source
is fixed and checksum-verified. Package installation is a separate administrator
action: install `icewine-0.1-1-x86_64.pkg.tar.zst` with `pacman -U`.
Keep the host's PipeWire/WirePlumber, logind, polkit, UDisks, UPower and power
profiles services available. Networking controls require NetworkManager;
Bluetooth controls require BlueZ. Device/backlight/i2c permissions remain host policy.
Keep Quickshell and Qt coherent with the distribution's normal full upgrades.

Run `icewine init` as the desktop user before selecting **Icewine** at login.
Existing incompatible Hyprland entries cause a reported conflict: back up and
move them before init. Editable defaults are kept in your XDG configuration and
data directories; untouched defaults update at the next Icewine login. Package
implementation files live in `/usr/share/icewine`. Change themes with
`icewine theme dracula`; native application entry points can be overridden through
your normal PATH. Use `~/.config/uwsm/env-icewine` for session overrides, such as
`export ICEWINE_STEAM_ENABLED=false`. Host authentication policy is included through
`/etc/pam.d/system-auth`; no login manager or PAM bypass is installed.

Ordinary Arch users manage their own shells. On CachyOS, optionally install the
`icewine-cachyos-fish` package for Starship and a Fastfetch greeting. It preserves
host/user greeting and prompt functions and `STARSHIP_CONFIG`; it never changes
your login shell. NixOS retains its existing Bash/ble.sh integration.

For an existing SDDM host, optionally install `icewine-sddm`. An administrator
must create `/var/lib/icewine/sddm` owned by the desktop user, mode 0755, and select
`Current=icewine` under `[Theme]` in an SDDM configuration file. Set
`InputMethod=qtvirtualkeyboard` under `[General]`. Icewine publishes only a theme
ID to `/var/lib/icewine/sddm/theme.ini`; the login screen uses packaged palettes.
This shared selection supports one desktop user; use a fixed login-screen theme
or revisit ownership if multiple users need to publish. Keep the previous SDDM
selection available for recovery.

To remove Icewine, first log into the fallback desktop, restore any selected SDDM
theme and remove the optional packages and `icewine` with `pacman -R`. User
configuration, theme state and wallpaper data are retained; back them up before
manually removing them. No uninstall hook deletes user files.

Installed login/logout, unlock, sleep/resume, portals, controls, screenshots,
Steam launch/shortcuts, SDDM updates and package update/removal still require
validation on both target distributions. Flatpak Steam and handhelds are outside
this qualification round.

The developer Nix integration target produces the same makepkg archives using a
Nix toolchain and `--nodeps`. Its `.BUILDINFO` accurately records an empty Arch
package database; the output also records the Nix toolchain PATH. This verifies
package production and focused checks, not Arch/CachyOS dependency transactions
or Qt ABI compatibility. Normal target-host `makepkg` records its installed
native packages as usual.
