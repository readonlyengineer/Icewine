#!/usr/bin/env python3
"""Focused regression checks for the shipped theme command."""

import os
import importlib.machinery
import json
import subprocess
import sys
import tempfile
import tomllib
import types
from pathlib import Path


script = Path(sys.argv[1]).resolve()
dispatcher = Path(sys.argv[2]).resolve()
assets = Path(sys.argv[3]).resolve()

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
        "config/quickshell/modules/Thing.qml": b"default module\n",
        "config/quickshell/adapters/Adapter.qml": b"default adapter\n",
        "config/btop/btop.conf": b"default btop\n",
        "config/user-dirs.locale": b"default locale\n",
        "data/wallpapers/default.jpg": b"default wallpaper",
        "data/wallpapers/current_blurr.jpg": b"default blur",
    }.items():
        path = defaults / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    env = dict(os.environ, XDG_CONFIG_HOME=str(config), XDG_STATE_HOME=str(state),
               ICEWINE_THEME_ASSETS=str(assets), ICEWINE_THEME_POLICY="",
               ICEWINE_DEFAULT_FILES=str(defaults),
               HOME=str(root))
    env["XDG_DATA_HOME"] = str(root / "data")
    env.pop("DBUS_SESSION_BUS_ADDRESS", None)
    env.pop("WAYLAND_DISPLAY", None)
    env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)

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

    result = run("init")
    assert result.returncode == 0, result.stderr
    assert "Effective theme: tokyo-night" in result.stdout
    assert edited.read_text() == "user edit\n"
    assert 'primary: "#7aa2f7"' in legacy.read_text()
    assert unrelated.is_symlink() and os.readlink(unrelated) == "/nix/store/" + "b" * 32 + "-user-css"
    assert unknown_path.is_symlink() and os.readlink(unknown_path) == unknown_target
    assert "conflict: preserved unrecognized symlink" in result.stderr
    migration = list((state / "icewine").glob("migration-*/quickshell/theme/Palette.qml"))
    assert len(migration) == 1 and os.readlink(migration[0]) == legacy_target
    assert (config / "icewine/current").is_symlink()
    nvim_theme = config / "icewine/current/nvim-theme.lua"
    assert 'local theme = "tokyo-night"' in nvim_theme.read_text()
    fastfetch = json.loads((config / "icewine/current/fastfetch.jsonc").read_text())
    assert not any(item.get("key", "").endswith("Nixpkgs") for item in fastfetch["modules"] if isinstance(item, dict))
    assert tomllib.loads((config / "icewine/current/starship.toml").read_text())["git_branch"]["disabled"] is False
    assert (config / "yazi/keymap.toml").is_symlink()
    assert (config / "hypr/hyprland.lua").read_text() == "default hypr\n"
    assert (config / "hypr/modules/Theme.lua").is_symlink()
    assert os.readlink(config / "hypr/modules/Theme.lua") == str(config / "icewine/current/Theme.lua")
    assert (config / "quickshell/modules/Thing.qml").read_text() == "default module\n"
    assert (root / "data/wallpapers/default.jpg").read_bytes() == b"default wallpaper"
    assert not (config / "quickshell/modules/Thing.qml").is_symlink()

    (config / "quickshell/modules/Thing.qml").write_text("user module edit\n")
    (root / "data/wallpapers/default.jpg").write_bytes(b"user wallpaper")
    assert run("init").returncode == 0
    assert (config / "quickshell/modules/Thing.qml").read_text() == "user module edit\n"
    assert (root / "data/wallpapers/default.jpg").read_bytes() == b"user wallpaper"

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
    assert 'primary: "#7aa2f7"' in legacy.read_text()

    result = run("theme", "dracula")
    assert result.returncode == 0, result.stderr
    assert (state / "icewine/theme").read_text() == "dracula\n"
    assert 'local theme = "dracula"' in nvim_theme.read_text()
    assert 'primary: "#bd93f9"' in legacy.read_text()
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
    assert 'primary: "#bd93f9"' in legacy.read_text()

    (state / "icewine/theme").write_text("broken ID\n")
    result = run("init", policy="dracula")
    assert result.returncode == 0, result.stderr
    assert 'primary: "#bd93f9"' in legacy.read_text()
    (state / "icewine/theme").write_text("tokyo-night\n")

    result = run("reset")
    assert result.returncode == 0, result.stderr
    assert not (state / "icewine/theme").exists()
    assert "gtk-theme-name=Icewine-tokyo-night" in edited.read_text()
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

    fake_bin = root / "bin"
    fake_bin.mkdir()
    command = fake_bin / "icewine-theme"
    command.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
    command.chmod(0o755)
    routed = subprocess.run(["bash", str(dispatcher), "theme", "dracula"],
                            env=dict(env, PATH=f"{fake_bin}:{os.environ['PATH']}"),
                            text=True, capture_output=True)
    assert routed.returncode == 0 and routed.stdout == "theme\ndracula\n", routed.stderr

    # Exercise migration of a live Home Manager target and its content backup.
    module = types.ModuleType("icewine_theme")
    importlib.machinery.SourceFileLoader(module.__name__, str(script)).exec_module(module)
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
    old_home = os.environ.get("HOME")
    try:
        os.environ["HOME"] = str(legacy_home)
        module.STORE_DIR = root / "store"
        module.publish(legacy_config, module.render_theme(assets, assets / "themes/tokyo-night.json"))
        module.install_defaults(str(defaults), legacy_config, legacy_home / "data",
                                legacy_home / ".local/state/icewine", False, None)
        module.install_links(legacy_config, legacy_home / ".local/state/icewine", False)
    finally:
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home
    assert 'primary: "#7aa2f7"' in old_link.read_text()
    saved = list((legacy_home / ".local/state/icewine").glob("migration-*/quickshell/theme/Palette.qml"))
    assert len(saved) == 1 and saved[0].read_text() == "old managed palette\n"
    assert module_link.is_dir() and not module_link.is_symlink()
    assert (module_link / "Thing.qml").read_text() == "default module\n"
    assert adapters_link.is_symlink() and not (adapters_link / "Adapter.qml").exists()
    saved_modules = list((legacy_home / ".local/state/icewine").glob(
        "defaults-migration-*/config/quickshell/modules/Thing.qml"))
    assert len(saved_modules) == 1 and saved_modules[0].read_text() == "old managed module\n"

    # Every shipped palette renders app-native files, including light mode.
    for theme_id, background, appearance in [
        ("tokyo-night", "1a1b26", "dark"), ("dracula", "282a36", "dark"),
        ("nord", "2e3440", "dark"), ("gruvbox-light", "fbf1c7", "light"),
        ("gruvbox-dark", "282828", "dark"),
        ("catppuccin-latte", "eff1f5", "light"),
        ("catppuccin-frappe", "303446", "dark"),
        ("catppuccin-macchiato", "24273a", "dark"),
        ("catppuccin-mocha", "1e1e2e", "dark"),
    ]:
        result = run("theme", theme_id)
        assert result.returncode == 0, result.stderr
        current = config / "icewine/current"
        assert f"background #{background}\n" in (current / "kitty.conf").read_text()
        assert f'vim.opt.background = "{appearance}"' in nvim_theme.read_text()
        assert f'dark: "{appearance}"' in (current / "Palette.qml").read_text()
        assert f"gtk-application-prefer-dark-theme={int(appearance == 'dark')}" in (current / "gtk-settings.ini").read_text()
        for filename in ("starship.toml", "yazi-theme.toml", "yazi-keymap.toml"):
            tomllib.loads((current / filename).read_text())
    assert run("theme", "nord", policy="gruvbox-light").returncode == 0
    assert 'local theme = "gruvbox-light"' in nvim_theme.read_text()

    # Opacity is independent of theme selection and survives reapplication.
    saved_theme = (state / "icewine/theme").read_text()
    for level, kitty_opacity, inactive_opacity in [
        ("off", "1.00", "1.00"), ("low", "0.92", "0.95"),
        ("med", "0.84", "0.85"), ("high", "0.76", "0.75"),
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
    assert "background_opacity 0.84\n" in (current / "kitty.conf").read_text()
    assert "inactive_opacity = 0.85" in (current / "Theme.lua").read_text()
    routed = subprocess.run(["bash", str(dispatcher), "transparency", "low"],
                            env=dict(env, PATH=f"{fake_bin}:{os.environ['PATH']}"),
                            text=True, capture_output=True)
    assert routed.returncode == 0 and routed.stdout == "transparency\nlow\n", routed.stderr
