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
Icewine uses NixOS user packages and services; Home Manager is optional for
unrelated host configuration.

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
### Host responsibilities

Users, passwords, autologin, networking, Bluetooth, hardware drivers, storage and
persistence remain the host's responsibility. Icewine includes network and
Bluetooth controls, but their underlying services must be enabled in your NixOS
configuration. For example:

```nix
networking.networkmanager.enable = true;
hardware.bluetooth.enable = true;
```

Customise monitors, bindings and other Hyprland settings in
`~/.config/hypr/hyprland.lua`. The default uses each display's preferred mode,
automatic placement and scaling. Add settings directly or load your own Lua
modules with `require()`. Rebuilds preserve edits; `icewine reset hypr` backs
up the current files and restores shipped defaults.

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
`wallpapers/current.jpg` images are copied during NixOS activation when
there is no saved selection; the old Nix-store-backed default is not migrated.

### Theme and user configuration

`icewine init` creates missing Icewine config under `$XDG_CONFIG_HOME` and
replaces recognized old Home Manager links. It preserves user-edited files.
Recognized links are backed up under `$XDG_STATE_HOME/icewine/migration-*`;
unrecognized symlinks remain untouched and are reported as conflicts.
Quickshell QML/JS and Hyprland behaviour run from a read-only implementation
package (the Nix store on NixOS).
Writable defaults contain the small entry points, settings, bindings and hooks,
plus host-owned btop, locale and wallpaper configuration. Icewine records the bytes or symlink it installed
in `$XDG_STATE_HOME/icewine/default-files.json`. Init refreshes a changed shipped
default only while the current file still matches that record; your edits,
untracked files, unknown symlinks and conflicting directories remain intact
with conflict diagnostics. Keep this state directory with your configuration
when using persistence. Migrated links, automatic updates/removals and explicit
resets are backed up under `defaults-migration-*`, `defaults-update-*` and
`defaults-reset-*` in the same state directory.
The full init also retires recognized Icewine Home Manager user-unit and target
links so native NixOS units load on the next login; an active user manager is
reloaded. If reload reports `Pending`, run `systemctl --user daemon-reload` in
the user session. Edited or unknown units are preserved and reported as conflicts.
The defaults come from Icewine, except for host-selected files supplied by
NixOS; later activations update unchanged defaults and preserve local edits. NixOS prepares
the files before the display manager starts and initializes missing files on
user activation. Initialization errors are reported but do not prevent SDDM
starting; the desktop shell still requires successful initialization.
Run
`icewine reset APP` to adopt updated shipped defaults for `hypr`, `quickshell`,
`uwsm`, `btop`, `user-dirs`, or `wallpapers`, or use `icewine reset` for all
defaults. Reset saves replaced content first. Generated appearance stays under
`icewine/current`; Hyprland `modules/Theme.lua` is a managed link and the packaged
Quickshell palette reads `palette.json` from that generated directory.

Supported writable entry points are:

- `quickshell/config/Settings.qml` for shell settings; keep its `qmldir` alongside it.
- `quickshell/shell.qml` imports `"icewine" as Icewine` and runs `Icewine.Desktop {}`
  or `Icewine.Handheld {}`. Additional user components may live in separate local
  directories and be instantiated from this entry point.
- `hypr/hyprland.lua` loads the packaged Icewine entry, then your host/Personal
  modules or local overrides. Keep the packaged loader before those hooks.
- `hypr/modules/Binds.lua` and `Autostart.lua` are managed aliases to shared defaults; edited or host-selected hooks remain active compatibility overrides.
  Load order is Baseline, LookAndFeel, generated Theme, WindowPolicy, Binds,
  Autostart, fallback monitor, then appended handheld and host overrides.

Shared defaults live under one immutable `ROOT`, with application subtrees such
as `ROOT/hyprland`, `ROOT/quickshell`, `ROOT/kitty`, `ROOT/nvim`, `ROOT/bash`,
`ROOT/uwsm`, `ROOT/hypridle` and `ROOT/gtk`. Each application's writable native
entry loads its neighbouring managed package link, then generated appearance,
then your settings in that same entry. No runtime `ICEWINE_IMPLEMENTATION`
environment variable is needed. On NixOS ROOT is a Nix store package; another
packager could use `/usr/share/icewine`. This is a path contract, not another
supported distribution or installer.

For example:

```text
ROOT/kitty/defaults.conf
~/.config/kitty/icewine -> ROOT/kitty
~/.config/kitty/kitty.conf
    include icewine/defaults.conf
    include ../icewine/current/kitty.conf
    font_size 16                       # my setting
```

