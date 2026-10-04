# Icewine on Bazzite / Fedora Atomic: scope

Research date: 2026-09-24. This is a feasibility report, not a compatibility
claim. Local findings refer to Icewine commit
`da3d511e68c1b8255953ab7986a95b51c2e49295` and the NixOS NixDeck host was
inspected read-only.

## Recommendation

Start with a **desktop-only selectable session on an existing Bazzite Desktop
installation**, delivered as one or more native layered RPMs. Keep Bazzite's KDE
session as a recovery path. This is the smallest useful experiment: rpm-ostree
supports persistent package layering, while an RPM can install the system-level
session, PAM, portal, systemd and policy files that dotfiles cannot. It avoids
owning an operating-system image before Icewine has run on Fedora at all.
Bazzite documents layering as a last resort because dependency conflicts can
pause updates or prevent rebases. Keep this prototype temporary and removable;
if it blocks lifecycle operations, uninstall its layers and reboot (or use
`rpm-ostree reset` to remove every layer) before updating or rebasing.

If the session works and a repeatable personal appliance is wanted, move the
same RPM payload into a **personal derived Bazzite Desktop image** made with the
recommended Universal Blue image template. An image makes the package closure,
update channel and rollback unit reproducible; it also adds CI, registry and
signing ownership. Do not start with Bazzite Deck: its Steam Gaming Mode and
InputPlumber ownership overlap Icewine's nested Gamescope and controller-routing
design. Treat Steam Deck support as a second, real-hardware phase.

“Spin” should therefore mean one of these explicit products:

| Product | Retains | Icewine owns | Suitable now? |
| --- | --- | --- | --- |
| Layered session on `bazzite:stable` | Bazzite Desktop image, KDE recovery session, kernel/drivers, gaming stack and upstream update channel | Compatible RPMs, Icewine session/config, PAM/portal/policy integration | **Yes: bounded, temporary personal prototype** |
| Personal image derived from `bazzite:stable` | Same Bazzite parent and update semantics | Above, plus build workflow, image pin, registry, signatures and update qualification | After session proof |
| Image derived from `bazzite-deck:stable` | Bazzite Gaming Mode, Deck services, Steam/Gamescope/InputPlumber stack | A coexistence design rather than a simple session | No: separate handheld phase |
| Image derived from Fedora Sway Atomic 44 | Official, relatively small wlroots-style Atomic desktop base | The full gaming/Deck stack and all Icewine RPM integration | Alternative only when minimal non-gaming Fedora matters more than Bazzite |

Fedora 44 currently lists Silverblue, Kinoite, Sway, Budgie and COSMIC Atomic;
there is no official Hyprland Atomic edition in that list. Bazzite currently
offers KDE/GNOME Desktop images and KDE/GNOME Deck images, with Gaming Mode as
an additional session on Deck images. These are source facts, not evidence that
Icewine runs on any of them.

## Why copying the configuration is insufficient

Icewine's source is ordinary QML, JavaScript, Lua and shell, but its installation
is a NixOS module with native user services (`flake.nix`,
`modules/default.nix`, `modules/home.nix`). Nix currently generates or wires all of the following:

- a Hyprland Lua tree with a generated `Theme.lua`, optional Deck modules and
  host overlays (`modules/home.nix:15-38`);
- a generated Quickshell palette and authentication setting, desktop/handheld
  entry point, adapters and modules (`modules/home.nix:39-58`);
- the `icewine.service` user unit and Flatpak icon-cache path/service units
  (`modules/home.nix:61-96`);
- wrapper executables with closed runtime paths, plus the screenshot,
  brightness and monitor-probe helpers (`modules/default.nix:10-30`,
  `modules/home.nix:5-13`);
- Hyprland/UWSM enablement, the `icewine` PAM service, polkit, PipeWire, I²C,
  UPower, power profiles, GVfs, fonts and packages
  (`modules/default.nix:102-125`);
- optional idle, battery, Yazi and shell presets (`modules/desktop.nix`,
  `modules/{gtk,shell}.nix`), including editable GTK/Kitty/Bash defaults and
  generated Fastfetch/Starship theme files; and
- handheld InputPlumber profiles, policy, user services, patched Squeekboard and
  patched Gamescope (`modules/handheld.nix`).

