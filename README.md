# Icewine

Icewine is a unified Hyprland desktop for desktops, laptops, handhelds and HTPCs,
developed NixOS-first.

It is deeply experimental; it will move fast and break things. Use at your own risk.

Experimental source bootstrap and native packages for [Arch Linux and CachyOS](packaging/arch/README.md)
open the existing manager and reuse the login manager; installed-session and hardware qualification remain pending.

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
            desktop.enable = true;
            terminal.enable = true;
            filemanager.enable = true;
            steam = "flatpak";
            login.greeter.enable = true;
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
Rebuild your host, run `icewine` as your desktop user from a TTY and Apply
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
Steam session. If Steam is running outside Gamescope, Icewine reuses it without
restarting it; quit Steam manually before retrying a Gamescope launch. Non-Steam games and emulators added to Steam can use the same
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
Your original file can then be moved or deleted. The desktop and lockscreen share
this wallpaper. The lockscreen blurs and dims it behind a large clock and date;
missing images fall back to an opaque dark background. Password input stays
concealed; edits briefly pulse the clock (colour only with motion disabled).
Press Enter to submit, or Escape/Ctrl+U to clear. The keyboard button opens the
shared Icewine keyboard, with input kept inside the lock surface. When
authentication is explicitly disabled, tap or press Enter to unlock.

Tuigreet uses declarative colours; it does not read or publish user theme state.
The old authentication wallpaper override and custom greeter are retired. Existing
user files are left in place. Keyboard/touch and real login/unlock behavior still
need validation on each supported device and distribution.

### On-screen keyboard

Use the topbar **Keyboard** button, or L5/the handheld radial's Keyboard action.
The shared 84-key US keyboard opens pinned at the bottom of the active output;
**Unpin** enables header dragging, and **Pin** restores its standard position.
Small screens scroll the key grid. D-pad/stick selects a key, A activates and B
hides; touch and pointer work alongside controller selection. Shift, Ctrl, Alt
and Super are one-shot latches; Caps changes letter case. Hold a typing/editing
key to repeat, and release or move away to stop further activations.

Ordinary applications use unprivileged `wtype` seat input; retain the intended
application's focus. Already emitted input cannot be retracted by hiding the
keyboard. Wayland/Xwayland, nested Gamescope, touch/controller hardware and
focus/lock transitions still need real-session validation. Locked entry uses
Qt locally and disables application/window shortcuts; authentication is unchanged.

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

Shell Extras Apply selects the generated Icewine theme in a regular btop config,
preserving other preferences unless Overwrite is selected. Symlinked configs are
preserved; set `color_theme = "icewine"` in their source yourself. Theme changes
update colours only. Install btop through your host package configuration and
reopen it after Apply or changing themes.

### Manage integrations and dotfiles

```sh
icewine
```

Tab cycles through Installer, Appearance and Widgets. Use Up/Down or
Shift-Tab to navigate rows, Space to select, and Enter on Apply or Cancel.
Left/right cycles Steam, Theme or Transparency. Theme/transparency changes and
wallpaper selections apply immediately; Installer/Appearance Apply affects utility choices.
Widgets Save (`s`) commits only widget preferences; Cancel/Esc discards unsaved drafts.
The module list scrolls with focus. Space toggles a card module; Left/right moves
it to the previous/next stack, and `n` moves it to a new stack. `-`/`+` moves it
within its stack; `[`/`]` moves its stack; Delete removes the whole stack.
Removing a stack disables its members; removing its last member deletes the empty
stack. The first member supplies the topbar icon. Rows show stack/member order
and the primary, secondary, tertiary accent cycle; modules absent from stacks
are disabled. These preferences describe configured membership, including cards
that are temporarily unavailable.

Bar Width selects 50–100% of the output (default 80%). Bar Style selects Anchored
(default, flush edge) or Floating (pill corners with a 4-pixel gap). At 100%,
both styles have square corners; 99% retains rounding. Overflowing workspace
and status rows scroll horizontally by dragging or using their scrollbars.

