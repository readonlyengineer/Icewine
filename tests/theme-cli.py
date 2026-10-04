#!/usr/bin/env python3
"""Focused regression checks for the shipped theme command."""

import os
import errno
import importlib.machinery
import json
import signal
import subprocess
import sys
import tempfile
import tomllib
import types
from pathlib import Path
from unittest import mock


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
    assert "Effective theme: catppuccin-mocha" in result.stdout
    assert edited.read_text() == "user edit\n"
    assert not legacy.is_symlink() and "property color primary" in legacy.read_text()
    assert unrelated.is_symlink() and os.readlink(unrelated) == "/nix/store/" + "b" * 32 + "-user-css"
    assert unknown_path.is_symlink() and os.readlink(unknown_path) == unknown_target
    assert "conflict: preserved unrecognized symlink" in result.stderr
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
    assert (config / "hypr/modules/Theme.lua").is_symlink()
    assert os.readlink(config / "hypr/modules/Theme.lua") == str(config / "icewine/current/Theme.lua")
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
    assert not old_steam.exists() and not old_steam.is_symlink()
    assert custom_launcher.read_text() == "user Steam launcher\n"
    assert unknown_steam.is_symlink()
    steam_migration = list((state / "icewine").glob("defaults-migration-*/data/applications/steam.desktop"))
    assert len(steam_migration) == 1 and os.readlink(steam_migration[0]) == old_steam_target
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
    assert run("init").returncode == 0
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
    importlib.machinery.SourceFileLoader(module.__name__, str(script)).exec_module(module)
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
        ("tokyo-night", "24283b", "dark"), ("dracula", "37354a", "dark"),
        ("nord", "37424e", "dark"), ("gruvbox-light", "e3e3bf", "light"),
        ("gruvbox-dark", "313433", "dark"),
        ("catppuccin-latte", "dae3f5", "light"),
        ("catppuccin-frappe", "394057", "dark"),
        ("catppuccin-macchiato", "2e344d", "dark"),
        ("catppuccin-mocha", "292d42", "dark"),
    ]:
        result = run("theme", theme_id)
        assert result.returncode == 0, result.stderr
        current = config / "icewine/current"
        assert f"background #{background}\n" in (current / "kitty.conf").read_text()
        assert kitty_entry.read_text() == "user Kitty theme edit\n"
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
        ("off", "1.00", "1.00"), ("low", "0.88", "0.91"),
        ("med", "0.80", "0.81"), ("high", "0.72", "0.71"),
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
    assert "background_opacity 0.72\n" in (current / "kitty.conf").read_text()
    assert "inactive_opacity = 0.71" in (current / "Theme.lua").read_text()
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
    result = run("apply")
    assert result.returncode == 0, result.stderr
    commands = command_log.read_text()
    for expected in ("hyprctl reload", "ya emit-to 0 app:theme",
                     "qs ipc call theme refresh"):
        assert expected in commands, commands
    assert "kitten @" not in commands and "nvim --server" not in commands
    yazi_command = (fake_bin / "ya").read_text()
    (fake_bin / "ya").write_text(yazi_command + "exit 2\n")
    command_log.write_text("")
    result = run("apply")
    assert result.returncode == 1 and "Failed: Yazi theme reload" in result.stderr
    assert "qs ipc call theme refresh" in command_log.read_text()
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
