#!/usr/bin/env python3
"""Focused regression checks for the shipped theme command."""

import os
import errno
import importlib.machinery
import io
import json
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import tomllib
import types
from pathlib import Path
from unittest import mock


script = Path(sys.argv[1]).resolve()
dispatcher = Path(sys.argv[2]).resolve()
assets = Path(sys.argv[3]).resolve()


def contrast(first, second):
    def luminance(color):
        channels = (int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))
        linear = (v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
                  for v in channels)
        return sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def css_hex(css, name):
    match = re.search(rf"(?m)^  {re.escape(name)}: #([0-9a-f]{{6}});$", css)
    assert match, name
    return match.group(1)


def named_color(css, name):
    match = re.search(rf"(?m)^@define-color {re.escape(name)}\s+#([0-9a-f]{{6}});$", css)
    assert match, name
    return match.group(1)


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    config = root / ".config"
    state = root / "state"
    wallpaper = root / "data/icewine/wallpapers/selection.img"
    wallpaper.parent.mkdir(parents=True)
    wallpaper.write_bytes(b"wallpaper is independent")
    defaults = root / "defaults"
    for relative, contents in {
        "config/hypr/hyprland.lua": b"default hypr\n",
        "config/hypr/modules/Baseline.lua": b"default baseline\n",
        "config/uwsm/env": b"default env\n",
        "config/quickshell/shell.qml": b"default shell\n",
        "config/quickshell/theme/Palette.qml": (script.parent.parent / "quickshell/theme/Palette.qml").read_bytes(),
        "config/quickshell/theme/qmldir": (script.parent.parent / "quickshell/theme/qmldir").read_bytes(),
        "config/quickshell/modules/Thing.qml": b"default module\n",
        "config/quickshell/adapters/Adapter.qml": b"default adapter\n",
        "config/btop/btop.conf": b"default btop\n",
        "config/user-dirs.locale": b"default locale\n",
        "config/nvim/init.lua": b"default nvim\n",
        "config/kitty/kitty.conf": (
            b"# Icewine's editable Kitty entry point.\n"
            b"include ../icewine/current/kitty-base.conf\n"
            b"include ../icewine/current/kitty.conf\n"
            b"include host.conf\n"
        ),
        "config/kitty/host.conf": b"",
        "config/icewine/shell/bashrc": b"# default bash\n",
        "config/icewine/shell/profile": b"# default profile\n",
        "config/icewine/shell/bash_profile": b"# default bash profile\n",
        "data/wallpapers/default.jpg": b"default wallpaper",
        "data/wallpapers/current_blurr.jpg": b"default blur",
    }.items():
        path = defaults / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    (defaults / "home").mkdir()
    for name in ("bashrc", "profile", "bash_profile"):
        (defaults / "home" / f".{name}").symlink_to(f"icewine/shell/{name}")
    env = dict(os.environ, XDG_CONFIG_HOME=str(config), XDG_STATE_HOME=str(state),
               ICEWINE_THEME_ASSETS=str(assets), ICEWINE_THEME_POLICY="",
               ICEWINE_DEFAULT_FILES=str(defaults),
               HOME=str(root))
    env["XDG_DATA_HOME"] = str(root / "data")
    sddm_file = root / "sddm/theme.ini"
    env["ICEWINE_SDDM_THEME_FILE"] = str(sddm_file)
    env.pop("DBUS_SESSION_BUS_ADDRESS", None)
    env.pop("WAYLAND_DISPLAY", None)
    env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)
    fake_bin = root / "bin"
    fake_bin.mkdir()
    (fake_bin / "ya").write_text("#!/bin/sh\nexit 0\n")
    (fake_bin / "ya").chmod(0o755)
    (fake_bin / "systemctl").write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$ICEWINE_TEST_SYSTEMCTL_LOG"\n')
    (fake_bin / "systemctl").chmod(0o755)
    env["PATH"] = f"{fake_bin}:{os.environ['PATH']}"
    env["ICEWINE_TEST_SYSTEMCTL_LOG"] = str(root / "systemctl.log")
    env["XDG_RUNTIME_DIR"] = str(root / "runtime")
    (root / "runtime/systemd").mkdir(parents=True)
    (root / "runtime/systemd/private").touch()

    def run(*arguments, policy="", skip="", nix_epoch=None, git_enabled="true"):
        command_env = dict(env, ICEWINE_THEME_POLICY=policy,
                           ICEWINE_THEME_SKIP=skip,
                           ICEWINE_THEME_GIT_ENABLE=git_enabled)
        command_env.pop("ICEWINE_NIXPKGS_LAST_MODIFIED", None)
        if nix_epoch is not None:
            command_env["ICEWINE_NIXPKGS_LAST_MODIFIED"] = nix_epoch
        return subprocess.run([sys.executable, str(script), *arguments],
                              env=command_env,
                              text=True, capture_output=True)

    edited = config / "gtk-3.0/settings.ini"
    edited.parent.mkdir(parents=True)
    edited.write_text("user edit\n")
    legacy = config / "quickshell/theme/Palette.qml"
    legacy.parent.mkdir(parents=True)
    legacy_target = "/nix/store/" + "a" * 32 + "-home-manager-files/.config/quickshell/theme/Palette.qml"
    legacy.symlink_to(legacy_target)
    unrelated = config / "gtk-3.0/gtk.css"
    unrelated.symlink_to("/nix/store/" + "b" * 32 + "-user-css")
    unknown_path = config / "gtk-4.0/gtk.css"
    unknown_path.parent.mkdir(parents=True)
    unknown_target = "/nix/store/" + "d" * 32 + "-home-manager-files/.config/gtk-4.0/gtk.css"
    unknown_path.symlink_to(unknown_target)
    kitty_entry = config / "kitty/kitty.conf"
    kitty_entry.parent.mkdir(parents=True, exist_ok=True)
    kitty_legacy_target = "/nix/store/" + "c" * 32 + "-home-manager-files/.config/kitty/kitty.conf"
    kitty_entry.symlink_to(kitty_legacy_target)
    legacy_bash = root / ".bashrc"
    legacy_bash_target = "/nix/store/" + "e" * 32 + "-home-manager-files/.bashrc"
    legacy_bash.symlink_to(legacy_bash_target)
    (root / ".profile").write_text("custom login profile\n")
    launchers = root / "data/applications"
    launchers.mkdir(parents=True)
    old_steam = launchers / "steam.desktop"
    old_steam_target = "/nix/store/" + "f" * 32 + "-home-manager-files/data/applications/steam.desktop"
    old_steam.symlink_to(old_steam_target)
    custom_launcher = launchers / "steam-gamescope.desktop"
    custom_launcher.write_text("user Steam launcher\n")
    unknown_steam = launchers / "com.valvesoftware.Steam.desktop"
    unknown_steam.symlink_to("/nix/store/" + "a" * 32 + "-host-launcher")
    units = config / "systemd/user"
    wants = units / "graphical-session.target.wants"
    requires = units / "other.target.requires"
    wants.mkdir(parents=True)
    requires.mkdir()
    unit_links = [units / "icewine.service", wants / "hypridle.service",
                  requires / "icewine-inputplumber-hyprland.service",
                  units / "icewine-refresh-flatpak-icons.path"]
    for path in unit_links:
        path.symlink_to("/nix/store/" + "1" * 32 + "-home-manager-files/"
                        + path.relative_to(root).as_posix())
    edited_unit = units / "hyprpolkitagent.service"
    edited_unit.write_text("user Polkit unit\n")
    unknown_unit = units / "icewine-keyboard.service"
    unknown_unit.symlink_to("/nix/store/" + "2" * 32 + "-custom-unit")
    unrelated_unit = units / "other.service"
    unrelated_unit.symlink_to("/nix/store/" + "3" * 32
                             + "-home-manager-files/.config/systemd/user/other.service")

    result = run("init")
    assert result.returncode == 0, result.stderr
    assert "Theme: catppuccin-mocha · Transparency: high" in result.stdout
    assert sddm_file.read_text() == "[General]\ntheme=catppuccin-mocha\n"
    assert sddm_file.stat().st_mode & 0o777 == 0o644
    assert edited.read_text() == "user edit\n"
    assert not legacy.is_symlink() and "property color primary" in legacy.read_text()
    assert unrelated.is_symlink() and os.readlink(unrelated) == "/nix/store/" + "b" * 32 + "-user-css"
    assert unknown_path.is_symlink() and os.readlink(unknown_path) == unknown_target
    assert "conflict: preserved unrecognized symlink" in result.stderr
    # Existing Icewine GTK4 links must migrate from the shared CSS to GTK4 CSS.
    old_gtk4_css = (config / "icewine/current/gtk.css").read_text()
    unknown_path.unlink()
    unknown_path.symlink_to(config / "icewine/current/gtk.css")
    result = run("init", "gtk")
    assert result.returncode == 0, result.stderr
    assert os.readlink(unknown_path) == str(config / "icewine/current/gtk4.css")
    migrated_gtk4 = list((state / "icewine").glob("migration-*/gtk-4.0/gtk.css"))
    assert len(migrated_gtk4) == 1 and migrated_gtk4[0].read_text() == old_gtk4_css
    migration = list((state / "icewine").glob("defaults-migration-*/config/quickshell/theme/Palette.qml"))
    assert len(migration) == 1 and os.readlink(migration[0]) == legacy_target
    assert (config / "icewine/current").is_symlink()
    nvim_theme = config / "icewine/current/nvim-theme.lua"
    assert 'local theme = "catppuccin-mocha"' in nvim_theme.read_text()
    fastfetch = json.loads((config / "icewine/current/fastfetch.jsonc").read_text())
    assert not any(item.get("key", "").endswith("Nixpkgs") for item in fastfetch["modules"] if isinstance(item, dict))
    assert tomllib.loads((config / "icewine/current/starship.toml").read_text())["git_branch"]["disabled"] is False
    assert (config / "yazi/keymap.toml").is_symlink()
    assert (config / "hypr/hyprland.lua").read_text() == "default hypr\n"
    assert not (config / "hypr/modules/Theme.lua").exists()
    assert (config / "quickshell/modules/Thing.qml").read_text() == "default module\n"
    assert (root / "data/wallpapers/default.jpg").read_bytes() == b"default wallpaper"
    assert not (config / "quickshell/modules/Thing.qml").is_symlink()
    assert (config / "nvim/init.lua").read_text() == "default nvim\n"
    kitty_includes = [line for line in kitty_entry.read_text().splitlines() if line.startswith("include ")]
    assert kitty_includes == [
        "include ../icewine/current/kitty-base.conf",
        "include ../icewine/current/kitty.conf",
        "include host.conf",
    ]
    kitty_migration = list((state / "icewine").glob("defaults-migration-*/config/kitty/kitty.conf"))
    assert len(kitty_migration) == 1 and os.readlink(kitty_migration[0]) == kitty_legacy_target
    assert os.readlink(legacy_bash) == str(config / "icewine/shell/bashrc")
    assert (root / ".profile").read_text() == "custom login profile\n"
    bash_migration = list((state / "icewine").glob("defaults-migration-*/home/.bashrc"))
    assert len(bash_migration) == 1 and os.readlink(bash_migration[0]) == legacy_bash_target
    assert old_steam.is_symlink() and os.readlink(old_steam) == old_steam_target
    assert custom_launcher.read_text() == "user Steam launcher\n"
    assert unknown_steam.is_symlink()
    steam_migration = list((state / "icewine").glob("defaults-migration-*/data/applications/steam.desktop"))
    assert not steam_migration  # Unreadable legacy content cannot establish Icewine ownership.
    for path in unit_links:
        assert not path.exists() and not path.is_symlink()
        backups = list((state / "icewine").glob("defaults-migration-*/config/"
                                               + path.relative_to(config).as_posix()))
        assert len(backups) == 1 and backups[0].is_symlink()
    assert edited_unit.read_text() == "user Polkit unit\n"
    assert unknown_unit.is_symlink() and unrelated_unit.is_symlink()
    assert (root / "systemctl.log").read_text() == "--user daemon-reload\n"

    (config / "quickshell/modules/Thing.qml").write_text("user module edit\n")
    (root / "data/wallpapers/default.jpg").write_bytes(b"user wallpaper")
    backups_before = set((state / "icewine").glob("defaults-migration-*"))
    assert run("init").returncode == 0
    assert set((state / "icewine").glob("defaults-migration-*")) == backups_before
    assert (config / "quickshell/modules/Thing.qml").read_text() == "user module edit\n"
    assert (root / "data/wallpapers/default.jpg").read_bytes() == b"user wallpaper"
    assert custom_launcher.read_text() == "user Steam launcher\n"
    assert unknown_steam.is_symlink()
    assert (root / "systemctl.log").read_text() == "--user daemon-reload\n"
    (config / "nvim/init.lua").write_text("user nvim edit\n")
    result = run("reset", "nvim")
    assert result.returncode == 0, result.stderr
    assert (config / "nvim/init.lua").read_text() == "default nvim\n"
    assert any(path.read_text() == "user nvim edit\n" for path in
               (state / "icewine").glob("defaults-reset-*/config/nvim/init.lua"))
    assert (root / "data/wallpapers/default.jpg").read_bytes() == b"user wallpaper"
    kitty_entry.write_text("user Kitty entry edit\n")
    assert run("init").returncode == 0
    assert kitty_entry.read_text() == "user Kitty entry edit\n"
    result = run("reset", "kitty")
    assert result.returncode == 0, result.stderr
    assert "include host.conf\n" in kitty_entry.read_text()
    assert any(path.read_text() == "user Kitty entry edit\n" for path in
               (state / "icewine").glob("defaults-reset-*/config/kitty/kitty.conf"))
    (config / "icewine/shell/bashrc").write_text("user Bash edit\n")
    assert run("init", "bash").returncode == 0
    assert (config / "icewine/shell/bashrc").read_text() == "user Bash edit\n"
    result = run("reset", "bash")
    assert result.returncode == 0, result.stderr
    assert (config / "icewine/shell/bashrc").read_text() == "# default bash\n"
    assert (root / ".profile").read_text() == "# default profile\n"
    assert any(path.read_text() == "user Bash edit\n" for path in
               (state / "icewine").glob("defaults-reset-*/config/icewine/shell/bashrc"))
    assert any(path.read_text() == "custom login profile\n" for path in
               (state / "icewine").glob("defaults-reset-*/home/.profile"))

    fastfetch_path = config / "fastfetch/config.jsonc"
    fastfetch_path.unlink()
    result = run("init", "fastfetch")
    assert result.returncode == 0 and fastfetch_path.is_symlink(), result.stderr
    assert edited.read_text() == "user edit\n"
    assert (config / "quickshell/modules/Thing.qml").read_text() == "user module edit\n"
    assert run("init", "unknown").returncode != 0

    result = run("apply", nix_epoch="1790821943", git_enabled="false")
    assert result.returncode == 0, result.stderr
    fastfetch = json.loads((config / "icewine/current/fastfetch.jsonc").read_text())
    assert any(item.get("key", "").endswith("Nixpkgs") for item in fastfetch["modules"] if isinstance(item, dict))
    assert tomllib.loads((config / "icewine/current/starship.toml").read_text())["git_branch"]["disabled"] is True
    assert run("apply").returncode == 0

    result = run("theme", "missing")
    assert result.returncode != 0
    assert not (state / "icewine/theme").exists()
    assert json.loads((config / "icewine/current/palette.json").read_text())["primary"] == "89b4fa"

    result = run("theme", "dracula")
    assert result.returncode == 0, result.stderr
    assert (state / "icewine/theme").read_text() == "dracula\n"
    assert 'local theme = "dracula"' in nvim_theme.read_text()
    assert json.loads((config / "icewine/current/palette.json").read_text())["primary"] == "bd93f9"
    assert unrelated.is_symlink() and os.readlink(unrelated) == "/nix/store/" + "b" * 32 + "-user-css"
    assert edited.read_text() == "user edit\n"
    assert "Effective: dracula" in run("theme").stdout

    yazi = config / "yazi/theme.toml"
    yazi.unlink()
    yazi.write_text("edited yazi theme\n")
    result = run("reset", "yazi")
    assert result.returncode == 0, result.stderr
    assert (state / "icewine/theme").read_text() == "dracula\n"
    assert "#bd93f9" in yazi.read_text()
    assert edited.read_text() == "user edit\n"
    assert any(path.read_text() == "edited yazi theme\n"
               for path in (state / "icewine").glob("reset-*/yazi/theme.toml"))

    result = run("theme", "tokyo-night", policy="dracula")
    assert result.returncode == 0, result.stderr
    assert "Nix policy overrides CLI selection" in result.stdout
    assert 'local theme = "dracula"' in nvim_theme.read_text()
    assert (state / "icewine/theme").read_text() == "tokyo-night\n"
    assert json.loads((config / "icewine/current/palette.json").read_text())["primary"] == "bd93f9"

    (state / "icewine/theme").write_text("broken ID\n")
    result = run("init", policy="dracula")
    assert result.returncode == 0, result.stderr
    assert json.loads((config / "icewine/current/palette.json").read_text())["primary"] == "bd93f9"
    (state / "icewine/theme").write_text("tokyo-night\n")

    result = run("reset")
    assert result.returncode == 0, result.stderr
    assert not (state / "icewine/theme").exists()
    assert "gtk-theme-name=Icewine-catppuccin-mocha" in edited.read_text()
    assert wallpaper.read_bytes() == b"wallpaper is independent"
    assert (config / "quickshell/modules/Thing.qml").read_text() == "default module\n"
    assert (root / "data/wallpapers/default.jpg").read_bytes() == b"default wallpaper"
    assert any(path.read_text() == "user module edit\n" for path in
               (state / "icewine").glob("defaults-reset-*/config/quickshell/modules/Thing.qml"))
    assert any(path.read_bytes() == b"user wallpaper" for path in
               (state / "icewine").glob("defaults-reset-*/data/wallpapers/default.jpg"))
    backups = list((state / "icewine").glob("reset-*/gtk-3.0/settings.ini"))
    assert len(backups) == 1 and backups[0].read_text() == "user edit\n"

    host_paths = ["fastfetch/config.jsonc", "starship.toml", "yazi/theme.toml", "yazi/keymap.toml"]
    for relative in host_paths:
        path = config / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
        path.write_text(f"host override: {relative}\n")
    for command_args in [("theme", "dracula"), ("reset",)]:
        result = run(*command_args, skip=":".join(host_paths))
        assert result.returncode == 0, result.stderr
        for relative in host_paths:
            assert (config / relative).read_text() == f"host override: {relative}\n"

    command = fake_bin / "icewine-theme"
    command.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
    command.chmod(0o755)
    routed = subprocess.run(["bash", str(dispatcher), "theme", "dracula"],
                            env=dict(env, PATH=f"{fake_bin}:{os.environ['PATH']}"),
                            text=True, capture_output=True)
    assert routed.returncode == 0 and routed.stdout == "theme\ndracula\n", routed.stderr

    # Exercise migration of a live Home Manager target and its content backup.
    module = types.ModuleType("icewine_theme")
    module.__file__ = str(script)
    importlib.machinery.SourceFileLoader(module.__name__, str(script)).exec_module(module)
    # Force both publishers past the existence check before the real rename.
    concurrent_config = root / "concurrent-config"
    barrier = threading.Barrier(2)
    rename = Path.rename
    def simultaneous_rename(path, destination):
        if path.name.startswith(".render-"):
            barrier.wait(timeout=5)
        return rename(path, destination)
    with mock.patch.object(Path, "rename", simultaneous_rename), ThreadPoolExecutor(max_workers=2) as publishers:
        jobs = [publishers.submit(module.publish, concurrent_config, {"palette.json": "{}\n"}) for _ in range(2)]
        for job in jobs:
            job.result(timeout=10)
    assert (concurrent_config / "icewine/current/palette.json").read_text() == "{}\n"
    with mock.patch.object(Path, "rename", side_effect=PermissionError(errno.EACCES, "denied")):
        try:
            module.publish(concurrent_config, {"palette.json": "changed\n"})
        except PermissionError:
            pass
        else:
            raise AssertionError("publication must propagate non-collision errors")
    # User-data masks override exported launchers, survive unchanged init, and
    # retire on opt-out without removing edited files or unrelated symlinks.
    mask_root = root / "mask-home"
    mask_defaults = root / "mask-defaults"
    for directory in (mask_root, mask_defaults / "config", mask_defaults / "data"):
        directory.mkdir(parents=True)
    mask_config, mask_data, mask_state = (mask_root / name for name in ("config", "data", "state"))
    mask_store = root / "mask-store"
    mask_store.mkdir()
    first_mask = mask_store / ("a" * 32 + "-icewine-steam-mask.desktop")
    first_mask.write_text("[Desktop Entry]\nHidden=true\n")
    second_mask = mask_store / ("b" * 32 + "-icewine-steam-mask.desktop")
    second_mask.write_text(first_mask.read_text())
    with mock.patch.object(module, "STORE_DIR", mask_store), mock.patch.dict(os.environ, {
        "HOME": str(mask_root), "XDG_CONFIG_HOME": str(mask_config),
        "ICEWINE_STEAM_MASK_FILE": str(first_mask),
    }):
        def reconcile_masks():
            module.install_defaults(str(mask_defaults), mask_config, mask_data, mask_state, False, None)
        reconcile_masks()
        mask_paths = [mask_data / "applications" / name for name in
                      ("steam.desktop", "com.valvesoftware.Steam.desktop")]
        assert all(path.is_symlink() and os.readlink(path) == str(first_mask) for path in mask_paths)
        reconcile_masks()
        assert not list(mask_state.glob("defaults-migration-*"))
        os.environ["ICEWINE_STEAM_MASK_FILE"] = str(second_mask)
        reconcile_masks()
        assert all(os.readlink(path) == str(second_mask) for path in mask_paths)
        os.environ["ICEWINE_STEAM_MASK_FILE"] = ""
        reconcile_masks()
        assert all(not path.exists() and not path.is_symlink() for path in mask_paths)
        legacy_mask = mask_store / ("c" * 32 + "-home-manager-files") / "data/applications/steam.desktop"
        legacy_mask.parent.mkdir(parents=True)
        legacy_mask.write_text("[Desktop Entry]\nType=Application\nName=Steam\nNoDisplay=true\nHidden=true\n")
        legacy_launcher = legacy_mask.with_name("steam-gamescope.desktop")
        legacy_launcher.write_text(
            "[Desktop Entry]\nVersion=1.0\nType=Application\nName=Steam (Gamescope)\n"
            "Comment=Launch Steam inside monitor-aware Gamescope\nIcon=steam\n"
            "Categories=Game;\nTerminal=false\nExec=/nix/store/" + "d" * 32
            + "-quickshell-0.3.1/bin/qs ipc call gameLauncher launchSteamGamescope\n")
        launcher_path = mask_data / "applications/steam-gamescope.desktop"
        launcher_path.symlink_to(legacy_launcher)
        mask_paths[0].symlink_to(legacy_mask)
        os.environ["ICEWINE_STEAM_MASK_FILE"] = str(first_mask)
        reconcile_masks()
        assert os.readlink(mask_paths[0]) == str(first_mask)
        assert not launcher_path.exists() and not launcher_path.is_symlink()
        os.environ["ICEWINE_STEAM_MASK_FILE"] = ""
        reconcile_masks()
        legacy_mask.write_text("[Desktop Entry]\nName=Custom Steam\nExec=custom-launcher\n")
        legacy_launcher.write_text(legacy_launcher.read_text() + "X-Custom=true\n")
        launcher_path.symlink_to(legacy_launcher)
        mask_paths[0].symlink_to(legacy_mask)
        mask_paths[1].symlink_to(first_mask.parent / "custom-mask")
        os.environ["ICEWINE_STEAM_MASK_FILE"] = str(first_mask)
        reconcile_masks()
        os.environ["ICEWINE_STEAM_MASK_FILE"] = ""
        reconcile_masks()
        assert os.readlink(mask_paths[0]) == str(legacy_mask)
        assert mask_paths[0].read_text() == "[Desktop Entry]\nName=Custom Steam\nExec=custom-launcher\n"
        assert os.readlink(mask_paths[1]) == str(first_mask.parent / "custom-mask")
        assert launcher_path.is_symlink() and "X-Custom=true" in launcher_path.read_text()
    mounted = config / "user-dirs.locale"
    mounted.write_text("user locale edit\n")
    replace = os.replace
    def busy_for_file(source, destination):
        if destination == mounted:
            raise OSError(errno.EBUSY, "simulated persisted file mount")
        return replace(source, destination)
    with mock.patch.object(module.os, "replace", side_effect=busy_for_file):
        module.install_defaults(str(defaults), config, root / "data", state / "icewine", True, "user-dirs")
    assert mounted.read_text() == "default locale\n"
    assert any(path.read_text() == "user locale edit\n" for path in
               (state / "icewine").glob("defaults-reset-*/config/user-dirs.locale"))
    legacy_home = root / "migration-home"
    old_file = root / "store" / ("c" * 32 + "-home-manager-files") / ".config/quickshell/theme/Palette.qml"
    old_file.parent.mkdir(parents=True)
    old_file.write_text("old managed palette\n")
    legacy_config = legacy_home / ".config"
    old_link = legacy_config / "quickshell/theme/Palette.qml"
    old_link.parent.mkdir(parents=True)
    old_link.symlink_to(old_file)
    old_modules = root / "store" / ("e" * 32 + "-modules")
    old_modules.mkdir()
    (old_modules / "Thing.qml").write_text("old managed module\n")
    module_link = legacy_config / "quickshell/modules"
    module_link.symlink_to(old_modules)
    unknown_adapters = root / "outside-adapters"
    unknown_adapters.mkdir()
    adapters_link = legacy_config / "quickshell/adapters"
    adapters_link.symlink_to(unknown_adapters)
    old_init = root / "store" / ("f" * 32 + "-init.lua")
    old_init.write_text("old generated nvim\n")
    init_link = legacy_config / "nvim/init.lua"
    init_link.parent.mkdir(parents=True)
    init_link.symlink_to(old_init)
    pure_mime = """[Default Applications]
application/pdf=firefox.desktop
application/xhtml+xml=firefox.desktop
text/html=firefox.desktop
x-scheme-handler/http=firefox.desktop
x-scheme-handler/https=firefox.desktop
"""
    mime_config = legacy_config / "mimeapps.list"
    old_mime_config = root / "store" / ("1" * 32 + "-home-manager-files") / ".config/mimeapps.list"
    old_mime_config.parent.mkdir(parents=True)
    old_mime_config.write_text(pure_mime)
    mime_config.symlink_to(old_mime_config)
    mime_data = legacy_home / "data/applications/mimeapps.list"
    old_mime_data = root / "store" / ("2" * 32 + "-home-manager-files") / "data/applications/mimeapps.list"
    old_mime_data.parent.mkdir(parents=True)
    old_mime_data.write_text(pure_mime + "image/png=imv.desktop\n")
    mime_data.parent.mkdir(parents=True)
    mime_data.symlink_to(old_mime_data)
    old_home = os.environ.get("HOME")
    try:
        os.environ["HOME"] = str(legacy_home)
        module.STORE_DIR = root / "store"
        module.publish(legacy_config, module.render_theme(assets, assets / "themes/tokyo-night.json"))
        module.install_defaults(str(defaults), legacy_config, legacy_home / "data",
                                legacy_home / ".local/state/icewine", False, None)
        assert not mime_config.exists() and not mime_config.is_symlink()
        assert mime_data.is_symlink() and mime_data.read_text().endswith("image/png=imv.desktop\n")
        backups = list((legacy_home / ".local/state/icewine").glob(
            "defaults-migration-*/config/mimeapps.list"))
        assert len(backups) == 1 and backups[0].read_text() == pure_mime
        mime_config.write_text("[Default Applications]\napplication/pdf=org.gnome.Evince.desktop\n")
        old_mime_data_pure = root / "store" / ("3" * 32 + "-home-manager-files") / "data/applications/mimeapps.list"
        old_mime_data_pure.parent.mkdir(parents=True)
        old_mime_data_pure.write_text(pure_mime)
        mime_data.unlink()
        mime_data.symlink_to(old_mime_data_pure)
        module.install_defaults(str(defaults), legacy_config, legacy_home / "data",
                                legacy_home / ".local/state/icewine", False, None)
        assert mime_config.read_text().endswith("org.gnome.Evince.desktop\n")
        assert not mime_data.exists() and not mime_data.is_symlink()
        backups = list((legacy_home / ".local/state/icewine").glob(
            "defaults-migration-*/data/applications/mimeapps.list"))
        assert len(backups) == 1 and backups[0].read_text() == pure_mime
        module.install_links(legacy_config, legacy_home / ".local/state/icewine", False)
    finally:
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home
    assert "property color primary" in old_link.read_text()
    saved = list((legacy_home / ".local/state/icewine").glob("defaults-migration-*/config/quickshell/theme/Palette.qml"))
    assert len(saved) == 1 and saved[0].read_text() == "old managed palette\n"
    assert module_link.is_dir() and not module_link.is_symlink()
    assert (module_link / "Thing.qml").read_text() == "default module\n"
    assert adapters_link.is_symlink() and not (adapters_link / "Adapter.qml").exists()
    saved_modules = list((legacy_home / ".local/state/icewine").glob(
        "defaults-migration-*/config/quickshell/modules/Thing.qml"))
    assert len(saved_modules) == 1 and saved_modules[0].read_text() == "old managed module\n"
    assert init_link.read_text() == "default nvim\n" and not init_link.is_symlink()
    saved_init = list((legacy_home / ".local/state/icewine").glob(
        "defaults-migration-*/config/nvim/init.lua"))
    assert len(saved_init) == 1 and saved_init[0].read_text() == "old generated nvim\n"

    # Every shipped palette renders app-native files, including light mode.
    kitty_entry.write_text("user Kitty theme edit\n")
    for theme_id, background, appearance in [
        ("tokyo-night", "13131a", "dark"), ("dracula", "1d1e27", "dark"),
        ("nord", "282e38", "dark"), ("gruvbox-light", "cfc19d", "light"),
        ("gruvbox-dark", "232323", "dark"),
        ("catppuccin-latte", "cacdd2", "light"),
        ("catppuccin-frappe", "242735", "dark"),
        ("catppuccin-macchiato", "1a1c2a", "dark"),
        ("catppuccin-mocha", "151521", "dark"),
    ]:
        result = run("theme", theme_id)
        assert result.returncode == 0, result.stderr
        assert sddm_file.read_text() == f"[General]\ntheme={theme_id}\n"
        current = config / "icewine/current"
        assert f"background #{background}\n" in (current / "kitty.conf").read_text()
        assert kitty_entry.read_text() == "user Kitty theme edit\n"
        assert f'vim.opt.background = "{appearance}"' in nvim_theme.read_text()
        assert f'dark: "{appearance}"' in (current / "Palette.qml").read_text()
        assert f"gtk-application-prefer-dark-theme={int(appearance == 'dark')}" in (current / "gtk-settings.ini").read_text()
        assert "gtk-theme-name=Adwaita\n" in (current / "gtk4-settings.ini").read_text()
        palette = json.loads((assets / "themes" / f"{theme_id}.json").read_text())
        assert not (current / "pywalfox.json").exists()
        assert not (current / "browser.css").exists()
        gtk4 = (current / "gtk4.css").read_text()
        for role, color in (("window-bg", "background"), ("view-bg", "backgroundDark"),
                            ("headerbar-bg", "backgroundDark"), ("sidebar-bg", "surface"),
                            ("card-bg", "surface"), ("accent-bg", "highlight")):
            assert f"--{role}-color: #{palette[color]};" in gtk4
        for role in ("accent", "success", "warning", "error", "destructive"):
            bg = css_hex(gtk4, f"--{role}-bg-color")
            fg = css_hex(gtk4, f"--{role}-fg-color")
            assert contrast(bg, fg) >= 4.5, (theme_id, role, bg, fg)
        gtk3 = (current / "gtk3-theme.css").read_text()
        accent_fg = css_hex(gtk4, "--accent-fg-color")
        assert f"@define-color palette_accent_fg       #{accent_fg};" in gtk3
        assert "@define-color theme_selected_fg_color   @palette_accent_fg;" in gtk3
        assert "@define-color accent_fg_color           @palette_accent_fg;" in gtk3
        assert not re.search(r"(?m)^  color: @palette_bg_dark;$", gtk3)
        for background_role, foreground_role in (
            ("palette_bg_highlight", "palette_fg"),
            ("palette_fg_gutter", "palette_button_hover_fg"),
            ("palette_bg_dark", "palette_headerbar_fg"),
            ("palette_bg_highlight", "palette_headerbar_hover_fg"),
        ):
            bg = named_color(gtk3, background_role)
            fg = named_color(gtk3, foreground_role)
            assert contrast(bg, fg) >= 4.5, (theme_id, background_role, foreground_role, bg, fg)
        assert "button:hover {\n  background-color: @palette_fg_gutter;\n  color: @palette_button_hover_fg;" in gtk3
        for selector, foreground in (
            ("headerbar, .titlebar, menubar, toolbar", "palette_headerbar_fg"),
            ("headerbar button, .titlebar button, toolbar button", "palette_headerbar_fg"),
            ("headerbar button:hover, .titlebar button:hover, toolbar button:hover",
             "palette_headerbar_hover_fg"),
        ):
            assert re.search(re.escape(selector) + r" \{[^}]*color: @" + foreground + ";", gtk3)
        assert "Tokyonight-Dark" not in (current / "gtk4-settings.ini").read_text()
        for filename in ("starship.toml", "yazi-theme.toml", "yazi-keymap.toml"):
            tomllib.loads((current / filename).read_text())
    assert run("theme", "nord", policy="gruvbox-light").returncode == 0
    assert sddm_file.read_text() == "[General]\ntheme=gruvbox-light\n"
    assert 'local theme = "gruvbox-light"' in nvim_theme.read_text()
    assert run("theme", "not-installed").returncode != 0
    assert sddm_file.read_text() == "[General]\ntheme=gruvbox-light\n"
    blocked = root / "not-a-directory"
    blocked.write_text("keep me\n")
    env["ICEWINE_SDDM_THEME_FILE"] = str(blocked / "theme.ini")
    result = run("apply")
    assert result.returncode == 0 and "Pending: SDDM colours will not update" in result.stderr
    assert blocked.read_text() == "keep me\n"
    env["ICEWINE_SDDM_THEME_FILE"] = str(sddm_file)

    # Opacity is independent of theme selection and survives reapplication.
    saved_theme = (state / "icewine/theme").read_text()
    for level, kitty_opacity, inactive_opacity in [
        ("off", "1.00", "1.00"), ("low", "0.80", "0.75"),
        ("med", "0.60", "0.55"), ("high", "0.40", "0.40"),
    ]:
        result = run("transparency", level)
        assert result.returncode == 0, result.stderr
        assert (state / "icewine/theme").read_text() == saved_theme
        assert (state / "icewine/transparency").read_text() == level + "\n"
        for command_args in [("init",), ("apply",)]:
            assert run(*command_args).returncode == 0
            assert f"background_opacity {kitty_opacity}\n" in (current / "kitty.conf").read_text()
            assert f"inactive_opacity = {inactive_opacity}" in (current / "Theme.lua").read_text()
    assert run("theme", "dracula").returncode == 0
    assert run("reset", "yazi").returncode == 0
    assert "Transparency: high" in run("transparency").stdout
    previous = os.readlink(current)
    assert run("transparency", "invalid").returncode != 0
    assert os.readlink(current) == previous
    assert (state / "icewine/transparency").read_text() == "high\n"
    (state / "icewine/transparency").write_text("broken\n")
    assert run("init").returncode != 0
    assert os.readlink(current) == previous
    assert run("transparency", "off").returncode == 0
    assert run("reset").returncode == 0
    assert not (state / "icewine/transparency").exists()
    assert "background_opacity 0.40\n" in (current / "kitty.conf").read_text()
    assert "inactive_opacity = 0.40" in (current / "Theme.lua").read_text()
    routed = subprocess.run(["bash", str(dispatcher), "transparency", "low"],
                            env=dict(env, PATH=f"{fake_bin}:{os.environ['PATH']}"),
                            text=True, capture_output=True)
    assert routed.returncode == 0 and routed.stdout == "transparency\nlow\n", routed.stderr

    # Dispatch to reachable consumers; no real application receives a signal.
    runtime = root / "runtime"
    command_log = root / "consumer-commands"
    for name in ("hyprctl", "qs", "ya"):
        command = fake_bin / name
        command.write_text("#!/bin/sh\n"
                           'printf "%s %s\\n" "$(basename "$0")" "$*" >> "$ICEWINE_TEST_COMMANDS"\n'
                           'if [ "$(basename "$0")" = qs ]; then echo "applied: tokyo-night"; fi\n')
        command.chmod(0o755)
    env.update(PATH=f"{fake_bin}:{os.environ['PATH']}",
               WAYLAND_DISPLAY="wayland-test", HYPRLAND_INSTANCE_SIGNATURE="test",
               XDG_RUNTIME_DIR=str(runtime), ICEWINE_TEST_COMMANDS=str(command_log))
    yazi_command = (fake_bin / "ya").read_text()
    (fake_bin / "ya").write_text(yazi_command + "exit 2\n")
    for app, expected in (("bash", ""), ("hypr", "hyprctl reload\n"),
                          ("quickshell", "qs ipc call theme refresh\n"),
                          ("kitty", ""), ("nvim", ""),
                          ("yazi", "ya emit-to 0 app:theme\n")):
        command_log.write_text("")
        result = run("reset", app)
        assert result.returncode == (1 if app == "yazi" else 0), (app, result.stderr)
        assert command_log.read_text() == expected, app
    (fake_bin / "ya").write_text(yazi_command)
    command_log.write_text("")
    result = run("reset")
    assert result.returncode == 0, result.stderr
    assert all(command in command_log.read_text() for command in
               ("hyprctl reload", "ya emit-to 0 app:theme", "qs ipc call theme refresh"))
    command_log.write_text("")
    result = run("apply")
    assert result.returncode == 0, result.stderr
    commands = command_log.read_text()
    for expected in ("hyprctl reload", "ya emit-to 0 app:theme",
                     "qs ipc call theme refresh"):
        assert expected in commands, commands
    assert "kitten @" not in commands and "nvim --server" not in commands
    assert result.stdout == "Theme: catppuccin-mocha · Transparency: high\n"
    (fake_bin / "ya").write_text(
        yazi_command + "echo 'Cannot emit command: Permission denied (os error 13)' >&2\nexit 2\n")
    command_log.write_text("")
    result = run("apply")
    assert result.returncode == 1 and "Failed: Yazi theme reload" in result.stderr
    assert "Permission denied (os error 13)" in result.stderr
    assert "qs ipc call theme refresh" in command_log.read_text()
    (fake_bin / "ya").write_text(
        yazi_command + "echo 'Cannot emit command: Connection refused (os error 111)' >&2\nexit 1\n")
    for args in (("transparency", "high"), ("reset", "yazi")):
        command_log.write_text("")
        result = run(*args)
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines()[-1] == "Theme: catppuccin-mocha · Transparency: high"
        if args[0] == "transparency":
            assert len(result.stdout.splitlines()) == 1
        assert "ya emit-to 0 app:theme" in command_log.read_text()
    (fake_bin / "ya").write_text(yazi_command)
    command_log.write_text("")
    qs_command = (fake_bin / "qs").read_text()
    (fake_bin / "qs").write_text(qs_command + "exit 2\n")
    result = run("apply")
    assert result.returncode == 1 and "Failed: Quickshell palette refresh" in result.stderr
    assert "ya emit-to 0 app:theme" in command_log.read_text()
    (fake_bin / "qs").write_text(qs_command)
    command_log.write_text("")
    (fake_bin / "hyprctl").write_text("#!/missing-interpreter\n")
    result = run("apply")
    assert result.returncode == 1 and "Failed: Hyprland reload" in result.stderr
    commands = command_log.read_text()
    assert "ya emit-to 0 app:theme" in commands and "qs ipc call theme refresh" in commands
    command_log.write_text("")
    (fake_bin / "hyprctl").write_text("#!/bin/sh\nexec sleep 20\n")
    (fake_bin / "hyprctl").chmod(0o755)
    result = run("apply")
    assert result.returncode == 1 and "Failed: Hyprland reload" in result.stderr
    commands = command_log.read_text()
    assert "ya emit-to 0 app:theme" in commands and "qs ipc call theme refresh" in commands

    # Synthetic proc entries exercise scoped pidfd dispatch and exit handling.
    proc = root / "proc"
    proc.mkdir()
    def process(pid, name, arguments, *, config_home=str(config), runtime_dir=str(runtime)):
        entry = proc / str(pid)
        entry.mkdir()
        (entry / "comm").write_text(name + "\n")
        (entry / "cmdline").write_bytes(b"\0".join(arg.encode() for arg in arguments) + b"\0")
        (entry / "environ").write_bytes(
            f"HOME={root}\0XDG_CONFIG_HOME={config_home}\0XDG_RUNTIME_DIR={runtime_dir}\0".encode())
    process(123, "kitty", ["kitty"])
    process(124, "kitty", ["kitty"], runtime_dir="/other-session")
    process(125, "kitty", ["kitty", "--config", "/other/kitty.conf"])
    process(126, "nvim", ["nvim", "notes.md"])
    process(127, "nvim", ["nvim", "-uNONE"])
    delivered = []
    def send(fd, number):
        delivered.append(number)
    with mock.patch.object(module, "PROC", proc), \
         mock.patch.object(module.os, "pidfd_open", lambda pid: os.open(os.devnull, os.O_RDONLY), create=True), \
         mock.patch.object(module.signal, "pidfd_send_signal", send, create=True):
        assert module.signal_reload("kitty", config, str(runtime)) is False
        assert module.signal_reload("nvim", config, str(runtime)) is False
        assert delivered == [signal.SIGUSR1, signal.SIGUSR1]
        with mock.patch.object(module.signal, "pidfd_send_signal", mock.Mock(side_effect=ProcessLookupError)):
            assert module.signal_reload("kitty", config, str(runtime)) is False
        with mock.patch.object(module.signal, "pidfd_send_signal", mock.Mock(side_effect=PermissionError)):
            assert module.signal_reload("kitty", config, str(runtime)) is True
    with mock.patch.object(module, "PROC", proc), \
         mock.patch.object(module.os, "getuid", return_value=os.getuid() + 1), \
         mock.patch.object(module.os, "pidfd_open", side_effect=AssertionError("other user"), create=True):
        assert module.signal_reload("kitty", config, str(runtime)) is False