Bar Behaviour offers Autohide (Keyboard), Autohide (Keyboard & Mouse), Toggle
(Keyboard), and Always Show. The default is keyboard hold-to-show; mouse mode
also reveals at the screen edge. Bar Locations offers Above (default overlay),
Top, and Bottom. Top/Bottom reserve space while visible; Bottom uses the bottom
mouse edge and opens cards upward. Left/Right cycles these choices before Save.
Always Show takes no keyboard focus by itself and remains visible after ordinary
application/media handoffs. Explicit hide or capture handoff suppresses the bar until
the next shortcut, widget or controller opening (mouse mode also permits a fresh
edge entry); unlocking restores the selected mode.
Notification toasts and the window switcher default to enabled. Disabling toasts
keeps notification history and sounds; session and authentication controls remain.
Onscreen Keyboard Access offers None (default), Launcher, or Topbar. Launcher
adds a searchable Onscreen Keyboard action; Topbar adds a keyboard icon. Both
open the existing keyboard for the original application. Lockscreen and
handheld/controller access remain independent.
Preferences live in `$XDG_STATE_HOME/icewine/widgets.json` (normally
`~/.local/state/icewine/widgets.json`); host persistence remains your policy.
NixOS `services.icewine.widgets.notificationToasts` and `.windowSwitcher` default
to null (user choice); true/false enforces policy in the manager and shell.
`.barBehaviour` accepts `keyboard`, `keyboard-mouse`, `toggle`, or `always`;
`.barLocation` accepts `above`, `top`, or `bottom`. `.barWidth` accepts integer
percentages 50–100; `.barStyle` accepts `anchored` or `floating`. `.oskAccess`
accepts `none`, `launcher`, or `topbar`. All default to
null (user choice).
The Widgets page requires shipped Settings.qml and a desktop/handheld entry;
custom settings or entries are read-only here. Invalid non-null widget policy
also makes the editor read-only and reports an error; repair the host policy
before saving.
Wallpaper pickers use optional Yazi; Configure monitors opens optional HyprMon.
HyprMon owns its live/save actions, which Cancel does not undo.
NixOS utility selections reflect the module options and are read-only. Apply
creates missing dotfiles; **Overwrite existing dotfiles** replaces selected defaults
without backups. It starts unchecked each time. Existing editable files are otherwise
preserved, including on rebuild, login and reboot. Explicitly host-managed files
and symlinked parent directories are preserved even with overwrite enabled,
including dangling links. Apply reports each skipped path. Host persistence
remains host policy; package, service and login choices remain host-owned on NixOS.

Appearance and Widgets use file ownership on every supported distribution:
linked preferences are shown read-only, while unrelated ordinary files remain
editable. Icewine's generated theme and implementation links keep working.
Theme policy and widget policy still take precedence. Configure monitors is
disabled when its main entry or HyprMon sidecar is linked; HyprMon otherwise
owns its own live/save behaviour.

Home Manager may supply ordinary configuration or preference links without any
Icewine Home Manager module. For example, with the normal XDG state directory:

```nix
home.file.".local/state/icewine/layout".text = "master\n";
home.file.".local/state/icewine/widgets.json".text = ''{"windowSwitcher":false}'';
```

Use the effective XDG path if you change it. Linking a shipped Settings.qml or
shell entry does not lock the separate widgets.json preference file when the
contents still match the shipped version. Install Icewine and enable host
services separately: installation remains through the NixOS module or the
experimental Arch/CachyOS packages; this adds no other distribution installer.

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
a stable package-managed path; generated theme files are kept separately.

```text
~/.config/hypr/
├── hyprland.lua                 ← Edit this: shared import, then your settings
└── icewine → /etc/icewine/implementation/hyprland/
    ├── icewine.lua              ← Loads shared behaviour and generated Theme.lua
    └── modules/                ← Shared bindings, window policy, docking, etc.

~/.config/icewine/current/        ← Generated appearance; do not edit
```

Shared implementation follows NixOS rebuilds and Arch package updates. After
upgrading from direct Nix-store links, run Apply once to adopt the stable paths;
edited entry points remain yours.

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