Icewine's NixOS adapter cannot simply be run on Fedora: generated services
embed store/profile paths. Concrete FHS leaks include
`/run/current-system/sw/bin` in Icewine's service PATH and
`/run/current-system/sw/share/inputplumber/profiles/default.yaml` in controller
restore. The shell prompt also compares NixOS generation kernels. Installing Nix
on Bazzite would still not create Fedora PAM, polkit, SELinux, display-manager or
system-service integration.

The native port should package the existing assets, materialise the generated
Hyprland/Quickshell/palette files and produce native command wrappers. The GTK,
Kitty and shell presets can be separate optional packages; they are not needed
to prove the desktop session. Replace Nix store/runtime paths with RPM/FHS paths
and install an `icewine-uwsm.desktop` entry that starts Hyprland through UWSM.
UWSM is a real dependency: Icewine launches applications with `uwsm app`, stops
the session with `uwsm stop`, installs `uwsm/env`, and starts its services at
`graphical-session.target`. Upstream documents that model and display-manager
entry format.

## Runtime and packaging contract

| Area | Verified local requirement | Fedora/Bazzite facility or gap |
| --- | --- | --- |
| Compositor | Hyprland Lua config and runtime APIs (`hl.config`, events, Lua callbacks and `hyprctl eval`); 0.55 is the earliest plausible generation because upstream introduced Lua configuration there, but Icewine's exact API floor is unmeasured | Fedora's package pages checked on the research date expose old F41/F42 builds, not a current F44 result. This is an evidence gap, not proof that no usable RPM exists. Select and pin a current compatible RPM source or own the RPM. |
| Shell | Quickshell with Hyprland, PAM, Wayland session-lock, PipeWire, MPRIS, UPower, Bluetooth, networking, notifications and global-shortcut QML modules | Fedora 44 packages a 0.2.1 snapshot and lists these modules. API compatibility with Icewine still needs a load/start test. |
| Session | UWSM, `graphical-session.target`, `uwsm app`, `uwsm stop`, and an installed Wayland session entry | Upstream supports Hyprland and display managers. No current official Fedora package page was found; record the chosen RPM source and version rather than silently enabling an unpinned COPR. |
| Portals | `xdg-desktop-portal`, a Hyprland screencast backend, and a GTK file/open-uri fallback; select them for the Icewine desktop name | Fedora packages the portal frontend. The official Hyprland backend page checked only showed F42-era builds, so version/source and screen-share behaviour remain gates. Do not inherit KDE/GNOME portal selection accidentally. |
| Authentication/lock | Quickshell `PamContext` uses PAM service `icewine`; `WlSessionLock` and logind lock/sleep signals are part of the design (`quickshell/modules/SessionControl.qml`) | RPM must install and review `/etc/pam.d/icewine`; test wrong/right passwords, lock-before-sleep, resume and loss/restart of Quickshell. Authentication-disabled mode is a deliberate handheld option, not a desktop default. |
| Privilege/policy | A graphical polkit agent; desktop brightness needs backlight access and external DDC needs I²C; power actions use logind/systemd | Reuse a Bazzite-provided polkit agent if it is session-scoped and compatible, otherwise package the current agent. Define udev/group/polkit access explicitly; do not copy NixOS groups by assumption. |
| SELinux | User services execute packaged helpers; handheld mode calls system InputPlumber D-Bus methods and loads profiles from `/etc/inputplumber` | Keep enforcing mode. Exercise the installed paths and inspect AVC denials; add the narrowest labelled policy only when a denial demonstrates a need. No current evidence establishes that custom policy is required. |
| Desktop tools | PipeWire/WirePlumber, NetworkManager, BlueZ, UPower, power profiles, GVfs, notification sound, screenshots, brightness and optional terminal tools | Most are normal Fedora facilities. Map Nix names to RPMs and make optional UI actions conditional where packages such as `bluetui`, `impala`, `wiremix`, `batsignal`, `hyprshutdown` or Yazi plugins are unavailable. |
| Applications | Host-selected terminal/browser/editor/file manager/Steam commands; Flatpak icons are monitored in system and user export paths | Preserve host choice. Prefer Flatpak for GUI applications; compositor, portal, PAM, helpers and session services belong on the host, not in Toolbx/Distrobox. |