# Updates exercise the shared installer directly, without live applications.
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    config, data, state = (root / name for name in ("config", "data", "state"))
    defaults = root / "defaults"
    for name in ("config", "data", "home"):
        (defaults / name).mkdir(parents=True)
    state.mkdir()
    initial = {
        "config/hypr/hyprland.lua": b"hypr v1\n",
        "config/quickshell/modules/Thing.qml": b"shell v1\n",
        "config/quickshell/config/Settings.qml": b"settings v1\n",
        "config/kitty/host.conf": b"",
        "config/uwsm/env": b"env v1\n",
        "config/btop/btop.conf": b"btop v1\n",
        "config/icewine/shell/profile": b"profile v1\n",
        "data/wallpapers/default.jpg": b"image v1",
    }
    for name, contents in initial.items():
        source = defaults / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(contents)
    (defaults / "home/.profile").symlink_to("icewine/shell/profile")
    config.mkdir()
    untracked = config / "uwsm/env"
    untracked.parent.mkdir()
    untracked.write_bytes(initial["config/uwsm/env"])  # Equality is not proof of ownership.
    wallpaper = data / "icewine/wallpapers/selection.img"
    wallpaper.parent.mkdir(parents=True)
    wallpaper.write_bytes(b"user selection")
    for name, value in {"theme": "dracula\n", "transparency": "low\n", "autofullscreen": "on\n"}.items():
        (state / name).write_text(value)
    update_env = dict(HOME=str(root), XDG_CONFIG_HOME=str(config), XDG_DATA_HOME=str(data),
                      XDG_STATE_HOME=str(root / "xdg-state"), ICEWINE_STEAM_MASK_FILE="")
    with mock.patch.dict(os.environ, update_env):
        def update(app=None, replace=False):
            module.install_defaults(str(defaults), config, data, state, replace, app)

        update()
        record = state / "default-files.json"
        assert "uwsm/env" not in json.loads(record.read_text())["config"]["files"]
        before = record.read_bytes()
        # A user-substituted known-looking legacy parent is not an untracked migration.
        original_modules = config / "quickshell/modules"
        user_modules = root / "store" / ("e" * 32 + "-modules")
        user_modules.parent.mkdir()
        original_modules.rename(user_modules)
        original_modules.symlink_to(user_modules)
        (defaults / "config/quickshell/modules/Thing.qml").write_text("shell v2\n")
        with mock.patch.object(module, "STORE_DIR", root / "store"), \
             mock.patch.object(module.sys, "stderr", new_callable=io.StringIO) as errors:
            update("quickshell")
        assert "preserved substituted parent" in errors.getvalue()
        assert original_modules.is_symlink() and (user_modules / "Thing.qml").read_text() == "shell v1\n"
        assert record.read_bytes() == before
        original_modules.unlink()
        user_modules.rename(original_modules)
        (defaults / "config/quickshell/modules/Thing.qml").write_text("shell v1\n")
        update()
        assert record.read_bytes() == before
        assert not list(state.glob("defaults-update-*"))
        user_settings = config / "quickshell/config/Settings.qml"
        user_settings.write_text("user settings\n")
        host = config / "kitty/host.conf"
        host.write_text("user Kitty overrides\n")
        v2 = {name: contents.replace(b"v1", b"v2") for name, contents in initial.items()}
        for name, contents in v2.items():
            (defaults / name).write_bytes(contents)
        (defaults / "home/.profile").unlink()
        (defaults / "home/.profile").symlink_to("icewine/shell/profile-v2")
        update("quickshell")
        assert (config / "quickshell/modules/Thing.qml").read_bytes() == v2["config/quickshell/modules/Thing.qml"]
        assert (config / "hypr/hyprland.lua").read_bytes() == initial["config/hypr/hyprland.lua"]
        update()
        assert (config / "hypr/hyprland.lua").read_bytes() == v2["config/hypr/hyprland.lua"]
        assert (data / "wallpapers/default.jpg").read_bytes() == v2["data/wallpapers/default.jpg"]
        assert os.readlink(root / ".profile") == str(config / "icewine/shell/profile-v2")
        assert untracked.read_bytes() == initial["config/uwsm/env"]
        assert user_settings.read_text() == "user settings\n" and host.read_text() == "user Kitty overrides\n"
        assert any(path.read_bytes() == initial["config/hypr/hyprland.lua"]
                   for path in state.glob("defaults-update-*/config/hypr/hyprland.lua"))
        # Rolling back reinstalls prior bytes without resetting independent choices.
        for name, contents in initial.items():
            (defaults / name).write_bytes(contents)
        update()
        assert (config / "hypr/hyprland.lua").read_bytes() == initial["config/hypr/hyprland.lua"]
        assert wallpaper.read_bytes() == b"user selection"
        assert (state / "theme").read_text() == "dracula\n"
        assert (state / "transparency").read_text() == "low\n"
        assert (state / "autofullscreen").read_text() == "on\n"
        # Recorded link edits are user-owned even if they resemble an old managed link.
        profile = root / ".profile"
        profile.unlink()
        profile.symlink_to(config / "icewine/shell/profile")
        update("bash")
        assert os.readlink(profile) == str(config / "icewine/shell/profile")
        profile.unlink()
        profile.symlink_to(config / "icewine/shell/profile-v2")
        # Removed/disabled unchanged files retire; edits and neighbouring user files stay.
        extra = config / "quickshell/modules/User.qml"
        extra.write_text("user extension\n")
        for name in ("config/quickshell/modules/Thing.qml", "config/quickshell/config/Settings.qml",
                     "config/btop/btop.conf", "data/wallpapers/default.jpg", "home/.profile"):
            (defaults / name).unlink()
        update("hypr")
        assert (config / "quickshell/modules/Thing.qml").exists()
        update()
        assert not (config / "quickshell/modules/Thing.qml").exists()
        assert not (data / "wallpapers/default.jpg").exists()
        assert not (root / ".profile").is_symlink()
        assert user_settings.read_text() == "user settings\n" and extra.read_text() == "user extension\n"
        assert any(path.read_bytes() == initial["data/wallpapers/default.jpg"]
                   for path in state.glob("defaults-update-*/data/wallpapers/default.jpg"))
        # Conflicting replacements never acquire ownership, including dangling parents.
        for name in ("directory", "unknown", "parent/entry"):
            source = defaults / "config" / name
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("new shipped file\n")
        (config / "directory").mkdir()
        (config / "directory/user").write_text("keep directory contents\n")
        (config / "unknown").symlink_to(root / "missing-user-target")
        (config / "parent").symlink_to(root / "missing-parent")
        update()
        assert (config / "directory/user").read_text() == "keep directory contents\n"
        assert (config / "unknown").is_symlink() and (config / "parent").is_symlink()
        assert not (root / "missing-parent").exists()
        # Explicit reset backs up an untracked regular file and establishes future ownership.
        update("uwsm", replace=True)
        assert any(path.read_bytes() == initial["config/uwsm/env"]
                   for path in state.glob("defaults-reset-*/config/uwsm/env"))
        (defaults / "config/uwsm/env").write_text("env v3\n")
        update("uwsm")
        assert untracked.read_text() == "env v3\n"
        # Failures before replacement preserve both live bytes and the ownership record.
        before = record.read_bytes()
        (defaults / "config/uwsm/env").write_text("env v4\n")
        with mock.patch.object(module.shutil, "copy2", side_effect=PermissionError("backup denied")):
            try:
                update("uwsm")
                raise AssertionError("backup failure must stop replacement")
            except PermissionError:
                pass
        assert untracked.read_text() == "env v3\n" and record.read_bytes() == before
        with mock.patch.object(module.os, "replace", side_effect=PermissionError("replace denied")):
            try:
                update("uwsm")
                raise AssertionError("replace failure must propagate")
            except PermissionError:
                pass
        assert untracked.read_text() == "env v3\n" and record.read_bytes() == before
        # A backup with different bytes must not authorize replacement.
        def incomplete_backup(source, destination, *args, **kwargs):
            Path(destination).write_bytes(b"incomplete backup")
        with mock.patch.object(module.shutil, "copy2", side_effect=incomplete_backup):
            try:
                update("uwsm")
                raise AssertionError("incomplete backup accepted")
            except ValueError:
                pass
        assert untracked.read_text() == "env v3\n" and record.read_bytes() == before
        # Edits made after backup or while preparing replacement survive refresh/retirement.
        copy2 = module.shutil.copy2
        def edit_after_backup(source, destination, *args, **kwargs):
            result = copy2(source, destination, *args, **kwargs)
            if source == untracked:
                untracked.write_text("concurrent user edit\n")
            return result
        for retiring in (False, True):
            if retiring:
                (defaults / "config/uwsm/env").unlink()
            with mock.patch.object(module.shutil, "copy2", side_effect=edit_after_backup), \
                 mock.patch.object(module.sys, "stderr", new_callable=io.StringIO) as errors:
                update("uwsm")
            assert "changed during installation" in errors.getvalue()
            assert untracked.read_text() == "concurrent user edit\n" and record.read_bytes() == before
            untracked.write_text("env v3\n")
            (defaults / "config/uwsm/env").write_text("env v4\n")
        copyfileobj = module.shutil.copyfileobj
        def edit_during_preparation(source, destination, *args, **kwargs):
            result = copyfileobj(source, destination, *args, **kwargs)
            if source.name == str(defaults / "config/uwsm/env"):
                untracked.write_text("late user edit\n")
            return result
        with mock.patch.object(module.shutil, "copyfileobj", side_effect=edit_during_preparation):
            update("uwsm")
        assert untracked.read_text() == "late user edit\n" and record.read_bytes() == before
        untracked.write_text("env v3\n")
        # A parent switched during backup is preserved even when its file bytes match.
        parent = config / "uwsm"
        moved_parent = root / "late-user-parent"
        def switch_parent_after_backup(source, destination, *args, **kwargs):
            result = copy2(source, destination, *args, **kwargs)
            if source == untracked:
                parent.rename(moved_parent)
                parent.symlink_to(moved_parent)
            return result
        with mock.patch.object(module.shutil, "copy2", side_effect=switch_parent_after_backup):
            update("uwsm")
        assert parent.is_symlink() and (moved_parent / "env").read_text() == "env v3\n"
        assert record.read_bytes() == before
        parent.unlink()
        moved_parent.rename(parent)
        # An interrupted manifest write leaves new bytes conservatively unowned.
        atomic = module.atomic_text
        def deny_record(path, *args, **kwargs):
            if path == record:
                raise PermissionError("ownership write denied")
            return atomic(path, *args, **kwargs)
        with mock.patch.object(module, "atomic_text", side_effect=deny_record):
            try:
                update("uwsm")
                raise AssertionError("ownership write failure must propagate")
            except PermissionError:
                pass
        assert untracked.read_text() == "env v4\n" and record.read_bytes() == before
        (defaults / "config/uwsm/env").write_text("env v5\n")
        update("uwsm")
        assert untracked.read_text() == "env v4\n"  # No stale-hash takeover on retry.
        untracked.write_text("env v3\n")
        (defaults / "config/uwsm/env").write_text("env v4\n")
        # Edited former managed paths may become dangling links or directories.
        untracked.unlink()
        untracked.symlink_to(root / "user-dangling")
        update("uwsm")
        assert os.readlink(untracked) == str(root / "user-dangling")
        untracked.unlink()
        untracked.mkdir()
        (untracked / "user").write_text("keep\n")
        update("uwsm")
        assert (untracked / "user").read_text() == "keep\n"
        (untracked / "user").unlink()
        untracked.rmdir()
        untracked.write_text("env v3\n")
        # Removed children behind a substituted parent link are never followed.
        original_uwsm = config / "uwsm"
        moved_uwsm = root / "user-uwsm"
        original_uwsm.rename(moved_uwsm)
        original_uwsm.symlink_to(moved_uwsm)
        (defaults / "config/uwsm/env").unlink()
        update("uwsm")
        assert (moved_uwsm / "env").read_text() == "env v3\n"
        original_uwsm.unlink()
        moved_uwsm.rename(original_uwsm)
        (defaults / "config/uwsm/env").write_text("env v4\n")
        # Corrupt/untrusted records cannot authorize deletion or replacement.
        for contents in ('[]', '{"config":{"root":"x","files":{"../escape":"link:x"}}}'):
            record.write_text(contents)
            try:
                update("uwsm")
                raise AssertionError("invalid record accepted")
            except ValueError:
                pass
            assert untracked.read_text() == "env v3\n"
        record.unlink()
        record.symlink_to(root / "missing-record")
        try:
            update("uwsm")
            raise AssertionError("symlink record accepted")
        except ValueError:
            pass
        record.unlink()
        record.write_bytes(before)
        # Changing XDG roots never cleans up the previous location.
        old_config = config
        config = root / "new-config"
        update("uwsm")
        assert (config / "uwsm/env").read_text() == "env v4\n"
        assert (old_config / "uwsm/env").read_text() == "env v3\n"

        # The public command waits for the defaults lock before modifying files.
        cli_env = dict(os.environ, ICEWINE_THEME_ASSETS=str(assets), ICEWINE_DEFAULT_FILES=str(defaults),
                       ICEWINE_GTK_ENABLE="false", ICEWINE_SDDM_THEME_FILE="")
        lock_root = Path(cli_env["XDG_STATE_HOME"]) / "icewine"
        lock_root.mkdir(parents=True)
        with (lock_root / "defaults.lock").open("w") as lock:
            module.fcntl.flock(lock, module.fcntl.LOCK_EX)
            child = subprocess.Popen([sys.executable, str(script), "init", "uwsm"], env=cli_env,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                child.communicate(timeout=0.2)
                raise AssertionError("init bypassed an existing defaults lock")
            except subprocess.TimeoutExpired:
                assert not (lock_root / "default-files.json").exists()
            finally:
                module.fcntl.flock(lock, module.fcntl.LOCK_UN)
            stdout, stderr = child.communicate(timeout=15)
            assert child.returncode == 0, stderr

# Consumer opt-outs retire recognised resources, without widening scoped operations.
# Supplying native CSS defaults must not hide a pre-migration generated link.
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    config, data, state, defaults = (root / name for name in ("config", "data", "state/icewine", "defaults"))
    css_source = defaults / "config/gtk-3.0/gtk.css"
    css_source.parent.mkdir(parents=True)
    css_source.write_text('@import url("icewine/defaults.css");\n'
                          '@import url("../icewine/current/gtk.css");\n'
                          '/* Add your overrides below. */\n')
    with mock.patch.dict(os.environ, {"HOME": str(root), "XDG_DATA_HOME": str(data),
                                     "ICEWINE_DEFAULT_FILES": str(defaults), "ICEWINE_THEME_ASSETS": str(assets),
                                     "DBUS_SESSION_BUS_ADDRESS": "",
                                     "ICEWINE_GTK_ENABLE": "false", "ICEWINE_THEME_SKIP": "yazi/theme.toml:yazi/keymap.toml"}):
        module.publish(config, module.render_theme(assets, assets / "themes/dracula.json"))
        for relative, output in module.OWNED.items():
            path = config / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(config / "icewine/current" / output)
        user_file = config / "gtk-3.0/settings.ini"
        user_file.unlink()
        user_file.write_text("user GTK settings\n")
        unknown = config / "gtk-4.0/settings.ini"
        unknown.unlink()
        unknown.symlink_to(root / "user-settings")
        module.install_links(config, state, False, "yazi", install=False)
        assert not (config / "yazi/theme.toml").is_symlink()
        assert (config / "gtk-3.0/gtk.css").is_symlink(), "Scoped opt-out touched another consumer"
        module.install_links(config, state, False, install=False)
        assert not (config / "gtk-3.0/gtk.css").is_symlink()
        assert user_file.read_text() == "user GTK settings\n" and unknown.is_symlink()
        assert (config / "starship.toml").is_symlink(), "Enabled consumer was retired"
        module.publish(config, module.render_theme(assets, assets / "themes/nord.json"))
        assert not (config / "gtk-3.0/gtk.css").exists(), "Disabled CSS followed the next theme"
        assert list(state.glob("opt-out-*/gtk-3.0/gtk.css")), "Retirement lost its recovery copy"

        # Record real native writable entries while GTK is enabled, then opt out
        # through each public theme-only command. Local edits retain ownership.
        (defaults / "data").mkdir()
        for action in (("theme", "nord"), ("transparency", "low"), ("apply",)):
            with mock.patch.dict(os.environ, ICEWINE_GTK_ENABLE="true"):
                module.install_defaults(defaults, config, data, state, False, "gtk")
                module.install_links(config, state, False, "gtk")
                assert (config / "gtk-3.0/gtk.css").read_bytes() == css_source.read_bytes()
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config), "XDG_STATE_HOME": str(state.parent),
                                             "ICEWINE_GTK_ENABLE": "false"}), \
                 mock.patch.object(module, "reload_session", return_value=False):
                assert module.dispatch(list(action)) == 0
            assert not (config / "gtk-3.0/gtk.css").exists(), action
        with mock.patch.dict(os.environ, ICEWINE_GTK_ENABLE="true"):
            module.install_defaults(defaults, config, data, state, False, "gtk")
        css = config / "gtk-3.0/gtk.css"
        css.write_text(css.read_text() + "/* my inline styles */\n")
        module.install_links(config, state, False, "gtk", install=False)
        assert css.read_text().endswith("/* my inline styles */\n")
        module.install_defaults(defaults, config, data, state, True, "gtk")
        module.install_links(config, state, True, "gtk")
        assert not css.exists(), "Reset reactivated disabled native CSS"

        # Host-selected standalone CSS remains active even when newly installed,
        # untouched and tracked while Icewine GTK styling is disabled.
        css_source.write_text("window { color: red; }\n")
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config), "XDG_STATE_HOME": str(state.parent)}):
            assert module.dispatch(["init", "gtk"]) == 0
            assert css.read_bytes() == css_source.read_bytes()
            assert module.dispatch(["reset", "gtk"]) == 0
            assert css.read_bytes() == css_source.read_bytes()

        named = data / "themes/Icewine-dracula/gtk-3.0/gtk.css"
        named.parent.mkdir(parents=True)
        named.symlink_to(config / "icewine/current/gtk3-theme.css")
        custom = data / "themes/Icewine-nord/gtk-3.0/gtk.css"
        custom.parent.mkdir(parents=True)
        custom.write_text("custom CSS\n")
        extension = data / "flatpak/extension/org.gtk.Gtk3theme.Icewine-dracula/x86_64/3.22/gtk.css"
        extension.parent.mkdir(parents=True)
        extension.write_text("generated extension\n")
        record = state / "flatpak-themes/x86_64/dracula.sha256"
        record.parent.mkdir(parents=True)
        record.write_text(module.default_signature(extension).removeprefix("sha256:"))
        edited_extension = data / "flatpak/extension/org.gtk.Gtk3theme.Icewine-nord/x86_64/3.22/gtk.css"
        edited_extension.parent.mkdir(parents=True)
        edited_extension.write_text("user extension\n")
        (record.parent / "nord.sha256").write_text("0" * 64)
        with mock.patch.dict(os.environ, {"DBUS_SESSION_BUS_ADDRESS": "test"}), \
             mock.patch.object(module.subprocess, "run"):
            assert module.sync_gtk_settings("dracula", "dark", state)
        with mock.patch.dict(os.environ, {"DBUS_SESSION_BUS_ADDRESS": "test"}), \
             mock.patch.object(module.subprocess, "run", return_value=types.SimpleNamespace(stdout="'Icewine-dracula'\n")) as settings:
            assert module.retire_gtk_theme(config, state, module.installed(assets))
        assert not named.is_symlink() and not extension.exists() and not record.exists()
        assert custom.read_text() == "custom CSS\n" and edited_extension.read_text() == "user extension\n"
        assert [call.args[0][1] for call in settings.call_args_list] == ["get", "reset"]
        assert all(call.args[0][-1] == "gtk-theme" for call in settings.call_args_list)
        with mock.patch.dict(os.environ, {"DBUS_SESSION_BUS_ADDRESS": "test"}), \
             mock.patch.object(module.subprocess, "run", return_value=types.SimpleNamespace(stdout="'Custom'\n")) as settings:
            assert module.retire_gtk_theme(config, state, module.installed(assets))
        assert settings.call_count == 1, "Opt-out reset a user-selected GTK theme"
        with mock.patch.dict(os.environ, {"DBUS_SESSION_BUS_ADDRESS": "test"}), \
             mock.patch.object(module.subprocess, "run", return_value=types.SimpleNamespace(stdout="'Icewine-dracula'\n")) as settings:
            assert module.retire_gtk_theme(config, state, module.installed(assets))
        assert settings.call_count == 1, "Opt-out reset an unrecorded Icewine GTK selection"

