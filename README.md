# Icewine

Icewine is a Hyprland and Quickshell desktop environment for NixOS.

## Setup

Add Icewine to your system flake:

```nix
inputs.icewine.url = "github:readonlyengineer/Icewine/main";
```

Import the module and configure an existing user:

```nix
imports = [ inputs.icewine.nixosModules.default ];

services.icewine = {
  enable = true;
  user = "alice";
};
```

Icewine configures its own Home Manager integration and a standard SDDM login
screen, with `hyprland-uwsm` as the overridable default session. SDDM uses its
default X11 greeter; the desktop session runs on Wayland. Login and locking
share the same QtQuick layout and palette, with separate authentication.

Set `services.icewine.login.enable = false;` to use another display manager or
a console login. Icewine does not create users or configure autologin, storage,
networking, kernel, or binary caches. Hosts choose those policies through the
standard NixOS options, including `services.displayManager.autoLogin` and
`services.displayManager.defaultSession`.

To use the latest Icewine `main` before rebuilding, update only that flake
input:

```sh
nix flake update --flake /path/to/nixos/desktop icewine
```

### Host overrides

Import Icewine directly from each host and keep that host's `services.icewine`
settings together. `hyprland.extraModules` accepts explicitly named Lua files;
Icewine loads an optional `host.lua` after its desktop defaults. Use it for panel
modes, calibration, rotation and other hardware-specific settings. Brightness
keys, touchpad defaults and three-finger navigation are supplied by Icewine.

### Browser

Icewine installs Firefox from Flathub and uses it for the browser launcher,
web links, HTML and PDFs. Replace it with another Flathub browser using one
setting:

```nix
services.icewine.browser.flatpak = "io.gitlab.librewolf-community";
```

Set `browser.flatpak = null;` and `applications.browser = [ "your-browser" ];`
to manage installation and associations yourself. Flatpak updates, permissions,
profile persistence and migrations remain host policy. Installation uses
[nix-flatpak](https://github.com/gmodena/nix-flatpak); it requires network access
after activation and is not part of the Nix build.

If the host already has a nix-flatpak input, share it:

```nix
inputs.icewine.inputs.nix-flatpak.follows = "nix-flatpak";
```

### Handheld

Enable the handheld interface on a host that already provides its hardware
support, controller service and native Steam installation:

```nix
services.icewine.handheld.enable = true;
```

## Basic hotkeys

| Key | Action |
| --- | --- |
| <kbd>Super</kbd>+<kbd>`</kbd> (hold) | Display topbar |
| `Super+Space` | Terminal |
| `Super+Return` | Launcher |
| `Super+E` | File manager |
| `Super+L` | Lock |
| `Super+Q` | Close window |
| `Super+F` | Toggle fullscreen |
| `Super+Arrow` | Focus window |
| `Super+Shift+Arrow` | Move window |
| `Super+Ctrl+Arrow` | Resize window |
| `Super+1…0` | Switch workspace |
| `Super+Shift+1…0` | Move window to workspace |

## For users who have already configured Home Manager

Make Icewine use the same Home Manager input as your system flake:

```nix
inputs.icewine.inputs.home-manager.follows = "home-manager";
```

### Supported alternative software

#### Neovim

The accompanying NixOS desktop configuration includes a Nixvim configuration.
Enable its editor command with:

```nix
services.icewine.applications.editor = [ "nvim" ];
```

## Opt-outs

These settings belong under `services.icewine`. They stop Icewine managing the
feature; they do not disable another module's configuration or delete user data.

| Setting | What Icewine stops providing |
| --- | --- |
| `browser.flatpak = null;` | Browser installation and web/PDF associations; also set `applications.browser` to your replacement command. |
| `terminal.preset = null;` | Kitty installation and configuration; also set `applications.terminal` to your replacement command. |
| `fileManager.preset = null;` | Yazi and its GVfs default; `applications.fileManager` falls back to `xdg-open .`, or can name your replacement. |
| `login.enable = false;` | SDDM login screen; provide another display manager or use console login. |
| `gtk.enable = false;` | Icewine GTK styling. |
| `idle.enable = false;` | Hypridle's automatic locking, display blanking and suspend hooks; manual locking remains available. |
| `battery.enable = false;` | Battery warnings and critical-battery suspend. |
| `shell.enable = false;` | Icewine's Bash configuration and all shell integrations below. |
| `shell.fastfetch.enable = false;` | Fastfetch installation and startup report. |
| `shell.blesh.enable = false;` | ble.sh installation and integration. |
| `shell.starship.enable = false;` | Starship installation and prompt. |
| `shell.starship.git.enable = false;` | Git information in the Starship prompt. |

The handheld interface is opt-in (`handheld.enable = true;`), not enabled by
default. There is no blanket exclusion list for core desktop dependencies.
