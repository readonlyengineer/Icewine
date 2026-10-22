# Icewine

An experimental Hyprland desktop built with Quickshell, developed NixOS-first
for desktops, laptops, handhelds and HTPCs. Handheld controls currently target
Steam Deck; HTPC support is not separately validated.

## Install

### NixOS

Requires flakes and `nix-command`. Add Icewine to your host flake:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    icewine.url = "github:readonlyengineer/Icewine/main";
    icewine.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { nixpkgs, icewine, ... }: {
    nixosConfigurations.YOUR_HOST = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        ./configuration.nix
        icewine.nixosModules.default
        {
          services.icewine = {
            enable = true;
            user = "YOUR_USERNAME";
            desktop.enable = true;
            terminal.enable = true;
            filemanager.enable = true;
            login.greeter.enable = true;
            shellExtras.enable = true;
          };
        }
      ];
    };
  };
}
```

Use your existing host target, architecture and username. Disable any previous
conflicting desktop/display manager, rebuild, then run `icewine` as your user
from a TTY and **Apply**. Select **Hyprland (UWSM)** at login.

Users, passwords, autologin, networking, Bluetooth, hardware, storage and
persistence remain host configuration. Enable NetworkManager and Bluetooth on
the host if you want their Icewine controls.

For Steam Deck, also set:

```nix
services.icewine = {
  handheld.enable = true;
  desktop.enable = true;
  steam = "native";
};
```

Controller input, touch, suspend/resume and docking need real-device validation.

### Arch Linux / CachyOS

Install headless, log in, then run from fish or sh:

```sh
curl -fsSL https://raw.githubusercontent.com/readonlyengineer/Icewine/HEAD/install.sh | sh
```

Complete the TUI, Apply, then choose reboot.

## Configure

Run `icewine` for utilities, appearance, widgets and hotkeys. Tab changes pane;
arrows navigate; Enter/Space acts.

On NixOS, select utilities through `services.icewine`; those choices are read-only
in the manager. **Apply** creates missing defaults and preserves existing files.
**Overwrite existing dotfiles** replaces selected defaults without backups and
starts unchecked. Host-managed files remain protected.

```sh
icewine theme                       # List themes
icewine theme tokyo-night            # Select a theme
icewine wallpaper "/path/to/image.png"
icewine transparency off            # off, low, med, high
icewine layout scrolling             # scrolling, dwindle, master, monocle
```

An explicit NixOS theme setting overrides the user choice. Edit application
entry files after their shared import to override defaults; generated files in
`~/.config/icewine/current/` are replaced by theme updates.

## Essential keys

| Key | Action |
| --- | --- |
| ``Super+` `` (hold) | Show the topbar |
| `Super+Return` | Terminal |
| `Super+Space` | Launcher |
| `Super+E` | File manager |
| `Super+L` | Lock |
| `Super+Q` | Close window |
| `Super+Arrow` | Focus window |
| `Super+1…0` | Switch workspace |
| `Super+Shift+1…0` | Move window to workspace |

Open **Hotkeys** in `icewine` to browse and edit bindings.

## Documentation

- [User guide](docs/user-guide.md): controls, applications, dotfiles, themes and module options.
- [NixOS options](modules/default.nix).
