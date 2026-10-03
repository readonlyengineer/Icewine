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

### Wallpaper

Choose a local wallpaper with `icewine wallpaper "/path/to/image.png"`. The
command validates and copies PNG, JPEG, GIF, or BMP images into
`$XDG_DATA_HOME/icewine/wallpapers/selection.img`, then refreshes the running
desktop and handheld shell. The original file can be moved or deleted. With no
selection, Icewine uses the shipped
`$XDG_DATA_HOME/wallpapers/default.jpg`. The selected copy follows the NixOS
persist allowlist. Legacy user-owned
`wallpapers/current.jpg` images are copied during Home Manager activation when
there is no saved selection; the old Nix-store-backed default is not migrated.

### Theme and user configuration

`icewine init` creates missing Icewine config under `$XDG_CONFIG_HOME` and
replaces recognized old Home Manager links. It preserves user-edited files.
Recognized links are backed up under `$XDG_STATE_HOME/icewine/migration-*`;
unrecognized symlinks remain untouched and are reported as conflicts.
Static Hyprland, Quickshell, UWSM, btop, locale and wallpaper defaults are
installed as writable files. Their migrated links and replaced files are saved
under `defaults-migration-*` and `defaults-reset-*` in the same state directory.
The defaults come from Icewine, except for host-selected files supplied by
NixOS; later activations and theme changes preserve local edits. Run
`icewine reset APP` to adopt updated shipped defaults for `hypr`, `quickshell`,
`uwsm`, `btop`, `user-dirs`, or `wallpapers`, or use `icewine reset` for all
defaults. Reset saves replaced content first. The generated Quickshell palette
and Hyprland `Theme.lua` remain Icewine-managed links so theme selection works.
`icewine init APP` installs missing files for one of `quickshell`, `gtk`,
`yazi`, `fastfetch`, `starship`, `hypr`, `uwsm`, `btop`, `user-dirs`, or
`wallpapers`. `icewine reset APP` backs up and refreshes
only that app's files without clearing the selected theme; plain `reset`
restores every Icewine-owned file and clears the CLI selection.
`icewine theme` lists the installed themes and effective selection;
`icewine theme tokyo-night` and `icewine theme dracula` save a choice under
`$XDG_STATE_HOME/icewine/theme`. On NixOS, `services.icewine.theme` accepts
`null` (the default), `"tokyo-night"`, `"dracula"`, `"nord"`, `"gruvbox-light"`,
`"gruvbox-dark"`, `"catppuccin-latte"`, `"catppuccin-frappe"`,
`"catppuccin-macchiato"`, or `"catppuccin-mocha"`. An explicit Nix value
overrides the CLI choice; otherwise the CLI choice wins, then Tokyo Night.
Catppuccin palettes use the [official colours](https://github.com/catppuccin/palette)
(MIT; licence in `theme/assets/themes/CATPPUCCIN-LICENSE`). Latte is light;
Frappé, Macchiato and Mocha are dark. Neovim requires `catppuccin-nvim`,
provided by the NixOS editor configuration.

`icewine transparency off|low|med|high` saves an independent transparency
preference. With no argument it reports the saved level. Kitty background /
inactive-window opacity is 1.00/1.00, 0.92/0.95, 0.84/0.85 or 0.76/0.75;
`med` is the default. Theme changes and login retain this choice. Hyprland
reloads where available; reopen Kitty to use its new background opacity.
Blur remains unchanged. A full `icewine reset` restores `med`; targeted resets
keep the preference.

`icewine autofullscreen on|off` controls automatic fullscreen on ordinary
windows and the width-toggle shortcut. The default is `off`; no argument shows
the saved setting. It is stored at `$XDG_STATE_HOME/icewine/autofullscreen` and
survives theme changes and login. The command reloads Hyprland when running.
Existing windows keep their state; manual/application fullscreen and Steam's
launch handoff are preserved. Full reset restores `off`; targeted resets keep it.

`icewine reset` backs up the Icewine-owned config paths under
`$XDG_STATE_HOME/icewine/reset-*`, restores their shipped defaults and clears
the CLI choice. It leaves the separately selected wallpaper alone. Theme
changes update the generated palette and report live reload failures and
which applications need a restart. GTK applications, browsers, Kitty, Yazi,
Fastfetch, Neovim and new shells use the new theme when restarted; an active Hyprland
and Quickshell session is refreshed where available. Browser chrome uses
shared GTK and portal appearance; no browser profile is changed. Select
"System theme — auto" in Firefox/LibreWolf and restart after changing palettes.
Icewine publishes a named GTK3 theme under `$XDG_DATA_HOME/themes` and updates
`org.gnome.desktop.interface` GTK theme and light/dark settings using `gsettings`.
The Settings portal must use a backend that exposes these settings (the NixOS
module selects GTK). When `flatpak` is available, Icewine also publishes the same
GTK3 CSS as a local Flatpak theme extension at
`$XDG_DATA_HOME/flatpak/extension/org.gtk.Gtk3theme.Icewine-THEME/ARCH/3.22/gtk.css`.
This uses Flatpak's documented externally managed ("unmaintained") extension
mechanism: no remote, per-app copies or host-theme filesystem grants are needed.
Compatible GTK3 runtimes discover it when apps launch; restart browsers after a
theme change. Native architecture is supported; GTK4 and Qt are outside this
extension's scope. Theme changes, login, `icewine init gtk`, and full/GTK resets
refresh the extension. Edited extension files and symlinked paths are preserved
and reported, including on reset; ownership hashes are saved under
`$XDG_STATE_HOME/icewine/flatpak-themes/`. Extension failures are reported without
blocking desktop startup. If Flatpak is installed later, run `icewine init gtk`.
Browser colour mapping remains browser-controlled; web content and privacy
preferences are unchanged.
Explicit Home Manager Fastfetch, Starship and Yazi settings retain their own
config files; Icewine skips those paths when applying or resetting a theme.
Icewine ships JSON palette data and app-native templates in `theme/assets`.
The CLI renders them into `$XDG_CONFIG_HOME/icewine/rendered/`; Nix packages
those source files and supplies optional policy/host metadata. On non-Nix
Linux, Fastfetch uses a generic kernel report and omits the Nixpkgs age row.

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
