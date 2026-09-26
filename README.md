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
