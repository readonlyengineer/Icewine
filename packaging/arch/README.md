# Arch Linux and CachyOS

Native packaging is experimental; installed sessions and hardware remain unqualified.
Keep a TTY and a fallback desktop available. Icewine does not configure users,
login shells, hardware permissions, networking or Bluetooth services.

From a committed Icewine checkout, bootstrap as your normal user:

```sh
sudo pacman -Syu --needed base-devel cargo python
mkdir -p build
git archive --format=tar.gz --prefix=icewine/ HEAD -o build/icewine.tar.gz
cp packaging/arch/PKGBUILD build/
cd build
makepkg -s
sudo pacman -U ./icewine-0.1-1-x86_64.pkg.tar.zst
ICEWINE_PACKAGE_DIR="$PWD" icewine manage
```

The base package supplies Quickshell, the manager and necessary runtime tools.
Apply installs and configures checked utilities; new selections start unchecked.
The package directory supplies optional session/login/Handheld archives for the first Apply.
Keep it available when selecting an integration later, or install those optional
packages from your package repository. Enable Multilib for native Steam.
Pacman and sudo request approval for host operations. Changing Steam, Gamescope
or Handheld restarts a running Icewine shell after stopping its affected helpers.

Use Tab/arrows to navigate and Space to select. Apply creates missing dotfiles;
**Overwrite existing dotfiles** replaces selected defaults without backups.
Existing files are otherwise preserved. Cancel changes nothing. Reopen with
`icewine manage`; previous successful selections are retained. On deselection,
only recorded Icewine configuration is removed and edited user files are preserved.
Desktop deselection removes only the Hyprland implementation link. Login
deselection removes the owned SDDM snippet, leaving SDDM enabled and the boot
target unchanged.

Steam uses a none/native/Flatpak selector (left/right). Its Gamescope child
starts checked; disabling it retains ordinary Steam without a splash or launcher
masks. Handheld requires native Steam, Desktop and Gamescope. Flatpak Steam does
not install Bazaar. Shell Extras supplies themed Starship and Fastfetch.
Icewine keeps host `EDITOR`/`VISUAL` values and MIME defaults.

For Handheld, build the optional private keyboard and controller-idle packages
as your normal user before Apply:

```sh
mkdir -p dependencies
cp ../packaging/arch/dependencies/* dependencies/
(cd dependencies && makepkg -s)
cp dependencies/*.pkg.tar.zst .
ICEWINE_PACKAGE_DIR="$PWD" icewine manage
```

The private keyboard applies the fullscreen overlay patch and uses the distro
Squeekboard resources; it does not replace the distro executable or data.
InputPlumber, controller device access and its normal host service must be
available. Apply installs only a named-user InputPlumber permission rule and
Icewine's helpers; it adds no kernel, driver or hardware permission policy.
Use **Overwrite existing dotfiles** to adopt the Handheld entry point when a
preserved desktop entry already exists. Deselection stops Icewine's controller
idle, keyboard and routing units before removing its own permission rule; it
leaves InputPlumber and unrelated services installed.

After selecting Desktop session and Login screen and applying, select **Icewine**
in SDDM; from a logged-in TTY run `icewine-session`. Keep PipeWire/WirePlumber,
logind, polkit, UDisks, UPower and power profiles available. Device/backlight/i2c
permissions remain host policy. Keep Quickshell and Qt coherent with normal
full distribution upgrades.

SDDM styling uses `/etc/sddm.conf.d/90-icewine.conf` with its X11 greeter;
Icewine sessions use Wayland. Existing `/etc/sddm.conf` settings take precedence.
Icewine publishes theme colours to `/var/lib/icewine/sddm/theme.ini`, shared by
one desktop user. Themes change with `icewine theme dracula`.

The developer Nix target builds the same makepkg archives with `--nodeps` and
an honest empty Arch package database. It checks packaging and manager behavior,
not target dependency transactions, Qt ABI compatibility or hardware.
