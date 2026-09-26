# Icewine

Icewine is a Hyprland and Quickshell desktop environment for NixOS.

## Setup

Add Icewine to your system flake:

```nix
inputs.icewine.url = "github:readonlyengineer/Icewine/main";
inputs.icewine.inputs.nixpkgs.follows = "nixpkgs";
inputs.icewine.inputs.home-manager.follows = "home-manager";
```

Import the module and configure an existing user:

```nix
imports = [ inputs.icewine.nixosModules.default ];

services.icewine = {
  enable = true;
  user = "alice";
};
```

Set the user's Home Manager `home.stateVersion`, then select the
`hyprland-uwsm` session at login. Icewine does not create users or configure
your login manager, autologin, storage, networking, kernel, or binary caches.

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