# Recorded untouched files can become directories in one init. Directories have
# no ownership record and require manual retirement, even when empty.
for remaining in (None, "user.txt", "empty-directory", "edited-default", "user-removed-default"):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config, data, state, defaults = (root / name for name in ("config", "data", "state", "defaults"))
        for name in ("config", "data", "home"):
            (defaults / name).mkdir(parents=True)
        source = defaults / "config/yazi/plugins/example"
        source.parent.mkdir(parents=True)
        source.write_text("file v1\n")
        with mock.patch.dict(os.environ, {"HOME": str(root), "ICEWINE_STEAM_MASK_FILE": ""}):
            def update_shape():
                module.install_defaults(str(defaults), config, data, state, False, "yazi")
            update_shape()
            source.unlink()
            (source / "nested").mkdir(parents=True)
            (source / "nested/main.lua").write_text("module v2\n")
            update_shape()
            target = config / "yazi/plugins/example"
            assert (target / "nested/main.lua").read_text() == "module v2\n"
            if remaining == "user.txt":
                (target / remaining).write_text("user data\n")
            elif remaining == "empty-directory":
                (target / remaining).mkdir()
            elif remaining == "edited-default":
                (target / "nested/main.lua").write_text("user edit\n")
            elif remaining == "user-removed-default":
                (target / "nested/main.lua").unlink()
                (target / "nested").rmdir()
            (source / "nested/main.lua").unlink()
            (source / "nested").rmdir()
            source.rmdir()
            source.write_text("file v3\n")
            errors = io.StringIO()
            with mock.patch("sys.stderr", errors):
                update_shape()
            assert target.is_dir() and "remaining contents before retrying init" in errors.getvalue()
            if remaining == "user.txt":
                assert (target / remaining).read_text() == "user data\n"
            elif remaining == "empty-directory":
                assert (target / remaining).is_dir()
            elif remaining == "edited-default":
                assert (target / "nested/main.lua").read_text() == "user edit\n"
            elif remaining == "user-removed-default":
                assert not list(target.iterdir()), "Unknown empty replacement directory was removed"

