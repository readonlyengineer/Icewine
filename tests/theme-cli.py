#!/usr/bin/env python3
"""Focused regression checks for the shipped theme command."""

import os
import importlib.machinery
import subprocess
import sys
import tempfile
import types
from pathlib import Path


script = Path(sys.argv[1]).resolve()
dispatcher = Path(sys.argv[2]).resolve()
names = {
    "Palette.qml", "Theme.lua", "kitty.conf", "gtk.css", "gtk-settings.ini",
    "yazi-theme.toml", "fastfetch.jsonc", "starship.toml", "ls-colors.sh",
}

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    assets = root / "assets"
    config = root / ".config"
    state = root / "state"
    wallpaper = root / "data/icewine/wallpapers/selection.img"
    wallpaper.parent.mkdir(parents=True)
    wallpaper.write_bytes(b"wallpaper is independent")
    for theme in ("tokyo-night", "dracula"):
        directory = assets / theme
        directory.mkdir(parents=True)
        for name in names:
            (directory / name).write_text(f"{theme}/{name}\n")
    env = dict(os.environ, XDG_CONFIG_HOME=str(config), XDG_STATE_HOME=str(state),
               ICEWINE_THEME_ASSETS=str(assets), ICEWINE_THEME_POLICY="",
               HOME=str(root))
    env.pop("WAYLAND_DISPLAY", None)
    env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)

    def run(*arguments, policy="", skip=""):
        return subprocess.run([sys.executable, str(script), *arguments],
                              env=dict(env, ICEWINE_THEME_POLICY=policy,
                                       ICEWINE_THEME_SKIP=skip),
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
    assert legacy.read_text() == "tokyo-night/Palette.qml\n"
    assert unrelated.is_symlink() and os.readlink(unrelated) == "/nix/store/" + "b" * 32 + "-user-css"
    assert unknown_path.is_symlink() and os.readlink(unknown_path) == unknown_target
    assert "conflict: preserved unrecognized symlink" in result.stderr
    migration = list((state / "icewine").glob("migration-*/quickshell/theme/Palette.qml"))
    assert len(migration) == 1 and os.readlink(migration[0]) == legacy_target
    assert (config / "icewine/current").is_symlink()

    result = run("theme", "missing")
    assert result.returncode != 0
    assert not (state / "icewine/theme").exists()
    assert legacy.read_text() == "tokyo-night/Palette.qml\n"

    result = run("theme", "dracula")
    assert result.returncode == 0, result.stderr
    assert (state / "icewine/theme").read_text() == "dracula\n"
    assert legacy.read_text() == "dracula/Palette.qml\n"
    assert unrelated.is_symlink() and os.readlink(unrelated) == "/nix/store/" + "b" * 32 + "-user-css"
    assert edited.read_text() == "user edit\n"
    assert "Effective: dracula" in run("theme").stdout

    result = run("theme", "tokyo-night", policy="dracula")
    assert result.returncode == 0, result.stderr
    assert "Nix policy overrides CLI selection" in result.stdout
    assert (state / "icewine/theme").read_text() == "tokyo-night\n"
    assert legacy.read_text() == "dracula/Palette.qml\n"

    (state / "icewine/theme").write_text("broken ID\n")
    result = run("init", policy="dracula")
    assert result.returncode == 0, result.stderr
    assert legacy.read_text() == "dracula/Palette.qml\n"
    (state / "icewine/theme").write_text("tokyo-night\n")

    result = run("reset")
    assert result.returncode == 0, result.stderr
    assert not (state / "icewine/theme").exists()
    assert edited.read_text() == "tokyo-night/gtk-settings.ini\n"
    assert wallpaper.read_bytes() == b"wallpaper is independent"
    backups = list((state / "icewine").glob("reset-*/gtk-3.0/settings.ini"))
    assert len(backups) == 1 and backups[0].read_text() == "user edit\n"

    host_paths = ["fastfetch/config.jsonc", "starship.toml", "yazi/theme.toml"]
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
    old_home = os.environ.get("HOME")
    try:
        os.environ["HOME"] = str(legacy_home)
        module.STORE_DIR = root / "store"
        module.publish(legacy_config, assets / "tokyo-night")
        module.install_links(legacy_config, legacy_home / ".local/state/icewine", False)
    finally:
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home
    assert old_link.read_text() == "tokyo-night/Palette.qml\n"
    saved = list((legacy_home / ".local/state/icewine").glob("migration-*/quickshell/theme/Palette.qml"))
    assert len(saved) == 1 and saved[0].read_text() == "old managed palette\n"
