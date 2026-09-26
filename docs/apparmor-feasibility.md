# AppArmor feasibility for Icewine

This report assesses source revision `da3d511e68c1b8255953ab7986a95b51c2e49295`
against the desktop configuration's pinned nixpkgs revision
`20b1ddd1aa5ace70c9468305030aa4f9ef79671b`. It is a source and documentation
assessment. No profile was parsed, loaded or exercised, and no running kernel,
D-Bus daemon or Icewine process was inspected.

## Conclusion

AppArmor is feasible for reducing the damage from a compromised fixed-purpose
Icewine helper. It is not presently a useful boundary between Icewine's shell,
launcher, lock screen and handheld overlay: all of those execute in one
Quickshell process. Confining Hyprland, Gamescope or the whole shell would also
require broad desktop, device and child-execution permissions, with substantial
compatibility and maintenance cost.

The sensible first experiment is therefore an opt-out, complain-mode pilot for
one or two narrow helpers, followed by enforcement only after real desktop and
Steam Deck traces pass the checks below. Do not describe this as hardening the
lock screen or compositor boundary.

## Actual boundaries and authority

| Component | Process and launcher | Required authority observed in source | Assessment |
| --- | --- | --- | --- |
| Hyprland | UWSM starts `hyprland-uwsm.desktop`; Icewine enables Hyprland with `withUWSM = true`. Lua in `~/.config/hypr`, including arbitrary host `extraModules`, runs in the compositor. | DRM/GPU, input and display devices, Wayland and Hyprland runtime sockets, configuration, application execution and session control. It launches generic host commands and `uwsm app`. | Do not custom-profile initially. A useful policy would be broad and mistakes can destroy the session. AppArmor would restrict compositor actions; it would not make an already compromised compositor trustworthy. |
| Icewine shell and lock | `icewine.service` executes the shared nixpkgs `quickshell/bin/qs`. Both desktop and handheld `shell.qml` instantiate wallpaper, notifications, topbar/launcher, `GameLauncher`, `SessionControl`, PAM authentication and `WlSessionLock`; handheld also instantiates `DeckOverlay`. | User configuration and icons, wallpaper, Steam shortcuts, `/proc`, `/sys`, Wayland, Hyprland IPC, Quickshell IPC, session/system D-Bus, PAM and its modules, PipeWire, system tray, UPower, Bluetooth/network services, child helpers and arbitrary desktop-entry commands. | A pilot profile could deny unrelated home writes and direct Internet sockets, but the profile is high-maintenance. It cannot separate the password-handling lock code from the launcher or other QML/JS loaded into the same address space. It therefore offers blast-radius reduction, not lock integrity. |
| Generic launchers | Generated `icewine-{terminal,browser,editor,file-manager,steam}` scripts `exec` host-selected commands. Launcher QML starts arbitrary desktop entries via `uwsm app --`; Hyprland also starts host commands. | Whatever each selected application needs. | Do not attach one generic policy. Inherit-mode confines every application as the shell; unconfined execution is an explicit escape; profile transitions require a maintained profile per target. Application sandboxing belongs to the application/host (Flatpak is already used for several applications). |
| Session control | Code is part of `qs`; it executes `loginctl`, `hyprctl` and `gdbus`, listens to logind, owns a Wayland session-lock surface, and calls PAM service `icewine`. | Wayland session-lock protocol, logind system bus, Hyprland control socket, PAM configuration/modules and authentication resources. | No separate profile is possible without a separate executable/process. PAM success does not repair compromise of the shared process before or after authentication. `pam_apparmor` is aimed at PAM *session* transitions and is not a substitute for profiling this PAM authentication client. |
| Screenshot and monitor helpers | Distinct store executables: `icewine-screenshot`, `icewine-monitor-capabilities`, and `icewine-monitor-brightness`. | Screenshot: Wayland capture, selection UI, clipboard, notifications and a chosen output directory. Capability probe: DRM sysfs/EDID. Brightness: DRM sysfs plus backlight or `/dev/i2c-*` through `brightnessctl`/`ddcutil`. | Best desktop candidates. Fixed child transitions can contain parsers/tools and limit file/device writes. Screenshot output paths and changing monitor/I²C devices still need host overrides. Medium maintenance. |
| InputPlumber routing | `icewine-inputplumber-hyprland.service` and `qs` run distinct generated scripts; they use `inputplumber`, `busctl`, `gdbus`, `jq` and fixed profiles in `/etc/inputplumber`. A system daemon performs the privileged work after polkit authorization. | System D-Bus calls/signals to `org.shadowblip.InputPlumber`, read-only profile files, and child execution. The existing polkit rule authorizes four actions for the configured user. | Strong handheld candidate because it is fixed-purpose and controls a privileged service. AppArmor can limit files, execution and bus messages only when D-Bus mediation is enabled; polkit still decides whether the daemon authorizes the action. Test on real hardware before enforcement. |
| On-screen keyboard | Separate `squeekboard` D-Bus user service; `icewine-keyboard-toggle` calls the user service and starts it with systemd. | Wayland input-method/layer protocols and session D-Bus; the toggle needs only the user bus and fixed child execution. | The toggle is a good narrow candidate. Squeekboard itself is plausible but needs upstream/profile research and runtime tracing; it is not Icewine-owned code. |
| Gamescope and Steam | Quickshell's `GameLauncher` starts Gamescope with the monitor-aware plan, which launches the host-selected Steam command and games. `GameLauncher` can also start arbitrary commands inside Gamescope. | GPU, input, audio, Wayland/Xwayland, networking, game files and arbitrary child applications. | Do not profile as an Icewine unit initially. A restrictive policy would need per-game/application transitions; an unconfined child transition largely removes containment. Prefer the host application's existing Flatpak boundary where configured. |
| `hypridle`, `batsignal`, `hyprpolkitagent`, PipeWire, logind and InputPlumber | Independent host/upstream services configured or consumed by Icewine. | Their normal service-specific authority. | They are not Icewine code. Reuse a maintained upstream/NixOS profile if one exists; do not copy their authority into an Icewine shell profile. No reusable upstream profile for the Icewine-named executables, Hyprland, Quickshell, Gamescope, Squeekboard or InputPlumber was established by this investigation. |