# Retirement rechecks the ownership boundary after backup/signature reads, even
# when a substituted directory presents a byte-identical managed-looking file.
for consumer in ("generated", "named-gtk", "flatpak-gtk"):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config, data, state = (root / name for name in ("config", "data", "state"))
        module.publish(config, module.render_theme(assets, assets / "themes/dracula.json"))
        user = root / "user-directory"
        user.mkdir()
        if consumer == "generated":
            path = config / "gtk-3.0/gtk.css"
            target = config / "icewine/current/gtk.css"
        elif consumer == "named-gtk":
            path = data / "themes/Icewine-dracula/gtk-3.0/gtk.css"
            target = config / "icewine/current/gtk3-theme.css"
        else:
            path = data / "flatpak/extension/org.gtk.Gtk3theme.Icewine-dracula/x86_64/3.22/gtk.css"
            record = state / "flatpak-themes/x86_64/dracula.sha256"
            record.parent.mkdir(parents=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        if consumer == "flatpak-gtk":
            path.write_text("recorded CSS\n")
            (user / path.name).write_bytes(path.read_bytes())
            record.write_text(module.default_signature(path).removeprefix("sha256:"))
        else:
            path.symlink_to(target)
            (user / path.name).symlink_to(target)
        moved = root / "original-directory"
        def substitute_parent():
            path.parent.rename(moved)
            path.parent.symlink_to(user)
        original_backup = module.backup_owned
        original_signature = module.default_signature
        swapped = False
        def backup_then_substitute(*args, **kwargs):
            original_backup(*args, **kwargs)
            substitute_parent()
        def signature_then_substitute(candidate):
            global swapped
            signature = original_signature(candidate)
            if candidate == path and not swapped:
                swapped = True
                substitute_parent()
            return signature
        errors = io.StringIO()
        with mock.patch.dict(os.environ, {"HOME": str(root), "XDG_DATA_HOME": str(data), "ICEWINE_GTK_ENABLE": "false", "DBUS_SESSION_BUS_ADDRESS": ""}), \
             mock.patch("sys.stderr", errors):
            if consumer == "generated":
                with mock.patch.object(module, "backup_owned", side_effect=backup_then_substitute):
                    module.install_links(config, state, False, "gtk", install=False)
            else:
                with mock.patch.object(module, "default_signature", side_effect=signature_then_substitute):
                    module.retire_gtk_theme(config, state, module.installed(assets))
        assert (user / path.name).exists() and (moved / path.name).exists(), consumer
        assert "changed during installation" in errors.getvalue(), consumer
        if consumer == "flatpak-gtk":
            assert record.exists(), "Preserved extension lost its ownership record"

# A packaged migration cannot strand an edited old implementation behind new
# entry points. Exercise the real CLI before any generated/theme mutation.
for conflict in (None, "module", "module-directory", "entry", "entry-directory", "untracked", "parent", "package"):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config, data, state, old, new = (root / name for name in ("config", "data", "state/icewine", "old", "new"))
        source = script.parent.parent
        legacy = {
            "quickshell/shell.qml": "legacy shell\n", "hypr/hyprland.lua": "legacy hypr\n",
            "quickshell/modules/Topbar.qml": "legacy module\n",
            "hypr/modules/Baseline.lua": "legacy baseline\n",
            "quickshell/config/Settings.qml": "default settings\n",
            "hypr/modules/Binds.lua": "default binds\n",
            "hypr/modules/Autostart.lua": "default autostart\n",
        }
        for name, text in legacy.items():
            path = old / "config" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        (old / "data").mkdir()
        module.install_defaults(old, config, data, state, False, None)
        settings, binds = config / "quickshell/config/Settings.qml", config / "hypr/modules/Binds.lua"
        settings.write_text("user settings\n")
        binds.write_text("user binds\n")
        (new / "config/quickshell").mkdir(parents=True)
        (new / "config/hypr/modules").mkdir(parents=True)
        (new / "data").mkdir()
        for name in ("quickshell/shell.qml", "hypr/hyprland.lua", "quickshell/config/Settings.qml",
                     "hypr/modules/Binds.lua", "hypr/modules/Autostart.lua"):
            target = new / "config" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if name == "hypr/modules/Autostart.lua":
                target.write_text("-- Host-selected custom hook\n")
            else:
                shutil.copyfile(source / name.replace("hypr/", "hyprland/"), target)
        with (new / "config/hypr/hyprland.lua").open("a") as entry:
            entry.write('\ndofile((os.getenv("XDG_CONFIG_HOME") or os.getenv("HOME") .. "/.config") .. "/hypr/modules/Binds.lua")\n')
            entry.write('dofile((os.getenv("XDG_CONFIG_HOME") or os.getenv("HOME") .. "/.config") .. "/hypr/modules/Autostart.lua")\n')
        package = root / "implementation/quickshell"
        package.mkdir(parents=True)
        (new / "config/quickshell/icewine").symlink_to(package)
        if conflict == "module":
            (config / "quickshell/modules/Topbar.qml").write_text("user implementation\n")
        elif conflict == "module-directory":
            (config / "quickshell/modules/Topbar.qml").unlink()
            (config / "quickshell/modules/Topbar.qml").mkdir()
        elif conflict == "entry":
            (config / "hypr/hyprland.lua").write_text("user entry\n")
        elif conflict == "entry-directory":
            (config / "hypr/hyprland.lua").unlink()
            (config / "hypr/hyprland.lua").mkdir()
        elif conflict == "untracked":
            (config / "quickshell/modules/Custom.qml").write_text("user component\n")
        elif conflict == "parent":
            (config / "quickshell/modules").rename(root / "user-modules")
            (config / "quickshell/modules").symlink_to(root / "user-modules")
        elif conflict == "package":
            (config / "quickshell/icewine").symlink_to(root / "unknown-package")
        env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(config), XDG_DATA_HOME=str(data),
                   XDG_STATE_HOME=str(root / "state"), ICEWINE_THEME_ASSETS=str(assets),
                   ICEWINE_DEFAULT_FILES=str(new), ICEWINE_GTK_ENABLE="false",
                   DBUS_SESSION_BUS_ADDRESS="", WAYLAND_DISPLAY="")
        before_entry = module.default_signature(config / "hypr/hyprland.lua")
        before_module = module.default_signature(config / "quickshell/modules/Topbar.qml")
        before_manifest = (state / "default-files.json").read_bytes()
        for args in ((["init"], ["reset"]) if conflict else (["init", "quickshell"],)):
            result = subprocess.run([sys.executable, str(script), *args], env=env, capture_output=True, text=True)
            assert result.returncode == 1, result.stdout + result.stderr
            assert "migration" in result.stderr and "icewine init" in result.stderr, result.stderr
            assert module.default_signature(config / "hypr/hyprland.lua") == before_entry
            assert (config / "hypr/hyprland.lua").is_dir() == (conflict == "entry-directory")
            assert module.default_signature(config / "quickshell/modules/Topbar.qml") == before_module
            assert (config / "quickshell/modules/Topbar.qml").is_dir() == (conflict == "module-directory")
            assert (state / "default-files.json").read_bytes() == before_manifest
            assert not (config / "icewine/current").exists()
            assert settings.read_text() == "user settings\n" and binds.read_text() == "user binds\n"
        if conflict:
            continue
        result = subprocess.run([sys.executable, str(script), "init"], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert (config / "quickshell/icewine").resolve() == package
        assert not (config / "quickshell/modules/Topbar.qml").exists()
        assert not (config / "hypr/modules/Baseline.lua").exists()
        assert settings.read_text() == "user settings\n" and binds.read_text() == "user binds\n"
        assert (config / "hypr/hyprland.lua").read_bytes() == (new / "config/hypr/hyprland.lua").read_bytes()
        assert list(state.glob("defaults-update-*/config/quickshell/modules/Topbar.qml"))
        # Package updates preserve link identity in backups, not a copied store tree.
        next_package = root / "next-implementation/quickshell"
        next_package.mkdir(parents=True)
        marker = new / "config/quickshell/icewine"
        marker.unlink()
        marker.symlink_to(next_package)
        result = subprocess.run([sys.executable, str(script), "init"], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert (config / "quickshell/icewine").resolve() == next_package
        assert any(path.is_symlink() and path.resolve() == package
                   for path in state.glob("defaults-update-*/config/quickshell/icewine"))
        # Substituting the immutable identity after migration also blocks reset.
        (config / "quickshell/icewine").unlink()
        (config / "quickshell/icewine").symlink_to(root / "unknown-package")
        result = subprocess.run([sys.executable, str(script), "reset", "quickshell"], env=env, capture_output=True, text=True)
        assert result.returncode == 1 and "migration blocked" in result.stderr
        assert settings.read_text() == "user settings\n"
print("packaged implementation migration checks passed")

# Detected late conflicts must not switch entry points or strand the old entry
# after more than one of its required modules has already been retired.
for failure in ("after-backup", "late-edit", "mounted", "substituted-parent", "restore-collision",
                "entry-after-backup", "custom-after-backup", "entry-after-retirement",
                "custom-after-retirement", "during-loader-write", "after-loader-switch"):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config, data, state, old, new = (root / name for name in ("config", "data", "state", "old", "new"))
        legacy = {"hypr/hyprland.lua": "legacy hypr\n", "quickshell/shell.qml": "legacy shell\n",
                  "hypr/modules/Baseline.lua": "required baseline\n",
                  "hypr/modules/WindowPolicy.lua": "required window policy\n",
                  "quickshell/modules/Topbar.qml": "required topbar\n"}
        for name, text in legacy.items():
            path = old / "config" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        (old / "data").mkdir()
        module.install_defaults(old, config, data, state, False, None)
        (new / "config/quickshell").mkdir(parents=True)
        (new / "config/hypr").mkdir()
        (new / "data").mkdir()
        (new / "config/hypr/hyprland.lua").write_text("new loader\n")
        (new / "config/quickshell/shell.qml").write_text("new shell\n")
        (new / "config/quickshell/icewine").symlink_to(root / "package")
        before_manifest = (state / "default-files.json").read_bytes()
        topbar = config / "quickshell/modules/Topbar.qml"
        removed = []
        original_copy, original_unlink = shutil.copy2, Path.unlink
        original_atomic, original_fsync = module.atomic_text, os.fsync
        shell_entry = config / "quickshell/shell.qml"
        custom = config / "quickshell/modules/Custom.qml"
        def change_layout():
            if failure.startswith("entry") or failure == "during-loader-write":
                shell_entry.write_text("user entry imports old modules\n")
            else:
                custom.write_text("user custom component\n")
        def edit_after_backup(source, destination, *args, **kwargs):
            result = original_copy(source, destination, *args, **kwargs)
            if source == topbar:
                if failure in ("entry-after-backup", "custom-after-backup"):
                    change_layout()
                else:
                    topbar.write_text("user edit\n")
            return result
        def fail_after_removals(path, *args, **kwargs):
            if path == topbar and failure in ("late-edit", "mounted", "substituted-parent", "restore-collision"):
                assert len(removed) == 2, "Failure must follow two real implementation retirements"
                if failure == "mounted":
                    raise OSError(errno.EBUSY, "mounted fixture")
                if failure == "substituted-parent":
                    topbar.parent.rename(root / "original-modules")
                    (root / "user-modules").mkdir()
                    (root / "user-modules/Topbar.qml").write_text("user file\n")
                    topbar.parent.symlink_to(root / "user-modules")
                elif failure == "restore-collision":
                    (config / removed[0]).write_text("new user file\n")
                    topbar.write_text("user edit\n")
                else:
                    topbar.write_text("user edit\n")
                raise OSError(errno.EBUSY, "changed fixture")
            result = original_unlink(path, *args, **kwargs)
            relative = path.relative_to(config).as_posix()
            if relative in legacy and relative not in ("hypr/hyprland.lua", "quickshell/shell.qml"):
                removed.append(relative)
            if path == topbar and failure in ("entry-after-retirement", "custom-after-retirement"):
                change_layout()
            return result
        def edit_during_fsync(fd):
            result = original_fsync(fd)
            change_layout()
            return result
        def conflict_during_loader(path, *args, **kwargs):
            if path == shell_entry and failure == "during-loader-write":
                with mock.patch.object(os, "fsync", side_effect=edit_during_fsync):
                    return original_atomic(path, *args, **kwargs)
            result = original_atomic(path, *args, **kwargs)
            if path == config / "hypr/hyprland.lua" and failure == "after-loader-switch":
                change_layout()
            return result
        with mock.patch.object(shutil, "copy2", side_effect=edit_after_backup if failure in
                               ("after-backup", "entry-after-backup", "custom-after-backup") else original_copy), \
             mock.patch.object(Path, "unlink", new=fail_after_removals), \
             mock.patch.object(module, "atomic_text", side_effect=conflict_during_loader):
            try:
                module.install_defaults(new, config, data, state, False, None)
            except ValueError as error:
                assert "implementation migration aborted" in str(error), error
            else:
                raise AssertionError("Migration switched loaders after a detected implementation retirement conflict")
        expected_removed = 0 if failure.endswith("after-backup") else (2 if failure in
                           ("late-edit", "mounted", "substituted-parent", "restore-collision") else 3)
        assert len(removed) == expected_removed, (failure, removed)
        assert (config / "hypr/hyprland.lua").read_text() == legacy["hypr/hyprland.lua"]
        expected_entry = "user entry imports old modules\n" if failure.startswith("entry") or failure == "during-loader-write" else legacy["quickshell/shell.qml"]
        assert shell_entry.read_text() == expected_entry
        assert not (config / "quickshell/icewine").is_symlink()
        assert (state / "default-files.json").read_bytes() == before_manifest
        for name in ("hypr/modules/Baseline.lua", "hypr/modules/WindowPolicy.lua"):
            expected = "new user file\n" if failure == "restore-collision" and name == removed[0] else legacy[name]
            assert (config / name).read_text() == expected, (failure, name)
        if failure in ("mounted", "entry-after-backup", "custom-after-backup", "entry-after-retirement",
                       "custom-after-retirement", "during-loader-write", "after-loader-switch"):
            assert topbar.read_text() == legacy["quickshell/modules/Topbar.qml"]
        elif failure == "substituted-parent":
            assert (root / "user-modules/Topbar.qml").read_text() == "user file\n"
            assert (root / "original-modules/Topbar.qml").read_text() == legacy["quickshell/modules/Topbar.qml"]
        else:
            assert topbar.read_text() == "user edit\n"
        if failure.startswith("custom") or failure == "after-loader-switch":
            assert custom.read_text() == "user custom component\n"
print("implementation retirement/layout conflict recovery checks passed")

# Native-entry migration uses the existing ownership record, never today's byte
# equality. Verify package identity, active removed overrides and GTK CSS ownership.
for conflict in (None, "hypr-entry", "kitty-host", "unknown-link", "link-parent"):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config, data, state, old, new, package = (root / name for name in
            ("config", "data", "state", "old", "new", "package"))
        for source in (old, new):
            (source / "config").mkdir(parents=True)
            (source / "data").mkdir()
        legacy = {"hypr/hyprland.lua": "legacy loader\n", "kitty/kitty.conf": "include host.conf\n",
                  "kitty/host.conf": "", "hypr/modules/Binds.lua": "legacy binds\n"}
        for name, text in legacy.items():
            path = old / "config" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        module.install_defaults(old, config, data, state, False, None)
        for directory in ("hypr", "kitty", "gtk-3.0", "gtk-4.0"):
            (package / directory).mkdir(parents=True)
            path = new / "config" / directory
            path.mkdir(parents=True)
            (path / "icewine").symlink_to(package / directory)
        (package / "hypr/modules").mkdir()
        (package / "hypr/modules/Binds.lua").write_text("shared binds\n")
        (new / "config/hypr/modules").mkdir()
        (new / "config/hypr/modules/Binds.lua").symlink_to("hypr/icewine/modules/Binds.lua")
        for name in ("hypr/hyprland.lua", "kitty/kitty.conf"):
            source = script.parent.parent / name.replace("hypr/", "hyprland/")
            (new / "config" / name).write_bytes(source.read_bytes())
        for version, generated in ((3, "gtk.css"), (4, "gtk4.css")):
            path = new / f"config/gtk-{version}.0/gtk.css"
            path.write_text('@import url("icewine/defaults.css");\n'
                            f'@import url("../icewine/current/{generated}");\n')
            installed = config / f"gtk-{version}.0/gtk.css"
            installed.parent.mkdir(parents=True)
            installed.symlink_to(config / "icewine/current" / generated)
        if conflict == "hypr-entry":
            (config / "hypr/hyprland.lua").write_text("user loader\n")
        elif conflict == "kitty-host":
            (config / "kitty/host.conf").write_text("font_size 18\n")
        elif conflict == "unknown-link":
            (config / "kitty/icewine").symlink_to(root / "user-package")
        elif conflict == "link-parent":
            (config / "kitty").rename(root / "user-kitty")
            (config / "kitty").symlink_to(root / "user-kitty")
        before = (state / "default-files.json").read_bytes()
        with mock.patch.dict(os.environ, ICEWINE_DEFAULT_FILES=str(new)):
            if conflict:
                for reset in (False, True):
                    try:
                        module.install_defaults(new, config, data, state, reset, None)
                    except ValueError as error:
                        assert "migration blocked" in str(error), error
                    else:
                        raise AssertionError(f"Native migration bypassed {conflict}")
                    assert (state / "default-files.json").read_bytes() == before
                continue
            module.install_defaults(new, config, data, state, False, None)
            assert not (config / "kitty/host.conf").exists()
            binds = config / "hypr/modules/Binds.lua"
            assert binds.is_symlink() and binds.read_text() == "shared binds\n"
            binds.unlink()
            binds.write_text("my active binds\n")
            module.install_defaults(new, config, data, state, False, None)
            assert binds.read_text() == "my active binds\n"
            assert (config / "hypr/icewine").resolve() == package / "hypr"
            assert any(path.is_symlink() for path in state.glob("defaults-update-*/config/gtk-3.0/gtk.css"))
            css = config / "gtk-3.0/gtk.css"
            css.write_text(css.read_text() + "/* my rules */\n")
            module.install_links(config, state, True, "gtk")
            assert css.read_text().endswith("/* my rules */\n"), "Theme reset bypassed native CSS tracking"
            next_package = root / "next-kitty"
            next_package.mkdir()
            marker = new / "config/kitty/icewine"
            marker.unlink()
            marker.symlink_to(next_package)
            module.install_defaults(new, config, data, state, False, "kitty")
            assert (config / "kitty/icewine").resolve() == next_package
            backups = list(state.glob("defaults-update-*/config/kitty/icewine"))
            assert len(backups) == 1 and backups[0].is_symlink(), "Package update copied immutable files"
print("native-entry migration and CSS ownership checks passed")

# Native Hyprland ownership: matching-path HM provenance stays external even
# after its old Icewine manifest record exists. Reset must not replace it.
for old_record in (False, True):
    with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(os.environ, HOME=temporary):
        root = Path(temporary)
        config, data, state, defaults = (root / name for name in (".config", "data", "state", "defaults"))
        (defaults / "config/hypr").mkdir(parents=True)
        (defaults / "data").mkdir()
        starter = (script.parent.parent / "hyprland/hyprland.lua").read_text()
        (defaults / "config/hypr/hyprland.lua").write_text(starter)
        if old_record:
            module.install_defaults(defaults, config, data, state, False, None)
        store = root / "store"
        target = store / ("a" * 32 + "-home-manager-files") / ".config/hypr/hyprland.lua"
        target.parent.mkdir(parents=True)
        target.write_text('-- A freely edited host comment.\nrequire("icewine.icewine")\n-- calibrated host overrides\n')
        entry = config / "hypr/hyprland.lua"
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.unlink(missing_ok=True)
        entry.symlink_to(target)
        package = root / "implementation"
        package.mkdir()
        (defaults / "config/hypr/icewine").symlink_to(package)
        with mock.patch.object(module, "STORE_DIR", store):
            for reset in (False, True):
                module.install_defaults(defaults, config, data, state, reset, None)
                assert entry.is_symlink() and entry.resolve() == target
                assert "hypr/hyprland.lua" not in module.default_records(state)["config"]["files"]
            # Comments are user text, not ownership identity. New HM personal
            # modules may reuse a retired name after the actual transition.
            target.write_text('-- Peter changed this comment.\nrequire("icewine.icewine")\nrequire("modules.Personal")\n')
            personal_target = target.with_name("modules") / "Personal.lua"
            personal_target.parent.mkdir()
            personal_target.write_text("-- new active personal module\n")
            personal = config / "hypr/modules/Personal.lua"
            personal.parent.mkdir()
            personal.symlink_to(personal_target)
            for reset in (False, True):
                module.install_defaults(defaults, config, data, state, reset, None)
                assert entry.resolve() == target and personal.resolve() == personal_target
                assert "hypr/modules/Personal.lua" not in module.default_records(state)["config"]["files"]
            personal.unlink()
            # Unknown hook content before a real migration still blocks while
            # preserving both entry ownership and the would-be inactive edits.
            personal.write_text("unknown legacy edits\n")
            records = module.default_records(state)
            records["config"]["files"]["hypr/hyprland.lua"] = "sha256:" + "0" * 64
            (state / "default-files.json").write_text(json.dumps(records))
            for reset in (False, True):
                try:
                    module.install_defaults(defaults, config, data, state, reset, None)
                except ValueError as error:
                    assert str(personal) in str(error)
                else:
                    raise AssertionError("Unknown pre-migration hook became inactive")
                assert entry.resolve() == target and personal.read_text() == "unknown legacy edits\n"
            personal.unlink()
            # During a real first transition an obsolete HM loader must be
            # updated by HM, never replaced or removed by Icewine.
            target.write_text("unknown host entry\n")
            (config / "hypr/icewine").unlink()
            records = module.default_records(state)
            records["config"]["files"].pop("hypr/icewine")
            (state / "default-files.json").write_text(json.dumps(records))
            try:
                module.install_defaults(defaults, config, data, state, False, None)
            except ValueError as error:
                assert "hyprland.lua" in str(error)
            else:
                raise AssertionError("An incompatible Home Manager loader bypassed migration")

for hook in ("Binds", "Autostart", "Theme", "host", "Personal"):
    for edited in (False, True):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, data, state, defaults = (root / name for name in ("config", "data", "state", "defaults"))
            (defaults / "config/hypr/modules").mkdir(parents=True)
            (defaults / "data").mkdir()
            starter = defaults / "config/hypr/hyprland.lua"
            starter.write_text("old entry\n")
            shipped = defaults / "config/hypr/modules" / (hook + ".lua")
            shipped.write_text("old active hook\n")
            module.install_defaults(defaults, config, data, state, False, None)
            active = config / "hypr/modules" / shipped.name
            if edited:
                active.write_text("user calibration or behaviour\n")
            shipped.unlink()
            starter.write_bytes((script.parent.parent / "hyprland/hyprland.lua").read_bytes())
            before = (config / "hypr/hyprland.lua").read_bytes()
            if edited:
                for reset in (False, True):
                    try:
                        module.install_defaults(defaults, config, data, state, reset, None)
                    except ValueError as error:
                        assert str(active) in str(error) and "hyprland.lua" in str(error)
                    else:
                        raise AssertionError("Edited removed hook became inert: " + hook)
                    assert active.read_text() == "user calibration or behaviour\n"
                    assert (config / "hypr/hyprland.lua").read_bytes() == before
            else:
                module.install_defaults(defaults, config, data, state, False, None)
                assert not active.exists()
print("Home Manager entry ownership and retired active-hook checks passed")

# An edited old entry can still call pristine old hooks; retire neither until
# the user has migrated that entry. Later edits to the new native entry stay active.
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    config, data, state, defaults = (root / name for name in ("config", "data", "state", "defaults"))
    (defaults / "config/hypr/modules").mkdir(parents=True)
    (defaults / "data").mkdir()
    starter = defaults / "config/hypr/hyprland.lua"
    starter.write_text('require("modules.host")\n')
    hook = defaults / "config/hypr/modules/host.lua"
    hook.write_text("calibrated old host\n")
    module.install_defaults(defaults, config, data, state, False, None)
    entry = config / "hypr/hyprland.lua"
    entry.write_text(entry.read_text() + "-- edited loader\n")
    hook.unlink()
    starter.write_bytes((script.parent.parent / "hyprland/hyprland.lua").read_bytes())
    for reset in (False, True):
        try:
            module.install_defaults(defaults, config, data, state, reset, None)
        except ValueError as error:
            assert str(entry) in str(error)
        else:
            raise AssertionError("Edited old loader lost its still-active host hook")
        assert (config / "hypr/modules/host.lua").read_text() == "calibrated old host\n"
    entry.write_text('require("modules.host")\n')
    module.install_defaults(defaults, config, data, state, False, None)
    entry.write_text(entry.read_text() + "-- inline user overrides\n")
    module.install_defaults(defaults, config, data, state, False, None)
    assert entry.read_text().endswith("-- inline user overrides\n")
print("old loader migration and native inline edit preservation checks passed")