Fastfetch, Starship, btop themes, Yazi theme/keymap and GTK settings normally link to generated
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

Choose the persistent desktop layout fallback in `icewine` (Appearance),
or with `icewine layout scrolling|dwindle|master|monocle`. The Launcher stack's
layout card (or Super+Shift+D) changes only the focused workspace; **Use default**
removes its session choice. Choices survive locking, shell restarts and config reloads, and expire
when Hyprland exits. The picker displays the compositor's actual layout.

The saved fallback loads before your `hyprland.lua` overrides. Explicit user
workspace rules take precedence over that fallback; the handheld profile keeps
scrolling. Picker choices temporarily take precedence over workspace rules;
Use default restores those rules and otherwise inherits the global layout.
Saving a global fallback reloads Hyprland, so ordinary external runtime rules
clear on reload. For permanent workspace choices, use the native rule above.
Icewine reserves workspace selector spellings starting with a tab and a space
for its removable native picker rules; use ordinary selectors in user rules.
Desktop controls support scrolling, dwindle, master and monocle.

### SSH identities

The network stack's third card is SSH (Tab cycles cards). Import reads an
explicit existing private-key path with owner-only permissions and a concealed
passphrase; it keeps the original file. Generate offers Temporary (agent only)
or Permanent (an absolute new file path and passphrase confirmation). Permanent
files are saved for later import, without automatic loading. Public keys can be
displayed/copied; private keys are never displayed or copied.

X unloads only a temporary identity added by the card. It preserves files,
remote authorisation and existing SSH connections. Reboot removes temporary
identities; shell/card reopening keeps them. Ordinary platform memory policy
(including swap, hibernation and core dumps) still applies.

The card manages the native local `ssh-agent.service` at
`$XDG_RUNTIME_DIR/ssh-agent`, shared with ordinary SSH clients. Configure
`programs.ssh.startAgent = true;` in your NixOS host and run its native unit as
`Type=simple` with `ssh-agent -D -a %t/ssh-agent` so socket credentials match
the service PID. The paired Nixos common core supplies this foreground mode;
other distributions use the native package instructions. Session defaults preserve an
existing `SSH_AUTH_SOCK`; the card refuses mutations when it points elsewhere.
Discovery covers conventional client filenames and static `IdentityFile` paths;
host-dependent paths or unavailable public metadata may require explicit import.

### Screenshots

Press Super+Print to open Flameshot directly, then drag to select an area.
The handheld Screenshot action opens the monitor editor without delay.

In Flameshot, select the area to crop, then use arrows, shapes, freehand, text and
undo. Use an opaque filled rectangle to cover sensitive content; blur/pixelation
is not secure redaction. Choose **Save** or **Copy**, or press Esc to cancel without
exporting. Save defaults to Pictures (then the last Flameshot save directory),
with a date/time PNG name and a numbered suffix on collisions; the save dialog
asks before replacing a chosen existing file. No unannotated original is saved.
Flameshot's own settings can change save/copy behavior, including save-after-copy.
Icewine leaves those settings intact. Cancelling the save dialog discards the
unsaved edit, so choose the destination before closing it.

The Clipboard card is behind Notifications (Tab switches cards). Click an entry to
load it; its accent outline follows the current clipboard. The ↑ action loads
and sends one Ctrl+V to the retained original app. Release the opening shortcut
first; terminals with a different paste binding need manual paste. A last-moment
clipboard/focus change can race delivery; it is not an atomic transaction.

History holds up to 50 plain UTF-8 text/PNG entries, at most 5 MB each, in private
runtime storage. It resets on lock, shell restart and logout; sensitive hints are
respected but do not identify every secret. X and **Clear history** remove stored
entries while keeping the current clipboard. The card's age limit defaults to
Off; choose 5 minutes, 30 minutes, 1 hour or 24 hours. The preference survives
shell restarts. Age uses elapsed session time (excluding suspend), starting when
content is stored. Loading or repeated notifications of the same selection do
not renew it; copying different content and then copying it again starts a new
age. Shortening the limit removes already-old entries immediately. Expiry also
keeps the current clipboard. Original multi-format selections
and other content types are not retained. The regular single-seat Wayland
clipboard (including Xwayland bridging) is used; primary selection is not recorded.
Crash remnants stay private until
logout; history is never reloaded from them.