Icewine's flake pins nixpkgs revision
`20b1ddd1aa5ace70c9468305030aa4f9ef79671b`, but it declares no portable
per-package version floor. Record an RPM lock matrix from the first working
deployment rather than treating that Nix revision as a Fedora specification.
Two known hard constraints are Hyprland's Lua API and the local Gamescope patch:
`patches/gamescope/README.md` targets Gamescope 3.16.28 and says its declaration
hunk also applies to 3.16.29. A Fedora/Bazzite package at the same version is not
automatically equivalent; its source and patch stack must be checked.

## Desktop and handheld are separate products

The shared desktop consists of Hyprland/UWSM, Quickshell, portals, PAM locking,
polkit, PipeWire, desktop services, helpers and selected applications. Validate
that first on one AMD/Intel desktop or laptop. NVIDIA, touch, suspend/resume,
docking and HTPC/controller operation remain untested coverage, even if the
session starts.

Handheld mode additionally assumes all of these Icewine-specific behaviours:

- exactly one InputPlumber composite named `Steam Deck`;
- InputPlumber CLI and D-Bus interfaces for `manage-all`, target creation,
  profile loading and intercept modes 0/3;
- Icewine profiles under `/etc/inputplumber/profiles`, a user service that
  changes global device routing, and four passwordless polkit actions;
- rear buttons mapped to F13-F17, with R5 controlling the radial and L5 the
  patched Squeekboard overlay;
- Steam launched in a **nested** Gamescope using focused-monitor dimensions,
  while Icewine owns the outer Hyprland session; and
- three Gamescope patches: Icewine's keyboard-focus patch everywhere and two
  upstream touch patches in handheld mode.

Bazzite Deck already enables its own InputPlumber service and Gaming Mode
session and ships its own Gamescope/Steam integration. Its current image source
also modifies the Steam Deck InputPlumber device and enables Deck-specific
services. Inference: installing Icewine handheld mode unchanged would create two
policy owners and two competing session models. Before any Deck image work,
choose one design:

1. **Icewine session only:** Bazzite supplies kernel, firmware and packages;
   Icewine owns controller routing and nested Gamescope. Disable only confirmed
   conflicting Bazzite behaviours in the derived image.
2. **Coexistence:** retain Bazzite Gaming Mode unchanged and offer Icewine as a
   desktop-mode session. Icewine handheld routing must be disabled or redesigned
   outside its session.

Neither is validated. A VM cannot establish controller routing, touchscreen
coordinates, suspend/resume, audio, performance controls or docking. Those need
a Steam Deck with recovery access and checks for routing restoration after
logout, crash, InputPlumber restart and update.

## Updates, rollback, persistence and release ownership

A layered-session prototype follows the existing Bazzite image channel;
rpm-ostree reapplies layered RPMs to new deployments and retains the prior
deployment for rollback. User configuration and data remain outside the image.
This persistence is also its main operational risk: Bazzite warns that a
dependency conflict can pause updates, block rebases and lengthen upgrades until
the layer is removed. Local RPM files do not receive automatic package updates.
Pin the external RPM repository, keep the package set small, and test an update
before removing the prior deployment. If an update or rebase is blocked, use
`rpm-ostree uninstall <package>` and reboot; `rpm-ostree reset` is the documented
fallback for removing all layers. Rollback covers the deployment, not every
mutable file in `/etc` or the user's home, so the package must avoid one-way
migrations. A successful prototype should graduate to a derived image rather
than retain a large permanent layer set.

A derived image should consume a pinned Bazzite parent digest, install signed
RPMs during the image build, run static/session checks in CI, publish to an OCI
registry, sign each image, retain a documented previous digest, and regularly
merge parent updates. Bazzite documents the Universal Blue image template as its
preferred custom-image method. Bazzite Desktop updates automatically; Deck
updates are manual by default, and both apply on reboot. Previous deployments
can be selected at boot or rolled back. The derived-image maintainer owns timely
rebuilds when Bazzite, Fedora, Hyprland, Quickshell, Gamescope or InputPlumber
changes.

Do not promise a distributable image yet. Icewine has no selected project
licence. Choose one and audit notices/source obligations for copied patches,
themes and every bundled RPM before publishing. Bazzite's repository is
Apache-2.0, but that does not relicense Steam, codecs, drivers or other payloads.
“Fedora Spin” denotes an approved Fedora deliverable; a third-party build is a
derived image/remix and must follow Fedora trademark guidance. Registry terms,
Bazzite naming/branding and redistribution of non-free components also require
human review.

