# Icewine

Icewine is a unified Hyprland desktop for Desktop/Laptop/Handheld/HTPC; developed NixOS-first.

It is deeply experimental at the moment; it will move fast and break things. 
Use at your own risk. 

## Setup

NixOS may be installed with the standard calamares installer before the following edits are made: 

Add Icewine to your system flake:

```nix
inputs.icewine.url = "github:readonlyengineer/Icewine/main";
```

Disable your existing desktop environment and display manager in your NixOS
configuration, then import Icewine and select an existing user. Importing Icewine
does not disable the old desktop for you.

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

### Host responsibilities

Users, passwords, autologin, networking, Bluetooth, hardware drivers, storage and
persistence remain the host's responsibility. Icewine includes network and
Bluetooth controls, but their underlying services must be enabled in your NixOS
configuration. For example:

```nix
networking.networkmanager.enable = true;
hardware.bluetooth.enable = true;
```

Monitor layout and hardware-specific settings belong on the host too. Extra
Hyprland Lua modules can be supplied through `services.icewine.hyprland.extraModules`.

For example:
```nix
services.icewine.hyprland.extraModules."host.lua" = ./hypr/host.lua;
```

Refer to Hyprland wiki for options and syntax. 

### Handheld

Enable the handheld interface and its native Steam and InputPlumber dependencies:

```nix
services.icewine.handheld.enable = true;
```

This enables the Quickshell handheld elements, native Steam and the InputPlumber
service. Selection of kernel and hardware drivers remains with the host.

#### Controller inputs

Controller input passes through while Gamescope is focused. On the desktop or overlay
it is mapped to keyboard and mouse controls.

Icewine's Steam launcher starts Steam inside Gamescope, or focuses an existing
Steam session. 

Non-Steam games and emulators added to Steam can use the same controller
passthrough when that session runs inside Gamescope. The easiest way to do this is 
to add them as "non-steam games" within steam. To do this, open the launcher while 
Steam/Gamecope is running, select Background Applications, Steam Actions, Exit Big Picture. 

### Steam

For desktop systems, we recommend Steam’s Flatpak package for its application sandbox:

```nix 
services.flatpak.packages = [
  "com.valvesoftware.Steam"
  "com.valvesoftware.Steam.CompatibilityTool.Proton-GE"
];

services.icewine.steam.enable = true;
services.icewine.applications.steam = [
  "flatpak" "run" "com.valvesoftware.Steam"
];
```

For handheld systems, Icewine installs native Steam as part of its Gamescope and controller integration. Steam is proprietary, so allow unfree packages on the host:

```nix
nixpkgs.config.allowUnfree = true;
services.icewine.handheld.enable = true;
```

### Software and packages

For users new to NixOS, it is recommended to use flatpak where possible. 
Flatpaks can be added declaratively in your nix configuration or downloaded direclty. 
The example below provides both an example of how to declaratively add a flatpak, and guides the user to Bazaar, a traditional appstore for flatpaks. 

```nix
services.flatpak.packages = [
  "io.github.kolunmi.Bazaar"
];
```
Icewine does not install Bazaar. 

System packages must be installed via the system configuration, refer to the nix wiki page for the package. 

## Basic hotkeys

| Key | Action |
| --- | --- |
| ``Super+` `` (hold) | display topbar |
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

## Further configuration

### Browser

Icewine installs native Firefox and uses it for the browser launcher, web links,
HTML and PDFs.

### For users who have already configured thier flake

Icewine configures and uses Home Manager for dotfiles. 
To make Icewine use the same Home Manager input as your system flake:

```nix
inputs.icewine.inputs.home-manager.follows = "home-manager";
```

### Supported alternative software

#### Neovim

Nano is installed by default. To use Neovim, install and configure it yourself,
then point Icewine at it:

```nix
services.icewine.applications.editor = [ "nvim" ];
```
This selects the editor command; it does not install Neovim or supply a
configuration. An optional preconfigured Neovim setup may come later.

#### Opt-outs

These settings belong under `services.icewine`. They stop Icewine managing the
feature; they do not disable another module's configuration or delete user data.

| Setting | What Icewine stops providing |
| --- | --- |
| `browser.enable = false;` | Firefox installation and web/PDF associations; also set `applications.browser` to your replacement command. |
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
