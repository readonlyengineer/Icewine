# Icewine

Icewine is a unified Hyprland desktop for desktops, laptops, handhelds and HTPCs,
developed NixOS-first.

It is deeply experimental; it will move fast and break things. Use at your own risk.

Experimental native desktop packages for [Arch Linux and CachyOS](packaging/arch/README.md)
reuse the existing login manager; installed-session and hardware qualification remain pending.

## Install on NixOS

Icewine assumes you are using nix-command and flakes.

```nix
nix.settings.experimental-features = [ "nix-command" "flakes" ];
```

Icewine assumes you bring your own NixOS security and update policy, and manage
your own hardware configuration.

Users, passwords, autologin, networking, Bluetooth, storage and persistence remain
the host's responsibility. Icewine includes network and Bluetooth controls, but
their underlying services must be enabled in your NixOS configuration. For example:

```nix
networking.networkmanager.enable = true;
hardware.bluetooth.enable = true;
```

### Replace the desktop with Icewine

In your `flake.nix`:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    icewine.url = "github:readonlyengineer/Icewine/main";
    icewine.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { nixpkgs, icewine, ... }: {
    nixosConfigurations.icewine = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        ./configuration.nix
        icewine.nixosModules.default
        {
          services.icewine = {
            enable = true;
            user = "YOUR_USERNAME";
          };
        }
      ];
    };
  };
}
```

Use your existing host target and username. Keep your hardware, users, storage
and persistence configuration. Disable the previous desktop and display manager;
Icewine supplies Hyprland and SDDM by default. Rebuild your host and select
**Hyprland (UWSM)** at login.

### Handheld

Enable the handheld interface and its native Steam and InputPlumber dependencies:

```nix
services.icewine.handheld.enable = true;
```

Kernel and hardware drivers remain host choices. The controls currently target Steam Deck; controller input,
touch, suspend/resume and docking need testing on the device. HTPC support is
intended scope rather than separately validated hardware.

#### Controller inputs

Controller input passes through while Gamescope is focused. On the desktop or
overlay it is mapped to keyboard and mouse controls.

Icewine's Steam launcher starts Steam inside Gamescope, or focuses an existing
Steam session. Non-Steam games and emulators added to Steam can use the same
controller passthrough.

To reach the Steam desktop interface, open Icewine's launcher while Steam is
running, then select **Background Applications → Steam Actions → Exit Big Picture**.
Add games using Steam's **Add a Non-Steam Game** action.

### Wallpaper

```sh
icewine wallpaper "/path/to/image.png"
```

Icewine copies PNG, JPEG, GIF or BMP images to
`$XDG_DATA_HOME/icewine/wallpapers/selection.img` and refreshes the wallpaper.
Your original file can then be moved or deleted.

### Theme and transparency

```sh
icewine theme                    # List themes and the current selection
icewine theme tokyo-night        # Select Tokyo Night
icewine transparency off         # Options: off, low, med, high
```

Choose the theme and wallpaper before transparency: wallpaper brightness has a
large effect on how transparency looks. Reopen apps if their appearance has not
updated.

Selections survive login and theme changes. An explicit `services.icewine.theme`
setting overrides the CLI theme choice; leave it unset to choose themes yourself.

### Init and reset

```sh
icewine init
```

Init creates missing dot files, updates untouched shipped defaults and preserves
user-edited entries. Icewine runs it automatically during NixOS activation,
before login and before its shell starts; you normally do not need to run it yourself.

```sh
icewine reset hypr               # Restore Hyprland defaults only
icewine reset                    # Restore all managed defaults
```

Reset backs up and replaces editable defaults, including `hyprland.lua` and your
overrides. Backups are under `$XDG_STATE_HOME/icewine/defaults-reset-*` and `reset-*`.
A full reset also clears theme, transparency and autofullscreen choices; a scoped
reset retains them. Neither clears your selected wallpaper.

Run these commands as your normal user. Reset cannot bypass migration conflicts
or replace a Hyprland entry managed by Home Manager.

If `icewine init` reports a conflict, it has preserved a file it cannot safely
replace. Read the reported path and back up the file before changing it.

## Basic hotkeys

| Key | Action |
| --- | --- |
| ``Super+` `` (hold) | Display topbar |
| `Super+Return` | Terminal |
| `Super+Space` | Launcher |
| `Super+E` | File manager |
| `Super+L` | Lock |
| `Super+Q` | Close window |
| `Super+F` | Toggle fullscreen |
| `Super+V` | Toggle floating |
| `Super+Arrow` | Focus window |
| `Super+Shift+Arrow` | Swap windows/columns |
| `Super+Ctrl+Arrow` | Resize window/column |
| `Super+1…0` | Switch workspace |
| `Super+Shift+1…0` | Move window to workspace |

Monocle arrows cycle its stack; directional swapping and resizing have no effect.
`Super+J` stacks/unstacks scrolling windows; `Super+M` toggles scrolling column width.

## Managing dot files

### Structure and editable entries

Each application uses its native configuration entry. That entry loads Icewine's
shared defaults, then your overrides. The shared implementation is reached through
a managed symlink into the Nix store; generated theme files are kept separately.

