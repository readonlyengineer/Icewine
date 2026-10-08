# Arch Linux and CachyOS

Native desktop packaging is experimental. Package production is checked separately
from installed Arch/CachyOS sessions; neither target is hardware-qualified yet.
The installer configures SDDM; keep TTY recovery and any fallback desktop available.
Icewine does not configure users, login shells, hardware permissions or other
host services.

On the target, enable Multilib for native Steam. From a committed Icewine checkout,
run as your normal desktop user:

```sh
bash install.sh
```

The installer performs a full system upgrade, installs `base-devel` and `python`,
builds the committed revision in a temporary directory and installs Icewine and
its SDDM theme. It offers Kitty, Alacritty, Ghostty or Neither, and Nano, Neovim
or Vim. Unselected terminal/editor packages are removed with normal Pacman
dependency checks and confirmation. An existing editor default is kept when
accepting its prompt. Neovim and Vim use their own configurations, without
Icewine plugins. If multiple terminals are installed manually, Kitty is preferred,
then Alacritty, then Ghostty. Neither leaves terminal commands to your own PATH
overrides; Icewine's terminal actions need a configured terminal. Alacritty and
Ghostty do not receive Icewine's Kitty theme configuration.
PCManFM-Qt is included as an additional graphical application; Yazi remains the
default. Open **PCManFM-Qt (Icewine)** to use the terminal palette without a terminal
emulator. Existing PCManFM-Qt instances must exit before launching the themed
entry or picking up a new theme; settings use its separate `icewine` profile.
See the main README for styling overrides and reset behaviour.
On CachyOS it also installs Fish integration; Arch shells remain user-managed.
Pacman still prompts for administrator approval. The upstream Yazi mount source
is fixed and checksum-verified.

Reboot when ready, then select **Icewine** in SDDM. The installer enables SDDM and
graphical boot without starting or restarting the greeter. An existing display
manager service alias must be disabled before enabling SDDM. You can also launch
from a logged-in TTY with `icewine-session`.
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
your normal PATH. Change the native editor without privileged edits:

```sh
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/icewine"
printf 'nvim\n' > "${XDG_CONFIG_HOME:-$HOME/.config}/icewine/editor" # or nano/vim
```

`icewine-editor` and the **Icewine Text Editor** Open With entry use that selection;
the graphical entry uses Icewine's selected terminal. Existing `EDITOR`/`VISUAL`
overrides are respected by terminal tools such as Yazi. Choose the entry in
PCManFM-Qt's Open With dialogue and remember it for a file type if wanted; Icewine
does not replace your MIME defaults, including HTML/browser associations. Use `~/.config/uwsm/env-icewine` for session overrides, such as
`export ICEWINE_STEAM_ENABLED=false`. Host authentication policy is included through
`/etc/pam.d/system-auth`; no login manager or PAM bypass is installed.

Ordinary Arch users manage their own shells. On CachyOS, the installer includes the
`icewine-cachyos-fish` package for Starship and a Fastfetch greeting. It preserves
host/user greeting and prompt functions and `STARSHIP_CONFIG`; it never changes
your login shell. NixOS retains its existing Bash/ble.sh integration.

The installer selects the theme and Qt virtual keyboard in
`/etc/sddm.conf.d/90-icewine.conf`, using SDDM's X11 greeter. Icewine sessions use
Wayland. Existing settings in `/etc/sddm.conf` take precedence over this snippet;
remove conflicting theme/input-method/display-server settings if needed.
Icewine publishes a theme ID to `/var/lib/icewine/sddm/theme.ini`, in a directory
owned by the installing desktop user; the login screen uses packaged palettes.
This shared selection supports one desktop user.

To remove Icewine, first log into the fallback desktop, restore any selected SDDM
theme, remove `/etc/sddm.conf.d/90-icewine.conf`, and remove the Icewine packages
with `pacman -R`. User configuration, theme state and wallpaper data are retained;
back them up before
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