The Hyprland entry prepends `hypr/icewine/?.lua` to Lua's search path; Neovim
runs `nvim/icewine/defaults.lua`; UWSM sources `uwsm/icewine/env`. These loaders
use HOME/XDG paths, with no hardcoded `/usr/share` or `/nix/store` dependency.
Nix provenance checks remain intentional for recognizing old Home Manager links.
Generated selections remain under `icewine/current`, separate from shared defaults.

For another packaging environment:

- Supply compatible Hyprland Lua, Quickshell/Qt (including virtual keyboard),
  systemd/UWSM session wiring, command wrappers/tools and selected applications.
- Launch Quickshell from the user's writable configuration root and initialize it
  before startup; a failed migration must prevent the new shell from starting.
- Supply `ICEWINE_THEME_ASSETS`, consistent HOME/XDG config/data/state roots and
  `ICEWINE_DEFAULT_FILES` to the Python theme CLI. The defaults tree contains
  `config/`, `data/` and optional `home/`, native entries and absolute package
  links. Retain `default-files.json` across updates and match feature flags/skip
  settings to the installed consumers.

#### Configuration inventory and native exceptions

Paths below are relative to XDG_CONFIG_HOME unless a different root is named.
“Current” means `icewine/current`; “none” means no generated appearance.

| Set | Native entry and shared package link | Appearance and personal settings |
| --- | --- | --- |
| Hyprland / handheld | writable `hypr/hyprland.lua`; `hypr/icewine -> ROOT/hyprland` | shared behaviour loads `hypr/modules/Theme.lua -> Current/Theme.lua`; append overrides after desktop/Deck loading |
| Quickshell / handheld | writable `quickshell/shell.qml`; `quickshell/icewine -> ROOT/quickshell` | packaged palette reads `Current/palette.json`; instantiate/customise components in the entry; singleton settings exception below |
| Kitty | writable `kitty/kitty.conf`; `kitty/icewine -> ROOT/kitty` | include shared defaults, `Current/kitty.conf`, then inline overrides; no new `host.conf` |
| Neovim | writable `nvim/init.lua`; `nvim/icewine -> ROOT/nvim` | shared defaults load/reload `Current/nvim-theme.lua`; append overrides in init.lua |
| Bash / ble.sh | home startup links to writable `icewine/shell/{bashrc,profile,bash_profile}`; `icewine/shell/icewine -> ROOT/bash` | interactive shared defaults source `Current/ls-colors.sh`; put interactive overrides in bashrc; native startup/ble.sh exceptions below |
| UWSM | writable `uwsm/env`; `uwsm/icewine -> ROOT/uwsm` | shared exports first, inline exports afterward; none |
| Hypridle | writable `hypr/hypridle.conf`; `hypr/hypridle-icewine -> ROOT/hypridle` | native `source` first, inline general settings afterward; none; link-name/listener exception below |
| GTK CSS 3 / 4 | writable `gtk-{3,4}.0/gtk.css`; neighbouring `icewine -> ROOT/gtk` | import shared semantic defaults, `Current/{gtk.css,gtk4.css}`, then inline CSS; generated complete CSS also serves legacy/named-theme consumers |
| GTK settings / named themes / Flatpak | `gtk-{3,4}.0/settings.ini -> Current/{gtk-settings.ini,gtk4-settings.ini}`; generated named GTK3 themes in XDG_DATA_HOME/themes and Flatpak extensions | key-file / external-theme exception below; local settings.ini files stay active |
| Fastfetch | normal `fastfetch/config.jsonc -> Current/fastfetch.jsonc` | whole-file JSONC exception; custom native files stay active; Bash invokes PATH-selected fastfetch without forced config flags |
| Starship | normal `starship.toml -> Current/starship.toml` | whole-file TOML exception; shared Bash uses normal file or explicit existing STARSHIP_CONFIG, so custom files stay active |
| Yazi | `yazi/{theme,keymap}.toml -> Current/yazi-{theme,keymap}.toml`; dependency plugin files under `yazi/plugins/mount.yazi` | TOML/flavour/plugin exception below; edited/native host files remain active |
| btop / user-dirs | optional host defaults `btop/btop.conf`, `user-dirs.locale` through defaultFiles; no Icewine-owned source defaults | host ownership / native flat-file exception; no appearance generation |
| Desktop entries / Steam masks / MIME defaults | package `share/applications` entries, XDG_DATA_HOME/applications masks and editable uuctl mask | desktop-file data exception; no appearance |
| Wallpapers | XDG_DATA_HOME/wallpapers defaults supplied by host; selection in XDG_DATA_HOME/icewine/wallpapers | image-data exception; generated selected/blurred images are not app config |
| SDDM | immutable theme package share/sddm/themes/icewine; mutable `/var/lib/icewine/sddm/theme.ini` | system/login ownership exception; generated palette is separate from user configuration |
| Browser | optional Firefox package and MIME defaults; GTK styling and system light/dark preference | browser profiles, theme extensions and custom styles remain user-owned |
| InputPlumber / services / launch tools | packaged YAML profiles, system/user units and executable scripts wired by NixOS | host/system/package ownership exception; none |

