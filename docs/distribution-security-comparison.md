# Desktop distribution security comparison

Research date: 2026-09-24. This is a documentation and source assessment, not
an installation or runtime test. “Default” means a fresh installation with the
choices stated below; it does not mean every derivative, upgrade, package or
user configuration. Links were read on that date. Release identities are pinned
where the project publishes them. Omarchy's ISO checksum is captured below;
other installation artifacts and installed manifests remain unpinned.

## Scope and evidence limits

| Project | Concrete comparison target | Base / inherited policy |
| --- | --- | --- |
| Omarchy | Official 4.0.4 ISO (SHA-256 `ddeded2758c48318d201dfdac905ecb28f570441883f0c052ea3cd5d05acf92d`, signed release commit `c668141`), full-disk installation, default encryption retained | Arch packages through Omarchy's stable mirror plus Omarchy repository/configuration |
| SteamOS | SteamOS 3.8.16 stable on Valve Steam Deck, Gaming Mode first; Desktop Mode is an alternate session | Valve image and Steam client; not ChimeraOS/HoloISO or other derivatives |
| Mint | Linux Mint 22.3 “Zena” Cinnamon official ISO, ordinary guided desktop install | Ubuntu LTS packages with Mint desktop/repositories |
| Ubuntu | Ubuntu Desktop 26.04.1 LTS official ISO, guided install | Canonical Ubuntu archive and desktop defaults |
| Fedora | Fedora Workstation 44 Live ISO, GNOME default install | Fedora RPM/DNF and Fedora Flatpak infrastructure |
| Bazzite | Stable 44.20260921 KDE Desktop image, fresh installer install; release commit `e1100db` is identified but the installed image digest was not captured | Universal Blue-derived Fedora Atomic image, Fedora and Bazzite policy |