The code paths supporting this map are `modules/{default,home,desktop,handheld}.nix`,
`quickshell/{shell,deck/shell}.qml`, `quickshell/modules/{SessionControl,
GameLauncher}.qml`, `quickshell/modules/topbar/`, `quickshell/deck/DeckOverlay.qml`,
`scripts/inputplumber-intercept.sh`, and `hyprland/{modules,deck}/`.

## What the pinned platform can express

The local locks pin both Icewine and the desktop to nixpkgs `20b1ddd...`.
The relevant NixOS module interface provides `security.apparmor.enable`,
`policies.<name>.{profile,path,state}`, `includes`, `packages`, `enableCache`
and `killUnconfinedConfinables`. Enabling it adds AppArmor to `security.lsm`,
adds the kernel parameter and loads declarative policy through
`apparmor_parser`. The module warns that enabling the LSM needs a reboot, that
already-running processes do not become confined merely because a new
attachment appears, and that cache entries containing store paths accumulate
across changes. The Nixpkgs common kernel configuration enables
`CONFIG_SECURITY_APPARMOR`; the Steam Deck uses a separately pinned CachyOS
kernel, so its actual config and policy ABI remain runtime checks.

NixOS also exposes `services.dbus.apparmor = "disabled" | "enabled" |
"required"`, with `disabled` the documented default. `required` is the honest
choice for a design whose security claim depends on D-Bus filtering, because it
fails if the bus cannot enable AppArmor. This setting and the loaded policy
must be verified for both the system and per-user bus in the pinned system;
kernel AppArmor support alone does not establish D-Bus mediation.

NixOS can carry custom profiles directly in `security.apparmor.policies` and
share abstractions through `includes`/`packages`. Upstream AppArmor ships
policy language, abstractions and example profiles, while nixpkgs packages
`apparmor-profiles`; none found in the reviewed primary-source trees provides a
drop-in Icewine desktop policy. Start from the NixOS module and upstream
abstractions, but treat a new Icewine policy as custom maintained code.

### Attachment and versioning