The exceptions describe actual loader and ownership boundaries:

- **Hyprland compatibility hooks:** shipped Binds and Autostart now live in
  ROOT/hyprland/modules. Their old paths are managed aliases through `hypr/icewine`,
  preserving the existing loader and Deck's Binds exports. New installs have one
  writable Hyprland entry; add personal commands/bindings there. Edited hooks or
  host-selected `defaultFiles` hooks remain separate and active, with ownership
  diagnostics; they are compatibility/host overrides, not the default format.
- **Quickshell Settings:** packaged components import the local QML singleton
  `quickshell/config/Settings.qml` using its neighbouring qmldir. This native
  singleton exposes readonly policy properties used by Desktop/Handheld SessionControl
  and BatteryAlert; shell.qml instantiates their root. Putting settings only on
  that root cannot replace singleton imports or assign its readonly values;
  importing the application entry back into its own components creates a cyclic
  component dependency. Retain this writable singleton/manifest for host and user
  settings; extra user component directories are optional explicit imports.
- **Bash:** Bash natively distinguishes login profile, interactive bashrc and
  bash_profile; a single entry would change which shells execute login additions.
  The existing home links and startup order remain. Only interactive enabled
  Bash sources shared defaults; noninteractive startup returns before personal
  interactive code. Profile has no shared behaviour to source; bash_profile sources
  profile and bashrc before login-only overrides. ble.sh remains the dependency's
  own startup script, selected from the user package profile. See the
  [Bash startup rules](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html).