### Automatic fullscreen

```sh
icewine autofullscreen on        # Options: on, off; default: off
```

This enables scrolling's automatic fullscreen policy, fullscreens lone tiled
windows in dwindle/master, and defaults the focused monocle window to fullscreen.
Manual and application fullscreen choices take precedence.

## Applications

The manager/module offers Kitty, Yazi, Steam with optional Gamescope/Handheld,
an optional NixOS greeter and Starship/Fastfetch alongside the optional desktop session.
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
select replacement applications. Enabling Yazi sets the directory default on Arch
Apply; NixOS supplies a per-user package default without writing user MIME files.
Existing explicit user or host associations take precedence on NixOS.

Hyprland opens terminals through `xdg-terminal-exec`, directories through
`xdg-open`, and the browser through its XDG default. Set a preferred terminal in
`~/.config/xdg-terminals.list`, or customise shortcuts in `hypr/hyprland.lua`.


Install replacement applications and their configuration in your host. Neovim
plugins and language servers are host-owned; Icewine generates the optional
`icewine/current/nvim-theme.lua` appearance adapter and signals themed instances.

On NixOS, `services.icewine.login.greeter.enable = true` opts into native
greetd/tuigreet with the Icewine Hyprland UWSM session and session selection.
It requires `desktop.enable`; another display manager must be disabled explicitly.
Host `services.greetd` settings override these defaults. Users, PAM policy and
autologin remain host-owned; greetd autologin uses `settings.initial_session`.
Disabling the opt-in removes only Icewine's service defaults. A host's explicit
`services.greetd.enable = true` and command remain; if Icewine supplied the only
login service, configure a replacement or use console login before rebuilding.
The Arch/CachyOS installer does not install or configure a greeter; retain your
host's login manager there.

The default greeter command sets only the session launch command and available
Wayland sessions, leaving appearance and session remembering at tuigreet defaults.
For custom host commands, `login.enable` exposes optional styling through
`services.icewine.login.args`, using the declared theme or Catppuccin Mocha.
User theme changes do not publish to the greeter.
Console resolution and output scaling belong to the host; Hyprland monitor
settings do not configure the login VT. Native screen coverage needs validation
on the affected output before choosing a console/display-mode change.

These options belong under `services.icewine`:

| Option | Stops Icewine providing |
| --- | --- |
| `desktop.enable = false;` | Hyprland session integration; explicit Apply removes its implementation link |
| `terminal.enable = false;` | Kitty defaults |
| `filemanager.enable = false;` | Yazi and its GVfs default |
| `steam = "none";` | Steam integration and dependent Gamescope/Handheld |
| `gamescope.enable = false;` | Gamescope launch integration; ordinary Steam remains available |
| `monitors.enable = false;` | Optional HyprMon; locked default needs a Lua-compatible `monitors.package` override |
| `login.greeter.enable = false;` | Optional NixOS greetd service defaults; explicit host login configuration remains |
| `login.enable = false;` | Optional tuigreet styling arguments for custom host commands |
| `shellExtras.enable = false;` | Starship/Fastfetch defaults and btop styling |
| `shellExtras.git.enable = false;` | Git information in the prompt |
| `gtk.enable = false;` | GTK styling |
| `idle.enable = false;` | Automatic idle locking and sleep; manual locking remains |
| `battery.enable = false;` | Battery warnings and automatic sleep; UPower remains |

Battery thresholds live in `quickshell/config/Settings.qml`: warnings at 20%,
10% and 5%, then a suspend request at 3%. The shell must be running; test sleep
behaviour on your hardware without deliberately draining the battery.

See [modules/default.nix](modules/default.nix) for application commands and
`defaultFiles.config`/`defaultFiles.data` options for host-supplied editable defaults.