Apart from Omarchy's ISO checksum, exact selected ISO/image digests—especially
Bazzite's installed OCI digest—installer choices, installed manifests and
effective configuration were not captured. This report therefore cannot prove
effective runtime policy. Omarchy's
[4.0.4 release](https://github.com/omacom/omarchy/releases/tag/v4.0.4),
Bazzite's [44.20260921 stable release](https://github.com/ublue-os/bazzite/releases/tag/44.20260921)
and Valve's [SteamOS 3.8.16 announcement](https://steamcommunity.com/ogg/1675200/announcements/detail/698770449667981857)
identify those concrete targets. Fedora's
[official Workstation 44 download](https://fedoraproject.org/workstation/download/)
identifies the release and OpenPGP-verified checksums; Mint's [22.3 release
notes](https://linuxmint.com/rel_zena.php) and [release announcement](https://blog.linuxmint.com/?p=4981)
identify its LTS support. Ubuntu's [download page](https://ubuntu.com/download/desktop)
identifies 26.04.1 as current LTS, and its [lifecycle](https://ubuntu.com/about/release-cycle)
states standard security maintenance to May 2031. SteamOS 3.9 is Preview and
excluded. The attempted bounded source clone was coordinator-interrupted, so it
supplies no evidence.

## What the projects say, and what that supports

| Project | Documented priority | Careful interpretation |
| --- | --- | --- |
| Omarchy | Its manual calls encryption, inbound firewalling and signed-repository measures security features. Its stable channel deliberately uses an Arch mirror one month behind the latest packages. | The strong physical-loss and exposed-service posture is explicit. The delayed stable mirror favours compatibility testing over earliest upstream fixes, so “latest updates” in the security page does not mean latest Arch packages on the default channel. Calling Omarchy broadly “most secure” would be inference. |
| SteamOS | Valve documents recovery, factory reset and rollback for its appliance. | Gaming compatibility and recoverability are demonstrated product priorities. Valve documentation found did **not** establish an LSM, firewall, encryption, Secure Boot, or general-purpose desktop threat model. |
| Mint | Mint documents a familiar desktop installation and optional encryption; 22.3 is supported through 2029. | Convenience/stability is an inference from product scope, not a statement that Mint rejects security. Fresh-default firewall/LSM coverage was not established from Mint primary material. |
| Ubuntu | Ubuntu documents AppArmor as installed/loaded by default and promotes LTS security maintenance. | AppArmor is a platform capability with binary-specific profiles, not universal confinement. Desktop-specific coverage must be inspected per release. |
| Fedora | Fedora's security model documents SELinux as mandatory access control and its Workstation project offers Flatpak plus opt-in third-party sources. | Upstream MAC and a free-software source boundary are explicit. The exact set of domains/processes confined on Workstation was not collected here. |
| Bazzite | Bazzite states SELinux, Secure Boot support, signed images/SBOM/provenance, LUKS and Flatpak sandboxing; it retains previous deployments. | Its documentation explicitly combines gaming/hardware support with an image-based maintenance model. It is not evidence that every game, driver or layered package is confined or rollback-safe. |

## Comparable default matrix

“Unknown” means this investigation found no release-specific primary evidence,
not that the protection is absent. “Available” means installer/feature choice,
not enabled without that choice.

| Area | Omarchy | Valve SteamOS (Deck) | Mint Cinnamon | Ubuntu Desktop | Fedora Workstation | Bazzite KDE Desktop |
| --- | --- | --- | --- | --- | --- | --- |
| Firewall / network exposure | **Enabled:** inbound deny except LocalSend UDP 53317; SSH disabled until its setup enables/rate-limits it. | Unknown from Valve material inspected. | UFW/Gufw is shipped, but fresh enabled state not established. | **UFW initially disabled**; enabling it is an administrator decision. | `firewalld` is the normal Fedora facility; fresh zone/services not established. | No project-specific fresh firewall policy established; inherit Fedora facilities only. |
| Admin, login, lock | Installer creates user; normal sudo password. Time-limited passwordless sudo is an explicit opt-in. | Steam account/device UI; Desktop Mode exists. SteamOS 3.8 adds a Developer Settings control to set the desktop password; its initial password, sudo and lock state were not established. | Normal installer user/admin model; exact sudo/locking config not traced. | Normal installer user/admin model; exact sudo/locking config not traced. | Normal installer user/admin model; exact sudo/locking config not traced. | Installer recommends no root account; user password is used for administration. |
| LSM and effective coverage | No shipped AppArmor/SELinux coverage was established. Arch inheritance alone says nothing about a loaded policy. | Unknown. | Ubuntu inheritance makes AppArmor plausible, but Mint's loaded profiles/coverage were not verified. | **AppArmor loaded by default**; application-specific profiles only. Desktop profile set/coverage unknown. | **SELinux enforcing is Fedora's documented default model**; actual Workstation domain coverage not traced. | **SELinux enabled** per Bazzite; Bazzite-specific policy additions and observed enforcement gaps unknown. |
| Apps and sandbox permissions | Official packages by default; optional AUR/browser installs alter trust boundary. No sandboxed-app default established. | Steam/game stack is host-integrated; no official Flatpak/permission policy found. | APT/deb desktop delivery; Flatpak availability/default remote and permissions not established. | APT/deb plus Snap are normal Ubuntu delivery paths; per-app confinement and user-granted interfaces vary. | RPM plus Fedora Flatpaks; third-party repositories require opt-in. Flatpak sandbox is per-app permission policy. | Bazaar/Flatpak is documented for most apps; Flatpak sandboxing/attestations are project claims. Host layering and containers are mutable exceptions. |
| Kernel / service hardening | Arch package stream through the delayed stable mirror; exact kernel config and systemd hardening not traced. | Image appliance; exact kernel/config/service hardening unknown. | Ubuntu-derived kernel/services; exact Mint deltas unknown. | Ubuntu kernel/service defaults; exact desktop hardening not traced. | SELinux is a material kernel LSM control; exact service hardening unknown. | Latest kernel claim and SELinux; exact systemd/service hardening unknown. |
| Secure Boot, drivers, encryption | **Encryption default/mandatory** except explicit no-encryption path. Installer says disable Secure Boot/TPM. Hardware-specific optional packages exist. | No secure-boot/encryption claim found. Valve documents supported devices and recovery only. | Encryption is an installer option; Secure Boot/driver defaults not established. | Secure Boot support and encryption installer choices are documented; no claim that encryption is forced by default. | Secure Boot and LUKS installer options are upstream facilities; exact selected defaults not captured. | Secure Boot supported after Universal Blue MOK enrollment; **LUKS optional**. Gaming driver/firmware choices are part of image scope. |
| Updates, trust, support | `omarchy-update`; default stable uses official releases and an Arch mirror one month behind upstream, while edge tracks latest Arch packages. AUR is optional. ISO/repo packages have documented OpenPGP key. No OS rollback claim except installer baseline reset. | Valve supports A/B rollback, repair, re-image and factory reset. Update signing/support lifecycle details not established. | Mutable APT system; support/automation/rollback specific to 22.x not traced. | Default Desktop installs apply security updates automatically after 24 hours and normal updates after seven days; signed APT/Snap channels and LTS support are documented. Mutable package/config state means no transactional rollback asserted. | Signed RPM/DNF, release cadence/lifecycle and mutable `/etc`/package state; ordinary DNF upgrade needs recovery media/backups, not an atomic rollback claim. | Desktop images check daily and install during idle periods; stable images are normally published fortnightly and downloaded updates apply on reboot. Signed Cosign images retain a previous bootable deployment. `/etc`, home, Flatpaks and layers remain outside image-only recovery. |
| Documented compatibility tradeoff | Secure Boot must be disabled; SSH/AUR/no-encryption are deliberate opt-outs. The default one-month Arch delay gives Omarchy time to catch incompatibilities but can also delay upstream security fixes; edge trades that qualification window for earlier packages. | Appliance integration/recovery takes priority; extension and security-policy exceptions are not documented here. | Optional encryption and manual firewall decisions leave choices to installer/user; exact tradeoffs need Mint-specific configuration evidence. | AppArmor profiles and Snap interfaces can affect app behavior; driver/proprietary-source choices are optional. | Third-party repos are opt-in; SELinux denials require policy-compatible packaging rather than disabling enforcement. | MOK enrollment and optional encryption are user steps. RPM layering can block updates/rebases; gaming drivers, games and containers expand compatibility surface. |

### Source notes for the matrix

- [Omarchy security manual](https://omarchy.org/manual/security/) documents its
  encryption, UFW rule, SSH, update/repository and signing claims; its
  [installation manual](https://omarchy.org/manual/getting-started/) documents
  encryption-by-default and the Secure Boot/TPM requirement. Its
  [update manual](https://github.com/omacom/omarchy/blob/quattro/manual/30-updates.md)
  establishes that new installations use the stable channel and its one-month-
  delayed Arch mirror; edge receives current Arch packages. These project
  sources support different aspects of policy and must be read together.
- Valve's [recovery and troubleshooting article](https://help.steampowered.com/en/faqs/view/1B71-EDF2-EB6D-2BB3)
  documents previous-image rollback while retaining user data, repair and
  re-image. Valve's [SteamOS 3.8 notes](https://steamcommunity.com/games/1675200/announcements/detail/697641379212298073)
  document the Developer Settings password control. Neither source establishes
  the initial password, sudo, lock or other unverified security cells above.
- Mint's [installation guide](https://linuxmint-installation-guide.readthedocs.io/en/latest/)
  is the relevant primary installer reference. It supports treating encryption
  as an option, but did not yield a source-established fresh firewall or LSM
  result for this report.
- Ubuntu's [AppArmor documentation](https://ubuntu.com/server/docs/how-to/security/apparmor/)
  says it is installed and loaded by default, and its
  [AppArmor overview](https://wiki.ubuntu.com/AppArmor) describes
  binary-specific confinement. Ubuntu documents UFW as
  [initially disabled](https://ubuntu.com/server/docs/how-to/security/firewalls/)
  and [default Desktop update automation](https://documentation.ubuntu.com/security/security-updates/).
  Platform documentation does not substitute for a 26.04 desktop process
  inventory.
- Fedora's [SELinux user documentation](https://docs.fedoraproject.org/en-US/quick-docs/selinux-getting-started/),
  [third-party repository policy](https://fedoraproject.org/wiki/Changes/Third_Party_Software_Mechanism),
  [Flatpak SIG page](https://fedoraproject.org/wiki/SIGs/Flatpak), and
  [DNF upgrade documentation](https://docs.fedoraproject.org/en-US/quick-docs/upgrading-fedora-offline/)
  support the Fedora cells. The last explicitly warns that `/etc` changes and
  third-party repositories need review through upgrades.
- Bazzite's [installation guide](https://docs.bazzite.gg/General/Installation_Guide/install-guide/),
  [project README](https://github.com/ublue-os/bazzite/blob/main/README.md),
  [update guide](https://docs.bazzite.gg/Installing_and_Managing_Software/Updates_Rollbacks_and_Rebasing/updating_guide/),
  [rollback documentation](https://docs.bazzite.gg/Installing_and_Managing_Software/Updates_Rollbacks_and_Rebasing/),
  and [rpm-ostree caveats](https://docs.bazzite.gg/Installing_and_Managing_Software/rpm-ostree/)
  support its specific claims. The website's claims about provenance/SBOMs and
  Flatpak should be checked against the exact image digest when relied on.

## Reading the comparisons correctly

1. A firewall limits unsolicited network access; it does not sandbox a browser,
   game or desktop shell. A service can still be exposed by an explicit rule or
   a permitted interface.
2. AppArmor and SELinux are useful only for processes covered by an enforced
   policy. “AppArmor installed” or “SELinux enabled” is neither a count of
   confined desktop apps nor proof that a particular exploit is contained.
3. Flatpak’s sandbox is app- and permission-specific. A host package, a
   privileged portal grant, a broad filesystem permission, or a game needing
   devices is a separate boundary decision.
4. An immutable/image-based root and an A/B or ostree rollback help recover a
   bootable deployment. They do not remove an attacker’s changes to home,
   external disks, accounts, secrets, firmware, or a mutable layer; they also
   do not isolate a running compromised process.
5. Secure Boot verifies a boot chain subject to enrolled keys. It is distinct
   from disk encryption, and signing claims must be tied to the exact package
   repository or image digest.

## Compatibility and upkeep implications

Omarchy provides explicit encryption and inbound-firewall defaults but makes
hardware/dual-boot compatibility pay the Secure-Boot-disable cost. Its optional
AUR and passwordless-sudo paths are consciously broader trust/privilege paths.
Its stable mirror's qualification month can prevent Arch changes from breaking
Omarchy configuration, but it can also postpone security fixes compared with
Arch upstream; edge removes that delay and its compatibility buffer. SteamOS
has the clearest appliance recovery story in the Valve material reviewed, but
its security defaults should not be extrapolated from its immutable-looking
console experience.

Mint, Ubuntu and Fedora Workstation are mutable package systems. Their normal
strength is broad package/hardware compatibility and conventional repair, with
the administrator carrying update, repository, configuration-drift and backup
responsibility. Ubuntu and Fedora make different MAC choices; neither source
supports comparing the *effective desktop confinement* without an installed
policy inventory. Fedora's opt-in third-party source mechanism is a concrete
compatibility/trust decision.

Bazzite makes a different split: a signed, image-based host with retained
deployments, while Flatpaks, Toolbox/Distrobox, user data, `/etc`, and optional
package layering preserve mutable escape hatches. Its own documentation warns
that layering can create dependency conflicts that pause updates or prevent
rebases. That is a maintenance cost of compatibility, not a reason to call the
base image compromise-proof. Its Deck images additionally have Steam Gaming
Mode and Deck-specific services; the KDE Desktop comparison target above must
not be treated as a policy statement for Deck.

## Lessons to investigate for Icewine/NixOS

No distribution policy is adopted by this report. The small, reusable lessons
are mechanisms to evaluate in NixOS, with their ownership costs:

| Candidate lesson | Native NixOS mechanism | Gap / upkeep cost |
| --- | --- | --- |
| Default-deny inbound exposure with deliberate service exceptions | `networking.firewall` and service modules, with explicit allowed TCP/UDP ports | Must trace every enabled service, LAN discovery need and handheld/Steam path; firewall is not application containment. |
| Make disk encryption and boot trust an explicit install/host decision | NixOS installer configuration, `boot.initrd.luks`, Secure Boot tooling such as `lanzaboote` where suitable | Key enrollment, recovery and real-device boot validation belong to Nixos/host policy, not Icewine. Encryption does not replace backups or running-system isolation. |
| Preserve a known-good generation | NixOS generations and bootloader configuration (`boot.loader.systemd-boot` or GRUB) | Validate rollback on each hardware class and document mutable state/data recovery separately. Generations are not compromise recovery. |
| Prefer maintained app boundaries before custom shell policy | `security.apparmor`, Flatpak, portals and package-specific upstream policy | The companion AppArmor investigation found Icewine's shared Quickshell process too broad for a useful shell/lock boundary. Start, if at all, with narrow fixed helpers and real traces. |
| Keep privilege exceptions visible and revocable | NixOS declarative users, groups, polkit rules and `security.sudo` | Icewine's existing handheld polkit grants and user-selected commands need an authority audit; avoid treating user convenience toggles as a security boundary. |
| Update from pinned reviewed inputs with a recovery route | `flake.lock`, NixOS generation rollback, declarative configuration | Pinning improves reproducibility, not vulnerability response by itself. Someone still owns update cadence, review and hardware regression tests. |

## Evidence gaps that matter before choosing policy

- Collect actual fresh-install `ss -lntup`, firewall rules, user/group/sudo,
  screen-lock and active-LSM/profile inventories for each selected release.
- Pin an ISO/image digest and package manifest before claiming a project
  shipped a particular kernel, driver, service hardening setting or Flatpak
  permission.
- Trace SteamOS's official image configuration only if it is a candidate;
  Valve recovery documentation alone cannot establish its network/LSM/encryption
  posture.
- Review Mint's actual installer and packages before asserting inherited Ubuntu
  AppArmor or UFW policy; derivatives can change defaults.
- For any Icewine mechanism, validate desktop and Steam Deck paths separately.
  A VM cannot establish controller routing, touch, suspend/resume, docking,
  GPU-driver or Secure-Boot behaviour.
