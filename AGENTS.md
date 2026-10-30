# Icewine

Read `/mnt/nas/Projects/AGENTS.md` first. Icewine is an experimental personal
desktop environment built on Hyprland and Quickshell, developed NixOS-first for
desktops, laptops, handhelds and HTPCs.

Icewine owns shared desktop interface and behaviour. Host users, applications,
login policy, networking, storage and persistence belong in Nixos.

Main areas: `quickshell/` for the shell UI, `hyprland/` and `session/` for session
behaviour, `manager/` for the Rust manager, `modules/` and `packaging/` for
integration, and `tests/` for developer checks. Read relevant callers and tests
before changing a component; reuse the established pattern.

The optional handheld interface includes a controller radial, on-screen
keyboard and nested Gamescope integration. Controls currently target Steam
Deck. HTPC support is intended scope, not separately validated hardware.
Controller, touch, suspend/resume and docking need real-device checks.

Use existing focused tests directly with installed tools. Read the relevant
`/mnt/nas/Projects/WORKFLOW.md` sections before ticket work or Nix/build operations. Functional
checks do not replace native visual comparison when implementing an accepted
UI reference. README ownership remains with the human.
