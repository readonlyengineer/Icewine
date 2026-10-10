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
          # Host login policy survives deselecting Icewine's login styling.
          services.displayManager.sddm.enable = true;
          services.icewine = {
            enable = true;
            user = "YOUR_USERNAME";
            desktop.enable = true;
            terminal.enable = true;
            filemanager.enable = true;
            steam = "flatpak";
            login.enable = true;
            shellExtras.enable = true;
          };
        }
      ];
    };
  };
}
```

Use your existing host target and username. Keep your hardware, users, storage
and persistence configuration. Disable the previous desktop and display manager;
The template opts into the complete experience; optional integrations default off.
Rebuild your host, run `icewine manage` as your desktop user from a TTY and Apply
to deploy editable defaults, then select **Hyprland (UWSM)** at login.

### Handheld

Enable the handheld interface and its native Steam and InputPlumber dependencies:

```nix
services.icewine = {
  handheld.enable = true;
  desktop.enable = true;
  steam = "native";
};
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

### Manage integrations and dotfiles

```sh
icewine manage
```

Use Tab or arrows to navigate, Space to select, and Enter on Apply or Cancel.
NixOS utility selections reflect the module options and are read-only. Apply
creates missing dotfiles; **Overwrite existing dotfiles** replaces selected defaults
without backups. It starts unchecked each time. Existing files are otherwise
preserved, including on rebuild, login and reboot. Host persistence remains host policy.

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
| UWSM | `uwsm/env` |
| Hypridle | `hypr/hypridle.conf` |
| GTK CSS | `gtk-3.0/gtk.css`, `gtk-4.0/gtk.css` |

Quickshell's entry selects `Icewine.Desktop {}` or `Icewine.Handheld {}`; keep
`Settings.qml` and its neighbouring `qmldir` together. Hypridle's shared listener
blocks append: to replace its timers, remove the shared source line and maintain
the complete config yourself.

Fastfetch, Starship, Yazi theme/keymap and GTK settings normally link to generated
files. To customise one, copy its contents, replace the link with a regular file
at the same path, then edit it. That file is preserved by Apply unless overwrite is checked, and no longer
follows generated theme changes. Initialise Starship and Fastfetch in your own shell configuration.

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

Edit the template's Applications block to change hotkeys; external applications
keep their installer/Nix defaults. Icewine uses the host browser and sets no web/PDF
associations. An empty browser command disables its hotkey.

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

The manager/module offers Kitty, Yazi, Steam with optional Gamescope/Handheld,
SDDM styling and Starship/Fastfetch alongside the optional desktop session.
Browser profiles and themes belong to you; Icewine uses the host browser.

### Steam and Flatpak

Steam defaults to none. Choose native or Flatpak with left/right in the manager,
or set `steam = "native";` / `steam = "flatpak";` under `services.icewine`.
Gamescope defaults on for a selected client and can be disabled independently
with `gamescope.enable = false;`; Steam then launches normally. Handheld defaults
off and requires native Steam, the desktop session and Gamescope. Flatpak Steam
supplies its required runtime and Flathub support. Bazaar is not installed.

### Alternative applications and opt-outs

Optional utility switches install and configure Icewine's defaults. They do not
select replacement applications or change your MIME defaults.

Hyprland opens terminals through `xdg-terminal-exec`, directories through
`xdg-open`, and the browser through its XDG default. Set a preferred terminal in
`~/.config/xdg-terminals.list`, or customise shortcuts in `hypr/hyprland.lua`.


Install replacement applications and their configuration in your host. Neovim
plugins and language servers are host-owned; Icewine generates the optional
`icewine/current/nvim-theme.lua` appearance adapter and signals themed instances.

These options belong under `services.icewine`:

| Option | Stops Icewine providing |
| --- | --- |
| `desktop.enable = false;` | Hyprland session integration; explicit Apply removes its implementation link |
| `terminal.enable = false;` | Kitty defaults |
| `filemanager.enable = false;` | Yazi and its GVfs default |
| `steam = "none";` | Steam integration and dependent Gamescope/Handheld |
| `gamescope.enable = false;` | Gamescope launch integration; ordinary Steam remains available |
| `login.enable = false;` | Icewine SDDM styling; host SDDM enablement is retained |
| `shellExtras.enable = false;` | Starship/Fastfetch defaults |
| `shellExtras.git.enable = false;` | Git information in the prompt |
| `gtk.enable = false;` | GTK styling |
| `idle.enable = false;` | Automatic idle locking and sleep; manual locking remains |
| `battery.enable = false;` | Battery warnings and automatic sleep; UPower remains |

Battery thresholds live in `quickshell/config/Settings.qml`: warnings at 20%,
10% and 5%, then a suspend request at 3%. The shell must be running; test sleep
behaviour on your hardware without deliberately draining the battery.

See [modules/default.nix](modules/default.nix) for application commands and
`defaultFiles.config`/`defaultFiles.data` options for host-supplied editable defaults.