Nix store executable paths include a content hash. An exact attachment such as
the evaluated `${pkgs.quickshell}/bin/qs` is narrow but changes when that output
changes; generating the attachment in Nix keeps policy and executable in the
same generation. A glob such as `/nix/store/*-quickshell-*/bin/qs` survives
updates but trusts any matching store output and makes audit attribution less
precise. A stable named profile entered with `aa-exec` or systemd's
`AppArmorProfile=` avoids executable-path attachment churn, but transition
permission and user-manager behaviour must be proven on the target rather than
assumed. Exact attachments are also the form for which NixOS documents
`killUnconfinedConfinables` support.

Generated shell applications introduce at least a wrapper, runtime shell and
their fixed tools. Execute rules must deliberately choose:

- `ix`: every child inherits the caller's restrictions, unsuitable for the
  generic application launcher;
- `px`/`cx`: enter a maintained profile/subprofile, appropriate for fixed
  helpers but only if every resolved store path and interpreter transition is
  covered; or
- `ux`/`Ux`: run unconfined, an explicit confinement escape. `Ux` scrubs the
  environment but does not preserve containment.

Open descriptors and resources inherited across execution can also retain
authority. AppArmor is additive to Unix permissions and does not revoke an
already opened resource merely because a later transition is narrower.

Host customisation is a policy input. `applications.*`, Hyprland `extraModules`, desktop entries, Steam
shortcuts, wallpapers and monitor/device topology vary by host or user. The
Hyprland modules execute inside the compositor; desktop entries can execute
through Quickshell. Allowing arbitrary host paths
or commands broadly defeats a fixed allow-list, while denying them breaks
documented extension points. A profile must either expose explicit host-owned
include fragments or declare those extension points incompatible with
enforcement.

## Mediation limits

- **Files and devices:** AppArmor can mediate path-based reads, writes,
  execution and mapped libraries, plus capabilities and selected device paths.
  Dynamic `/nix/store`, `/run/user/$UID`, DRM, input and I²C paths make desktop
  profiles version- and hardware-sensitive.
- **Wayland and Hyprland IPC:** access to filesystem-named Unix sockets can be
  restricted with file/Unix-socket policy supported by the loaded ABI. Once a
  client is connected, AppArmor does not understand Wayland object/protocol
  semantics; compositor protocol and permission policy remains decisive.
  Quickshell needs privileged protocols such as layer shell and session lock,
  while its adapter and helpers use Hyprland IPC.
- **D-Bus and portals:** AppArmor D-Bus rules can restrict bus, name, path,
  interface, method and send/receive/acquire operations only when the bus has
  AppArmor mediation enabled. A blanket `dbus,` rule yields little value.
  Portals add a brokered D-Bus API; allowing a portal method is not equivalent
  to a path rule and the portal's own authorization still applies.
- **PAM:** file, execution and capability rules constrain the shared `qs`
  process and loaded PAM modules. The PAM conversation and password remain
  inside that process. `pam_apparmor` session hats are application-directed
  transitions and do not split QML objects or authenticate the caller.
- **Polkit:** AppArmor can limit which bus messages reach a privileged service;
  polkit separately authorizes the subject. The existing InputPlumber rules
  are broad grants to the configured user for four actions, so both controls
  are needed for a meaningful reduction. Neither substitutes for the other.
- **Process interaction:** signal and ptrace rules can reduce same-UID process
  attacks if peer labeling is maintained. They do not make unconfined desktop
  peers safe, and broad `peer=unconfined` allowances weaken the boundary.
- **Networking:** family/type/socket operations can be restricted. A direct
  Internet deny may be useful for fixed local helpers. Quickshell still needs
  local sockets and service discovery; address-aware enforcement and the exact
  kernel ABI need runtime parser tests before making finer claims.

## Ownership and defaults

If the parent ownership decision assigns the feature to Icewine, Icewine can
provide profile text/options close to its generated executables while the host
must still enable the LSM, choose D-Bus mode, supply host/device overrides and
accept reboot/activation consequences. If ownership stays with Nixos, Icewine
should expose only the stable executable/configuration facts needed by a host
module. This report does not decide that open question.