## Work plan and effort

Qualitative effort assumes one experienced maintainer and excludes upstream
packaging delays.

1. **Decide scope (hours):** choose AMD/Intel Bazzite Desktop, layered RPM
   prototype, retained KDE session, authentication on, and no handheld mode.
2. **Resolve the package closure (days, high uncertainty):** select exact F44
   RPM sources/versions for Hyprland 0.55+, portal backend, UWSM, Quickshell and
   small tools; reject mixed repositories with unresolved ABI ownership.
3. **Create native Icewine RPM payload (several days):** install generated/static
   configuration, wrappers, user units, PAM/portal/session files and declared
   dependencies. Remove NixOS paths and keep host application choices external.
4. **Static and disposable-system validation (days):** lint RPM contents,
   scripts, desktop/PAM/polkit/SELinux data and run existing JS/Lua/shell checks;
   then install in a disposable Fedora/Bazzite VM only under separate approval.
   Check login/logout, UWSM targets, portals, lock/PAM, Flatpaks, audio,
   notifications, power controls and rollback. A VM does not validate hardware.
5. **One desktop/laptop pilot (days):** validate displays, input, suspend/resume,
   screen sharing, brightness, updates and rollback. Record the exact image
   digest and RPM matrix.
6. **Optional personal image (days plus ongoing maintenance):** move the proven
   RPMs to an image-template repository; add CI, registry, signing and update
   policy. Keep KDE until recovery through TTY/rollback is proven.
7. **Optional Steam Deck track (weeks, high uncertainty):** choose the ownership
   model above, compare Bazzite and Icewine patch/profile versions, then test on
   real hardware. HTPC and non-Deck handhelds are later, separate coverage.

Required human decisions before implementation:

- personal prototype or maintained/distributable image;
- initial GPU/hardware (recommend AMD/Intel desktop/laptop only);
- KDE Bazzite Desktop versus GNOME, and whether the fallback session stays;
- acceptable RPM source policy: Fedora only, selected COPRs, or self-built;
- whether future Deck work uses Icewine-owned nested Gamescope or coexists with
  Bazzite Gaming Mode; and
- project licence, image name, registry/signing owner and update service level
  before redistribution.

## Primary sources

- [Bazzite image variants and Gaming Mode](https://docs.bazzite.gg/General/Installation_Guide/install-guide/)
- [Bazzite custom-image guidance](https://docs.bazzite.gg/Advanced/creating_custom_image/)
- [Bazzite updates, rollback and rebasing](https://docs.bazzite.gg/Installing_and_Managing_Software/Updates_Rollbacks_and_Rebasing/)
- [Bazzite package-layering caveats and removal](https://docs.bazzite.gg/Installing_and_Managing_Software/rpm-ostree/)
- [Bazzite image source (packages and Deck services)](https://github.com/ublue-os/bazzite/blob/main/Containerfile)
- [Fedora Atomic Desktop variants](https://fedoraproject.org/atomic-desktops/)
- [Fedora Silverblue image/package model](https://fedoraproject.org/atomic-desktops/silverblue/)
- [Fedora Quickshell package](https://packages.fedoraproject.org/pkgs/quickshell/quickshell/fedora-44.html)
- [Fedora Hyprland package overview](https://packages.fedoraproject.org/pkgs/hyprland/hyprland/)
- [Fedora Hyprland portal package overview](https://packages.fedoraproject.org/pkgs/xdg-desktop-portal-hyprland/)
- [Hyprland Lua configuration](https://wiki.hypr.land/configuring/core/config-options/)
- [Hyprland releases](https://github.com/hyprwm/Hyprland/releases)
- [UWSM session and display-manager integration](https://github.com/Vladimir-csp/uwsm)
- [Universal Blue image template](https://github.com/ublue-os/image-template)
- [Fedora Remix and trademark distinction](https://fedoraproject.org/wiki/Remix)
- [Bazzite repository licence](https://github.com/ublue-os/bazzite)

Sources were read on the research date. Package and image versions are moving
inputs; re-check them when implementation begins.