- **Hypridle:** both applications use the `hypr` config directory, so its package
  link is named `hypridle-icewine` to avoid the Hyprland `icewine` link. Upstream
  [source loading](https://github.com/hyprwm/hypridle/blob/main/src/config/ConfigManager.cpp)
  resolves paths relative to the current config and appends anonymous listener
  blocks. Later general values override; additional listeners append rather than
  replacing timers. To replace/remove shipped listeners, remove the source line
  and keep a local full config; future shared timer updates then do not apply.
- **GTK settings:** GTK uses [GKeyFile settings.ini](https://docs.gtk.org/gtk4/class.Settings.html),
  whose [format](https://docs.gtk.org/glib/struct.KeyFile.html) has no include directive.
  Its native system/XDG layers do not provide a per-user generated layer followed
  by an include in the same file. Keep the generated link or replace it with one
  native writable file; the latter opts out of generated settings while CSS imports
  still follow themes. Native [CSS loading](https://docs.gtk.org/gtk4/class.CssProvider.html)
  permits imports/inline rules, hence CSS entries do adopt the format. Named GTK3
  themes and Flatpak extensions need complete external theme directories, not a
  user entry; their existing generated ownership and retirement remain.
- **Fastfetch / Starship:** their native configuration selects one
  [JSONC config](https://github.com/fastfetch-cli/fastfetch/wiki/Configuration) or
  [TOML config](https://starship.rs/config/). Fastfetch's
  [schema](https://github.com/fastfetch-cli/fastfetch/blob/dev/doc/json_schema.json)
  has no configuration include; Lua preload runs helpers, not JSONC config layering.
  Starship's [config loader](https://github.com/starship/starship/blob/master/src/config.rs)
  parses the selected TOML, without an include layer. A package link cannot make
  native parsers combine shared defaults, generated values and inline overrides.
  Retain one generated normal-path link; copy it to a writable normal-path file
  for personal settings. That whole file stays active but no longer follows themes.
  There is no dead package link or custom merge engine. The legacy generated
  `Current/kitty-base.conf` remains for already-edited old Kitty entries.
- **Yazi:** [configuration mixing](https://yazi-rs.github.io/docs/configuration/overview/)
  merges the program's built-in presets with one user TOML file; it does not include
  a separate Icewine keymap. Native [flavours](https://yazi-rs.github.io/docs/flavors/overview/)
  could layer theme settings but require a matching tmtheme.xml. The
  [flavour loader](https://github.com/sxyazi/yazi/blob/main/yazi-config/src/theme/flavor.rs)
  forces that flavour's preview-highlighting path, superseding user syntect_theme.
  Icewine currently generates UI colours only, with no tmTheme asset; converting
  this to a flavour would change previews or require a new highlighting artifact
  and policy. Keep the generated complete theme/keymap links; writable replacements
  stay active and opt out of generated updates. The mount plugin is dependency
  executable code loaded by Yazi's native `plugin mount` resolver, not a user
  settings entry. Existing tracked vendor files update only when unchanged; edited
  plugins remain active. No fabricated TOML include or new flavour framework.
- **Host/data/system sets:** btop and user-dirs defaults, wallpapers and additional
  `defaultFiles` come from the host. Icewine cannot move host policy into its shared
  package. [btop's loader](https://github.com/aristocratos/btop/blob/main/src/btop_config.cpp)
  reads recognised assignments from one file, without include support; locale/image
  and [desktop-entry data](https://specifications.freedesktop.org/desktop-entry-spec/latest/)
  are native data formats rather than shared-code entry points. SDDM operates before
  the user's session with system theme paths; InputPlumber YAML is an external
  service input. NixOS owns their
  installation, dependencies and privilege boundary. Their immutable assets and
  mutable palette/data paths remain separate; customisation uses the existing
  host options or native user files, never a fake per-user include.

Nix-specific package construction, dependency selection and session environment
wiring stay in the NixOS module. Ordinary-directory loader checks establish this
path contract; they do not validate another distribution's session integration.

The neighbouring `icewine` links are managed package identity. `defaultFiles.config`
may supply these settings and hooks; it cannot supply packaged implementation
paths. Changes to internal QML/JS or Lua modules belong in an Icewine source fork.
Updates refresh the implementation package without copying it into writable home
files, while preserving edited settings and entry points. Existing edits to an
entry point remain your compatibility responsibility when the packaged API changes.

The first migration requires full `icewine init`. Unchanged recorded legacy
implementation is backed up and retired automatically. Edited or untracked
legacy modules, old entry points, and unknown package/container links block
migration before files or generated appearance are changed; the old entry points
and code remain in place. Retirements and both entry points are backed up as one
migration batch. The complete layout is rechecked after backups/removals, during
loader installation and before ownership is committed. A detected late edit,
new legacy component or mounted-file failure aborts migration. Already switched
loaders roll back only if still unchanged; removed files restore only to absent
paths behind unchanged parents. New user content remains preserved, with recovery
backups reported if a path cannot be restored. The individual loader writes are
not atomic across a running session; finish editing before init.
Back up the listed conflicts, move settings/bindings
into the supported hooks or custom components into a separate local directory,
then move the conflicting legacy paths aside and rerun `icewine init`. Internal
behaviour edits require porting to a source fork. Untracked files are not adopted
based on matching today's bytes. Do not use reset as a migration shortcut: it
also restores settings and bindings within its explicit scope, and it cannot
bypass implementation conflicts. Untouched Settings, Binds, Autostart and host
hooks retain their existing paths; local edits to them survive ordinary init.

Rollbacks within the packaged layout restore the implementation link and
unchanged writable defaults. A rollback to the previous writable implementation
layout can restore its unchanged recorded files, but cannot reconstruct user
edits moved elsewhere; keep the migration backups and any manually moved code.
Init preserves edited removed defaults and unrelated files. The new Kitty entry
has inline overrides. An explicitly host-selected defaultFiles `kitty/host.conf`
retains its include as a host-ownership exception. Other nonempty/unknown legacy
host.conf files block migration before
any entry or theme changes; move its settings after the includes in kitty.conf,
back up and move host.conf, then rerun full init. Reset cannot bypass this conflict.
An edited/untracked old Hyprland loader likewise blocks the link migration; port
its loader and move its overrides into the native entry before retrying. New
package links use the same unknown-link/parent guards during init/reset, before
migration changes generated output. Theme/transparency/apply commands update
appearance without switching or validating package links. Review Quickshell
settings after an update.
Init retires removed or disabled shipped defaults only if they still match the
record, saving a backup first; edited remnants and other user files remain.
A mounted file that cannot be removed remains with a diagnostic. Disabling
Icewine entirely runs no initializer and leaves configuration, state and user
data intact. Changing an XDG root also leaves the previous location intact.

The packaged layout requires successful implementation migration. Init does not restart the running shell; restart `icewine.service`
after adopting Quickshell changes. Updates preserve the selected theme,
transparency, fullscreen preference and independently selected wallpaper.
Init/reset serialize with each other and recheck live files after backup and
preparation, preserving changes detected during installation. Ordinary editors
do not take that lock: an edit in the narrow gap after the final check can still
race replacement, and mounted files use a backed-up direct write. Finish editing
Icewine defaults before a rebuild, init or reset; this is not a transaction with
independent editors.
`icewine init APP` installs missing files for one of `quickshell`, `gtk`,
`yazi`, `fastfetch`, `starship`, `hypr`, `uwsm`, `btop`, `user-dirs`,
`wallpapers`, `nvim`, or `bash`. `icewine reset APP` backs up and refreshes
only that app's files without clearing the selected theme; plain `reset`
restores every Icewine-owned file and clears the CLI selection.
`icewine theme` lists the installed themes and effective selection;
`icewine theme tokyo-night` and `icewine theme dracula` save a choice under
`$XDG_STATE_HOME/icewine/theme`. On NixOS, `services.icewine.theme` accepts
`null` (the default), `"tokyo-night"`, `"dracula"`, `"nord"`, `"gruvbox-light"`,
`"gruvbox-dark"`, `"catppuccin-latte"`, `"catppuccin-frappe"`,
`"catppuccin-macchiato"`, or `"catppuccin-mocha"`. An explicit Nix value
overrides the CLI choice; otherwise the CLI choice wins, then Catppuccin Mocha.
Catppuccin palettes use the [official colours](https://github.com/catppuccin/palette)
(MIT; licence in `theme/assets/themes/CATPPUCCIN-LICENSE`). Latte is light;
Frappé, Macchiato and Mocha are dark. Neovim requires `catppuccin-nvim`,
provided by the NixOS editor configuration.
`icewine theme status` reports shell application or pending consumers while
Quickshell is running; without the shell it reports the saved selection and
unknown live status. Set `ICEWINE_THEME_TRANSITION=off` in the `icewine.service`
environment and restart that service once to disable subsequent colour
transitions.

When Icewine's SDDM login is enabled, only `services.icewine.user` publishes the
greeter's theme ID to `/var/lib/icewine/sddm/theme.ini`. NixOS creates this
selected-user-owned directory; the file is publicly readable but contains only
the theme ID. SDDM uses the matching packaged palette at its next greeter start
(normally after logout), not during an already-running greeter. Missing,
unreadable or unrecognized IDs use the packaged Tokyo Night palette. No theme
change needs sudo or a NixOS rebuild. On reboot, `icewine-init.service`
republishes the saved selection before SDDM starts; disabling Icewine login
stops publication.

`icewine transparency off|low|med|high` saves an independent transparency
preference. With no argument it reports the saved level. Kitty background /
inactive-window opacity is 1.00/1.00, 0.80/0.75, 0.60/0.55 or 0.40/0.40;
`high` is the default. Theme changes and login retain this choice. Hyprland
reloads where available; reopen Kitty to use its new background opacity.
Kitty backgrounds mix 88% of the darker palette base and 12% black
for a smoky tint without adding accent colour. Only background opacity changes; terminal text stays opaque.
Blur remains unchanged. A full `icewine reset` restores `high`; targeted resets
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
rereads its full configuration, including inline settings, any explicit local
includes and command-line overrides, and may reset a temporary font-size change or preserve colours set
by an application. Neovim instances with an older or edited `init.lua` may not
have the Signal hook and remain pending. Yazi receives a reload broadcast for
all current user clients, including other sessions; it is not acknowledged per
instance. GTK's theme and light/dark preference are published through
GSettings; custom CSS in already open GTK or Flatpak apps may require reopening
those apps. Starship uses the new theme at the next prompt and Fastfetch at its
next run. The CLI reports failed or pending consumers separately from the saved
selection.
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
Native GTK4 uses Adwaita with Icewine's user CSS. GTK 4.16 and newer can use
the palette's window, view, headerbar, sidebar, card, accent and status CSS
variables in libadwaita; older GTK4 releases retain the named colour mapping.
Flatpak GTK4 apps do not receive this host CSS through the GTK3 extension.
Browser colour mapping remains browser-controlled; web content and privacy
preferences are unchanged.

Browser profiles, theme extensions and custom styles remain user-owned.
Icewine supplies GTK styling and the system light/dark preference; it does not
publish a separate browser palette or native messaging host.

The Bash starter files live under `$XDG_CONFIG_HOME/icewine/shell/`; `.bashrc`,
`.profile` and `.bash_profile` link to them. NixOS supplies current package paths,
feature flags and session variables, so disabling Fastfetch, ble.sh or Starship
on rebuild takes effect without replacing an edited Bash starter. Existing home
dotfiles and recognized Home Manager links are backed up on migration or reset;
unknown symlinks remain untouched. If you previously set Home Manager Kitty,
Fastfetch, Starship, Yazi or Hypridle options, move those custom settings into
the corresponding editable files. Icewine no longer reads those options. Review
the saved `defaults-migration-*` files before removing the old Home Manager
configuration. A regular file edited by the user is preserved by `init`; a
scoped `reset` backs it up before restoring the default.
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

Firefox's web/PDF defaults are in the selected user's package profile. Full
`icewine init` backs up and retires old Home Manager `mimeapps.list` links only
when they contain exactly Icewine's five Firefox defaults, at either the XDG
config or data location. Combined host MIME files and edited files remain in
place and take priority. If you disable Firefox or change the browser and a
combined file still names `firefox.desktop`, remove those five web/PDF defaults
from the host's `xdg.mimeApps.defaultApplications` and activate Home Manager.
If Home Manager no longer owns that file, copy its contents to a writable
temporary file, replace the old symlink with that file at
`$XDG_CONFIG_HOME/mimeapps.list` or `$XDG_DATA_HOME/applications/mimeapps.list`,
and remove only those entries, preserving the other associations.

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

The Gamescope launcher is installed in the selected user's NixOS package
profile while `steam.enable` is true. Steam hiding entries are owned symlinks
under `$XDG_DATA_HOME/applications`, ahead of Flatpak exports. Disabling Steam
integration removes those masks on the next full `icewine init`, run during
boot and user activation, and removes the profile launcher on the next
generation. Old Home Manager links are backed up during migration; local
launcher edits and unknown symlinks remain untouched.

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

Icewine installs native Firefox and gives the selected user defaults for web
links, HTML and PDFs through that user's package profile. User and host MIME
settings remain higher priority, including Nixos's independent media defaults.

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
| `battery.enable = false;` | Icewine battery warnings and automatic sleep; UPower remains available for battery data and host policy. |
| `shell.enable = false;` | Icewine's Bash configuration and all shell integrations below. |
| `shell.fastfetch.enable = false;` | Fastfetch installation and startup report. |
| `shell.blesh.enable = false;` | ble.sh installation and integration. |
| `shell.starship.enable = false;` | Starship installation and prompt. |
| `shell.starship.git.enable = false;` | Git information in the Starship prompt. |

Opt-outs retire recognised Icewine-generated theme links and unchanged recorded
shipped GTK CSS import entries, preserving standalone host-selected CSS, edited
files and unknown links. Edited CSS
with an Icewine import remains your override; remove that import to stop following
Icewine's generated colours. GTK opt-out also retires unchanged recorded Flatpak
CSS and Icewine's named-theme links. In a live session, it resets `gtk-theme`
only when the value still matches Icewine's ownership record; older unrecorded
selections need a manual change through your GTK settings. The existing colour
scheme preference remains yours, and running applications may need restarting.

Default-file updates retire untouched removed files before installing their
replacements, so files can become directories in one `icewine init`. Directory
ownership is not recorded: replacing a directory with a file requires you to
back up and move that directory first, even when it is empty. Icewine reports
the conflict and preserves its contents.

Battery thresholds are editable in `quickshell/config/Settings.qml`: 20% low,
10% critical and 5% danger warnings, then a 3% Suspend request by default.
These replace former `services.batsignal.extraArgs` values; no current Nixos
host sets an override. Icewine reads UPower's aggregate display battery, but
does not change the host's UPower power policy. Warnings and the 3% sleep request
require Quickshell to be running. Suspend uses the same session action as the
Sleep button and reports a failed request; check notifications and sleep on
real hardware without deliberately draining a battery.

With the Kitty preset active, Icewine installs editable
`$XDG_CONFIG_HOME/kitty/kitty.conf` entry. It includes shared defaults and generated
appearance before your inline settings. Move former Home
Manager Kitty settings from the migration backup after its includes if needed.
Setting `terminal.preset = null` leaves Kitty installation and configuration to
the host.

The handheld interface is opt-in (`handheld.enable = true;`), not enabled by
default. There is no blanket exclusion list for core desktop dependencies.