A future interface can be default-on only after enforcement is demonstrated on
desktop and handheld paths. It needs one explicit global opt-out and per-profile
state/override hooks; host extensions should be additive narrow includes, not
replacement policy. Until then, default-on `complain` is telemetry rather than
protection and should be labelled as such. Do not silently fall back when
`services.dbus.apparmor = "required"` is part of the promised boundary.

## Staged validation for a later authorised implementation

1. **Static/evaluation:** evaluate desktop and handheld hosts; parse the exact
   generated profiles against the pinned parser/ABI; verify attachment paths,
   child transitions and that disabled profiles produce no loaded policy. This
   can use a disposable checkout, but any build remains subject to the ticket
   workflow.
2. **Complain-mode inventory:** on separately authorised test hardware or VM,
   boot with the LSM enabled, confirm the kernel feature/ABI, loaded profile,
   process label and system/user D-Bus mediation. Exercise each operation below
   and review complete audit records. Complain mode permits operations, so it
   does not prove denials.
3. **Focused allow/deny tests:** for a helper profile, positively test its
   intended store executables, sockets, files and devices. Negatively test
   reading `~/.ssh`, writing an unrelated home file, opening an Internet socket,
   executing an unlisted shell/tool, sending an unrelated D-Bus method, and
   signaling/ptracing an unrelated peer. Verify the operation actually fails
   and produces the expected profile-labelled denial.
4. **Desktop regression:** log in/out; restart the user service; lock from the
   keybind, logind and suspend path; reject a bad password and accept a good
   one; wake displays; launch native and Flatpak apps and terminal tools; use
   notifications, tray, audio, Bluetooth, network, power, screenshots,
   brightness, hotplug and multi-monitor changes. Confirm no application is
   accidentally left in the shell's profile.
5. **Handheld regression on a real Steam Deck:** start/stop the InputPlumber
   unit, route desktop/overlay/game modes, recover from shell crash, operate the
   radial and keyboard, start/focus/exit Gamescope, launch Steam and a game,
   suspend/resume and dock/undock. A VM cannot establish controller, GPU,
   touch, suspend or docking behaviour.
6. **Enforcement and update:** enforce only the narrow profiles that passed;
   repeat all positive and negative checks after nixpkgs/Icewine updates and
   inspect cache/profile replacement behaviour. Keep an unconfined recovery
   session available during early trials.

None of these runtime results was obtained in this investigation.

## Primary sources

- [Pinned NixOS AppArmor module](https://github.com/NixOS/nixpkgs/blob/20b1ddd1aa5ace70c9468305030aa4f9ef79671b/nixos/modules/security/apparmor.nix)
- [Pinned NixOS D-Bus module](https://github.com/NixOS/nixpkgs/blob/20b1ddd1aa5ace70c9468305030aa4f9ef79671b/nixos/modules/services/system/dbus.nix)
- [Pinned nixpkgs common kernel configuration](https://github.com/NixOS/nixpkgs/blob/20b1ddd1aa5ace70c9468305030aa4f9ef79671b/pkgs/os-specific/linux/kernel/common-config.nix)
- [Linux kernel AppArmor documentation](https://docs.kernel.org/admin-guide/LSM/apparmor.html)
- [AppArmor core policy reference](https://apparmor-documentation-c38b15.gitlab.io/documentation/in-depth/profiles/core-policy-reference/)
- [AppArmor rule basics](https://apparmor-documentation-c38b15.gitlab.io/documentation/getting-started/rules-basics/)
- [AppArmor profile language and execution transitions](https://manpages.ubuntu.com/manpages/resolute/man5/apparmor.d.5.html)
- [Upstream `pam_apparmor` design](https://gitlab.com/apparmor/apparmor/-/blob/master/changehat/pam_apparmor/README)
- [Upstream AppArmor profiles and abstractions](https://gitlab.com/apparmor/apparmor/-/tree/master/profiles)
- [Nixpkgs `apparmor-profiles` package](https://github.com/NixOS/nixpkgs/blob/20b1ddd1aa5ace70c9468305030aa4f9ef79671b/pkgs/by-name/ap/apparmor-profiles/package.nix)