```text
~/.config/hypr/
├── hyprland.lua                 ← Edit this: shared import, then your settings
└── icewine → /nix/store/…-icewine-implementation/hyprland/
    ├── icewine.lua              ← Loads shared behaviour and generated Theme.lua
    └── modules/                ← Shared bindings, window policy, docking, etc.

~/.config/icewine/current/        ← Generated appearance; do not edit
```

This schema was chosen to allow Icewine to update with the package, but still give the user freedom.

| Application | Editable entry under `~/.config` |
| --- | --- |
| Hyprland | `hypr/hyprland.lua` |
| Quickshell | `quickshell/shell.qml`; settings in `quickshell/config/Settings.qml` |
| Kitty | `kitty/kitty.conf` |
| Neovim | `nvim/init.lua` |
| Bash | `icewine/shell/bashrc`, `profile`, `bash_profile`; home dot files link here |
| UWSM | `uwsm/env` |
| Hypridle | `hypr/hypridle.conf` |
| GTK CSS | `gtk-3.0/gtk.css`, `gtk-4.0/gtk.css` |

Quickshell's entry selects `Icewine.Desktop {}` or `Icewine.Handheld {}`; keep
`Settings.qml` and its neighbouring `qmldir` together. Hypridle's shared listener
blocks append: to replace its timers, remove the shared source line and maintain
the complete config yourself.

Fastfetch, Starship, Yazi theme/keymap and GTK settings normally link to generated
files. To customise one, copy its contents, replace the link with a regular file
at the same path, then edit it. That file is preserved by init but no longer
follows generated theme changes. Keep your own copy before a reset.

### Hyprland example

Below is an example of what someone's Hyprland.lua might look like.
This user prefers dwindle over the shipped scrolling layout.

In `~/.config/hypr/hyprland.lua`:

```lua
require("icewine.icewine")

-- Explicit monitor settings, using details from hyprctl monitors
hl.monitor({ output = "eDP-1", mode = "2880x1800@120.00Hz", position = "0x0", scale = 1 })

-- Use dwindle as the default layout for workspaces.
hl.config({ general = { layout = "dwindle" } })
```

Settings below the shared import override its defaults. An explicit workspace
layout rule takes precedence over the default; for example:

```lua
hl.workspace_rule({ workspace = "2", layout = "master" })
```

#### Runtime changes

For a temporary change in the running session:

```sh
hyprctl eval 'hl.workspace_rule({ workspace = "2", layout = "dwindle" })'
```

Runtime changes clear on config reload or restart. Desktop controls support
scrolling, dwindle, master and monocle; Deck controls assume scrolling.

### Automatic fullscreen

```sh
icewine autofullscreen on        # Options: on, off; default: off
```

This enables scrolling's automatic fullscreen policy, fullscreens lone tiled
windows in dwindle/master, and defaults the focused monocle window to fullscreen.
Manual and application fullscreen choices take precedence.

## Applications

Icewine provides Firefox, Kitty, Yazi and desktop controls. Other applications
belong in your host configuration. Browser profiles and browser themes are yours;
Icewine supplies GTK styling and the system light/dark preference.

### Steam

Steam is proprietary, installed natively by default, and Icewine permits the
required unfree Steam packages. Set `services.icewine.steam = "native"` or
`"flatpak"` to choose its installation method. Set `"none"` to disable Steam
installation and integration; Icewine then grants no Steam-related unfree permission.

When switching away from Flatpak Steam, keep `services.flatpak.enable = true;`
until rebuilding has removed it. Game and client data are preserved.

### Optional Flatpak app store

Enable Flatpak in your host configuration:

```nix
services.flatpak.enable = true;
```

After rebuilding, add Flathub and optionally install Bazaar as your normal user:

```sh
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub io.github.kolunmi.Bazaar
```

### Alternative applications and opt-outs

Set replacement commands and disable the corresponding preset together:

```nix
services.icewine = {
  browser.enable = false;
  applications.browser = [ "librewolf" ];
  applications.editor = [ "nvim" ];
};
```

Install the replacement applications in your host configuration. The Neovim
starter is installed by `icewine init nvim`; plugins and language servers must
also be supplied by the host.

These options belong under `services.icewine`:

| Option | Stops Icewine providing |
| --- | --- |
| `browser.enable = false;` | Firefox and its web/PDF defaults |
| `terminal.preset = null;` | Kitty installation and configuration; set `applications.terminal` and `applications.terminalExecute` |
| `fileManager.preset = null;` | Yazi and its GVfs default; set `applications.fileManager` if needed |
| `login.enable = false;` | SDDM; provide your own login method |
| `gtk.enable = false;` | GTK styling |
| `idle.enable = false;` | Automatic idle locking and sleep; manual locking remains |
| `battery.enable = false;` | Battery warnings and automatic sleep; UPower remains |
| `shell.enable = false;` | Bash configuration and its integrations |
| `shell.fastfetch.enable = false;` | Fastfetch |
| `shell.blesh.enable = false;` | ble.sh |
| `shell.starship.enable = false;` | Starship |
| `shell.starship.git.enable = false;` | Git information in the prompt |

Battery thresholds live in `quickshell/config/Settings.qml`: warnings at 20%,
10% and 5%, then a suspend request at 3%. The shell must be running; test sleep
behaviour on your hardware without deliberately draining the battery.

See [modules/default.nix](modules/default.nix) for application commands and
`defaultFiles.config`/`defaultFiles.data` options for host-supplied editable defaults.
