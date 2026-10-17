# Arch Linux and CachyOS

Native packaging is experimental; installed sessions and hardware remain unqualified.
Keep a TTY and a fallback desktop available. Icewine does not configure users,
login shells, hardware permissions, networking or Bluetooth services.

Prepare prerequisites through your normal full distribution upgrade first:

```sh
sudo pacman -Syu --needed base-devel cargo python git curl
```

For a published commit containing `install.sh`, set its full commit ID:

```sh
revision=FULL_PUBLISHED_COMMIT_ID
curl -fL --proto '=https' --tlsv1.2 "https://raw.githubusercontent.com/readonlyengineer/Icewine/$revision/install.sh" | sh -s -- "$revision"
```

This candidate has not been published. The bootstrap fetches exactly that Git
commit over HTTPS, checks Git object integrity and the fetched ID, then runs
existing makepkg packaging without installing missing build dependencies.
Git/HTTPS establish source identity; no independent signature or prebuilt
release checksum is available. Inspect the script before running it if desired.
Preparation and its revision/archive hash are retained in a printed temporary
directory. The manager confirms base installation with pacman before optional
choices. Cancel before installation changes no user configuration.
If acquisition or compilation fails, fix the prerequisite and rerun; incomplete
preparation never launches the manager. Keep the prepared directory for later
optional Apply, or reopen with `ICEWINE_PACKAGE_DIR=/path/to/build icewine manage`.

The base package already requires `libcanberra`, which brings
`sound-theme-freedesktop` for Kitty's native audible bell at
`/usr/share/sounds/freedesktop/stereo/bell.oga`. Keep audio output enabled; later
overrides in `~/.config/kitty/kitty.conf` take precedence.

From a committed local checkout, the existing manual path also works. Install
its declared runtime dependencies with `makepkg -s` before installing the archive:

```sh
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
The package directory supplies optional session/Handheld archives for the first Apply.
Keep it available when selecting an integration later, or install those optional
packages from your package repository. Enable Multilib for native Steam.
Pacman and sudo request approval for host operations. Changing Steam, Gamescope
or Handheld restarts a running Icewine shell after stopping its affected helpers.

Use Tab/arrows to navigate and Space to select. Apply creates missing dotfiles;
**Overwrite existing dotfiles** replaces selected defaults without backups.
Shell Extras Apply selects Icewine in regular btop configs while preserving other
preferences. Other existing files are preserved. Cancel before Apply leaves utility choices unapplied; Appearance changes act immediately. Review the planned changes before confirming Apply. Failures can leave earlier
package/file changes; resolve the error and retry with overwrite off. Reopen with
`icewine manage`; previous successful selections are retained. On deselection,
only recorded Icewine configuration is removed and edited user files are preserved.
Desktop deselection removes only the Hyprland implementation link. Login is
host-owned; the installer no longer provides a greeter or changes boot targets.
Existing installations retain their old `/etc/sddm.conf.d/90-icewine.conf`;
review and remove it yourself when migrating away from the former integration.

Steam uses a none/native/Flatpak selector (left/right). Its Gamescope child
starts checked; disabling it retains ordinary Steam without a splash or launcher
masks. Handheld requires native Steam, Desktop and Gamescope. Flatpak Steam does
not install Bazaar. Shell Extras supplies themed Starship and Fastfetch.
Icewine keeps host `EDITOR`/`VISUAL` values. Selecting Yazi makes it the directory
default on Apply, using the host terminal through `xdg-terminal-exec`. Other MIME
defaults are preserved; disabling Yazi leaves the current association alone.

For Handheld, build the optional private controller-idle package
as your normal user before Apply:

```sh
mkdir -p dependencies
cp ../packaging/arch/dependencies/* dependencies/
(cd dependencies && makepkg -s)
cp dependencies/*.pkg.tar.zst .
ICEWINE_PACKAGE_DIR="$PWD" icewine manage
```

The shared QS keyboard uses distro `wtype`; no Squeekboard service is needed.
Before upgrading an existing Squeekboard-based Handheld session, stop its old
unit with `systemctl --user disable --now icewine-keyboard.service`, then restart
Icewine after the package update.
InputPlumber, controller device access and its normal host service must be
available. Apply installs only a named-user InputPlumber permission rule and
Icewine's helpers; it adds no kernel, driver or hardware permission policy.
Use **Overwrite existing dotfiles** to adopt the Handheld entry point when a
preserved desktop entry already exists. Deselection stops Icewine's controller
idle and routing units before removing its own permission rule; it
leaves InputPlumber and unrelated services installed.

After selecting Desktop session and applying, select **Icewine** in your host's
session picker; from a logged-in TTY run `icewine-session`. Keep
PipeWire/WirePlumber, logind, polkit, UDisks, UPower and power profiles available.
Device/backlight/i2c permissions remain host policy. Keep Quickshell and Qt
coherent with normal full distribution upgrades.

For SSH controls, use OpenSSH's native per-user service with the same socket as
the Icewine session. The card requires current OpenSSH including `ssh-add -Q`.
If you use the packaged socket unit, disable it before selecting this service
contract. Save this as `~/.config/systemd/user/ssh-agent.service`:

```ini
[Unit]
Description=Local OpenSSH agent

[Service]
Type=simple
ExecStart=/usr/bin/ssh-agent -D -a %t/ssh-agent

[Install]
WantedBy=default.target
```

Run `systemctl --user daemon-reload` and
`systemctl --user enable --now ssh-agent.service`, then start a fresh Icewine
session. Icewine sets `SSH_AUTH_SOCK=$XDG_RUNTIME_DIR/ssh-agent` only when unset;
external/forwarded agent choices are preserved and the card refuses to modify
them. The installer does not replace agent services or load keys automatically.

The developer Nix target builds the same makepkg archives with `--nodeps` and
an honest empty Arch package database. It checks packaging and manager behavior,
not target dependency transactions, Qt ABI compatibility or hardware.
