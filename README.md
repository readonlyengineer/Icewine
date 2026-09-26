# Icewine

Unified Hyprland desktop for Desktop/Laptop/Handheld/HTPC; developed NixOS-first.

Icewine combines a Quickshell desktop, Hyprland window behaviour and an optional
handheld interface with a controller radial, on-screen keyboard and nested
Gamescope integration. It is an experimental personal desktop environment.
The handheld mappings currently target Steam Deck controls. HTPC is part of the
intended scope, not a claim of separate hardware validation.

## NixOS integration

Add the input to your system flake:

```nix
inputs.icewine.url = "github:readonlyengineer/Icewine";
inputs.icewine.inputs.nixpkgs.follows = "nixpkgs";
inputs.icewine.inputs.home-manager.follows = "home-manager";
```

The last line assumes your flake already declares Home Manager. Otherwise omit
it and Icewine uses its own pinned Home Manager input. The module imports the
Home Manager NixOS integration itself.

Import the module and configure an existing user:

```nix
imports = [ inputs.icewine.nixosModules.default ];
services.icewine = {
  enable = true;
  user = "alice";
};
```

Kitty and the Bash setup below are installed and configured by default. Install
other selected applications in your host configuration and set the user's Home
Manager `home.stateVersion`. Select your login manager/session separately;
the session remains `hyprland-uwsm`. Icewine does not create users or configure
autologin, storage, persistence, networking, SSH, a kernel or binary caches.

For the handheld UI:

```nix
services.icewine.handheld.enable = true;
```

The physical host supplies Steam Deck/Jovian hardware support, InputPlumber's
system service, native Steam and panel orientation. Handheld UI selection alone
does not configure Steam Deck hardware. A VM can select the same UI and disable
the controller service when no controller is present.

## Host choices

Kitty and Bash are independent presets. These defaults require no declarations:

```nix
services.icewine = {
  terminal.preset = "kitty";
  shell = {
    enable = true;
    fastfetch.enable = true;
    blesh.enable = true;
    starship.enable = true;
    starship.git.enable = true;
  };
};
```

Fastfetch includes the current user's network information. It runs once at
interactive Bash startup, including SSH and TTY sessions, and never during
non-interactive startup. Bash configuration does not change the user's login
shell. The Starship preset keeps Icewine's time/directory/duration layout and
includes the standard Git branch, commit, state and status modules. Git metrics
remain disabled, matching Starship's default. `shell.starship.git.enable = false`
removes all Git prompt modules, including the branch name.

Disabling a component leaves its installation, configuration and startup hooks
to the host. Existing Home Manager options override preset defaults, for example
`home-manager.users.alice.programs.kitty.font.size = 12`.

To manage both terminal and shell yourself:

```nix
services.icewine = {
  terminal.preset = null;
  shell.enable = false;
  applications.terminal = [ "foot" ];
  applications.terminalExecute = [ "foot" "--" ];
};
```

Commands are argument lists, not shell strings. Apart from the Kitty preset,
the host installs applications selected by these options:

- `applications.terminal`: defaults to Kitty; required when the preset is null.
- `applications.terminalExecute`: terminal prefix for running a command;
  defaults to the terminal command followed by `-e`.
- `applications.editor`, `fileManager`, `steam`: application commands.
- `authenticationRequired`: defaults to `true`; uses the `icewine` PAM service.
- `hyprland.extraModules`: Lua files keyed by filename, overlaid into the
  generated `modules/` directory. Optional `host.lua` and `Personal.lua` run
  after the shared configuration. `Autostart.lua` can replace session startup.

Personal wallpaper files may be supplied at
`~/.local/share/wallpapers/current.jpg` and `current_blurr.jpg`. None are bundled.
The palette is also exported as `lib.palette` for downstream application themes.

The user service is `icewine.service`. Handheld mode also adds
`icewine-inputplumber-hyprland.service` and `icewine-keyboard.service`.
Quickshell's executable, configuration directory and global-shortcut application
identifier retain their upstream names.

## Development

Run the window-policy regression test without a compositor from the repository
root with Lua installed:

```sh
lua hyprland/tests/window-policy.lua hyprland/modules/WindowPolicy.lua
```

The `logic` check runs this alongside the existing JavaScript/Lua suites;
`modules` checks desktop/handheld packaging, including exclusion of developer
tests from the deployed Hyprland configuration:

```sh
nix build --no-link path:.#checks.x86_64-linux.logic path:.#checks.x86_64-linux.modules
nix flake check path:.
# In the consuming configuration, test a local checkout without changing its pin:
nix build .#nixosConfigurations.HOST.config.system.build.toplevel \
  --override-input icewine path:/absolute/path/to/Icewine --no-write-lock-file
```

Checks cover JavaScript/Lua logic and desktop/handheld module composition. They
do not replace real-device testing of controller routing, suspend, touch or
locking. Source files are ordinary QML, JavaScript, Lua and shell; only NixOS
integration is provided today.

Icewine builds on Hyprland, Quickshell, InputPlumber, Gamescope and the NixOS/Home
Manager module systems. Handheld patches are retained with their source URLs in
`modules/handheld.nix`. A project licence is still to be selected before release.

### Desktop defaults

Icewine also provides GTK styling, idle locking, battery warnings and a Yazi
file-manager preset. All are enabled by default:

```nix
services.icewine = {
  gtk.enable = true;
  idle.enable = true;
  battery.enable = true;
  fileManager.preset = "yazi";
};
```

Yazi includes video previews, archive support, palette colours and the `M` mount
plugin binding; the preset enables GVfs. Set `fileManager.preset = null` to manage
your own file manager and set `applications.fileManager` to its command list.
Normal Home Manager `programs.yazi` settings remain available for customisation.

The network popup shows two minutes of Wi-Fi/Ethernet upload and download
history. The performance icon (`Super+Shift+P`) shows matching CPU/RAM usage
graphs, readable GPU usage counters and the first temperature channel from each
sensor chip. Sampling runs once per second, including while the popups are closed.
GPU usage needs a readable `gpu_busy_percent` counter; unsupported readings show
as unavailable. Sensors are discovered at shell startup. The performance popup's
**Advanced · btop** button opens btop in the configured terminal.

The power/battery popup controls brightness on the monitor hosting the widget.
Built-in backlights use `brightnessctl`; external monitors need DDC/CI enabled in
monitor settings and a supported connector. Unsupported or ambiguous mappings
show an unavailable slider. Icewine enables NixOS I²C support for local-session
access. Keep awake pauses idle locking, display-off and automatic suspend until
switched off; it defaults off on shell startup. Manual sleep and critical-battery
suspend still work. Do not disturb silences ordinary notification popups, sounds
and pulses while retaining history; critical notifications bypass it. DND also
defaults off on shell startup.

Idle defaults lock after 10 minutes, turn displays off after 20 and suspend after
30, respecting inhibitors. Locking is also requested before sleep. Override
`home-manager.users.<user>.services.hypridle.settings.listener` to change the
schedule or omit automatic suspend. Battery defaults warn at 20%, become critical
at 10% and request suspend at 3%; override `services.batsignal.extraArgs` in Home
Manager to change these. Each service can be disabled with its Icewine switch.

GTK uses the Tokyonight theme and Icewine palette CSS; native Home Manager `gtk`
settings can override it. Flatpak permissions and application policy remain with
the host. Bash receives palette-derived `LS_COLORS`. The internal UWSM control
launcher is hidden. Waybar is retired; Quickshell supplies the desktop bar.
