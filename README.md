# Icewine

Icewine is a unified Hyprland desktop for Desktop/Laptop/Handheld/HTPC; developed NixOS-first.

It is deeply experimental at the moment; it will move fast and break things. 
Use at your own risk. 

## Install on NixOS

Start from an installed NixOS graphical system and open its terminal. The guide
below targets Intel/AMD PCs (`x86_64-linux`) and keeps the users, disks and
hardware configuration created by the installer. Icewine follows
`nixos-unstable`; this moves the whole system onto that rolling branch.

If you already use a system flake, skip to [Existing flakes](#existing-flakes).

### 1. Back up your configuration and enable flakes

Check your username and save the installer configuration:

```sh
id -un
sudo cp -a /etc/nixos /etc/nixos.before-icewine
sudo nano /etc/nixos/configuration.nix
```

Add this inside the existing configuration's final `{ ... }` block:

```nix
nix.settings.experimental-features = [ "nix-command" "flakes" ];
```

Apply that setting before creating a flake:

```sh
sudo nixos-rebuild switch
```

Keep `hardware-configuration.nix`, your user settings and `system.stateVersion`
unchanged. Flakes are explained in the [NixOS guide](https://wiki.nixos.org/wiki/Flakes).

### 2. Replace the installer desktop with Icewine

Edit `/etc/nixos/configuration.nix` again. Remove the lines enabling the old
desktop and display manager, such as GNOME/GDM or Plasma/SDDM, and any explicit
old default session. Look for `services.desktopManager.gnome.enable`,
`services.displayManager.gdm.enable`, `services.desktopManager.plasma6.enable`
and `services.displayManager.sddm.enable`; older configurations may put these
under `services.xserver`. Remove the matching enable lines already in your file.
Leave `services.xserver.enable` and your networking and hardware settings in
place. Icewine provides SDDM and Hyprland itself.

Create `/etc/nixos/flake.nix` with `sudo nano /etc/nixos/flake.nix` and paste:

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

Replace `YOUR_USERNAME` with the result of `id -un`. The `icewine` name is the
configuration selected by the commands below; it does not rename your computer.
Icewine includes Home Manager integration, so no separate installation is needed.

### 3. Build, reboot and log in

Build the configuration for your next boot, leaving the current desktop running:

```sh
sudo nixos-rebuild boot --flake path:/etc/nixos#icewine
```

The first build may take a while. If it fails, fix the reported error before
rebooting. Once it succeeds:

```sh
sudo reboot
```

At SDDM, select **Hyprland (UWSM)** if it is not already selected, then log in
with your existing username and password. Icewine installs its initial user
configuration automatically; do not run `icewine init` with sudo.

- `Super+Space` opens a terminal; `Super+Return` opens the launcher.
- `icewine theme` lists themes; `icewine theme catppuccin-mocha` selects one.
- `icewine wallpaper "/path/to/image.png"` selects a wallpaper.

To recover from a bad boot, choose an earlier NixOS generation in the boot menu.
The original configuration is also saved in `/etc/nixos.before-icewine`.

For later configuration edits, use:

```sh
sudo nixos-rebuild switch --flake path:/etc/nixos#icewine
```

To update the rolling inputs first:

```sh
sudo nix flake update --flake path:/etc/nixos
sudo nixos-rebuild boot --flake path:/etc/nixos#icewine
```

Reboot after that update succeeds. Keep `flake.lock` with your configuration;
it records the revisions used by a rebuild.

### Existing flakes

Add the input below, import `icewine.nixosModules.default` in your existing
`nixosSystem.modules`, and set `services.icewine.enable = true` and
`services.icewine.user` to your existing username. Disable your old desktop and
display manager as above, then rebuild your usual flake target.

```nix
inputs.icewine.url = "github:readonlyengineer/Icewine/main";
inputs.icewine.inputs.nixpkgs.follows = "nixpkgs";
```

Use a current `nixos-unstable` Nixpkgs input for Icewine's desktop dependencies.
If your flake already imports Home Manager, share its input too:

```nix
inputs.icewine.inputs.home-manager.follows = "home-manager";
```

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
defaults. Reset saves replaced content first. Quickshell's writable
`theme/Palette.qml` reads generated palette data; Hyprland `Theme.lua` remains
an Icewine-managed link. An existing user-edited palette is preserved by `init`
and may not support live updates. `icewine reset quickshell` backs it up and
installs the live palette, but also replaces other edited Quickshell defaults;
review the saved `defaults-reset-*` files before restoring local changes.
`icewine init APP` installs missing files for one of `quickshell`, `gtk`,
`yazi`, `fastfetch`, `starship`, `hypr`, `uwsm`, `btop`, `user-dirs`,
`wallpapers`, or `nvim`. `icewine reset APP` backs up and refreshes
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
`icewine theme status` reports shell application or pending consumers while
Quickshell is running; without the shell it reports the saved selection and
unknown live status. Set `ICEWINE_THEME_TRANSITION=off` in the `icewine.service`
environment and restart that service once to disable subsequent colour
transitions.

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
changes update the running Quickshell palette without restarting the shell.
Scoped same-user Kitty and Neovim instances receive native `SIGUSR1` reload
requests; signal delivery cannot confirm that colours were applied. Kitty
rereads its full configuration, including `host.conf` and command-line
overrides, and may reset a temporary font-size change or preserve colours set
by an application. Neovim instances with an older or edited `init.lua` may not
have the Signal hook and remain pending. Yazi receives a reload broadcast for
all current user clients, including other sessions; it is not acknowledged per
instance. GTK's theme and light/dark preference are published through
GSettings; custom CSS in already open GTK or Flatpak apps may require reopening
those apps. Starship uses the new theme at the next prompt and Fastfetch at its
next run. The CLI reports failed or pending consumers separately from the saved
selection. Browser chrome uses shared GTK and portal appearance where supported;
browser-specific reload behaviour remains outside this command. No browser
profile is changed. Select "System theme — auto" in Firefox/LibreWolf for
system appearance.
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

### Applications and Steam

Icewine installs Firefox, Kitty, Yazi and desktop controls. Add other native
packages inside `/etc/nixos/configuration.nix`, then rebuild:

```nix
environment.systemPackages = with pkgs; [ vlc ];
```

For a graphical app store, enable Flatpak in that same configuration:

```nix
services.flatpak.enable = true;
```

Rebuild and log out/in, then add Flathub and install Bazaar as your normal user:

```sh
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub io.github.kolunmi.Bazaar
```

Launch Bazaar from Icewine's launcher to install more applications. Icewine does
not install Bazaar automatically. See the [NixOS Flatpak guide](https://wiki.nixos.org/wiki/Flatpak).

For desktop Steam through Flatpak, install it from Bazaar or run:

```sh
flatpak install --user flathub com.valvesoftware.Steam
```

Then add these settings and rebuild:

```nix
services.icewine.steam.enable = true;
services.icewine.applications.steam = [
  "flatpak" "run" "com.valvesoftware.Steam"
];
```

Handheld mode installs native Steam for its Gamescope/controller integration.
Steam is proprietary, so allow unfree packages on the host:

```nix
nixpkgs.config.allowUnfree = true;
services.icewine.handheld.enable = true;
```

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

### Supported alternative software

#### Neovim

Nano remains the default editor command. Nixos desktop installs Neovim, plugins,
parsers and language servers; select it for Icewine launchers with:

```nix
services.icewine.applications.editor = [ "nvim" ];
```
`icewine init nvim` installs the editable `$XDG_CONFIG_HOME/nvim/init.lua`;
`icewine reset nvim` backs it up and copies the current shipped default. Theme
changes update a separate generated fragment without replacing this file.
Outside NixOS, install Neovim 0.11 or newer, nvim-treesitter with the shipped
grammars (including `diff`), render-markdown.nvim, yazi.nvim with plenary.nvim,
nvim-lspconfig, blink.cmp, the five colour schemes, Yazi and the six configured
language servers. Provide the plugins through Neovim's native package path;
the Lua config does not download them.

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

With the Kitty preset active, Icewine installs an editable
`$XDG_CONFIG_HOME/kitty/kitty.conf` entry. Home Manager redirects its generated
Kitty config, including host settings, fonts, bindings and extra config, to
`kitty/host.conf`; the entry includes it after Icewine's base and theme files so
host settings retain precedence without sharing the editable entry path. Shell
integration remains managed through Home Manager's separate shell hooks.
Setting `terminal.preset = null` leaves Home Manager's normal Kitty
configuration path to the host. On the Nixos desktop, Home Manager's `hm-bak`
policy backs up the editable entry when handing that path back to host settings;
activation stops safely if that backup already exists. Other Home Manager
consumers need a backup extension configured or must move the entry first.

The handheld interface is opt-in (`handheld.enable = true;`), not enabled by
default. There is no blanket exclusion list for core desktop dependencies.
