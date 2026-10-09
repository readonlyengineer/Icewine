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
        "config/user-dirs.locale": b"default locale\n",
        "config/nvim/init.lua": b"default nvim\n", # Host-supplied default.
        "config/nano/nanorc": b'include "/packaged/nano/*.nanorc"\n',
        "config/kitty/kitty.conf": b"default kitty\n",
        "config/icewine/shell/bashrc": b"# default bash\n",
        "config/icewine/shell/profile": b"# default profile\n",
        "config/icewine/shell/bash_profile": b"# default bash profile\n",
    }.items():
        path = defaults / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    (defaults / "home").mkdir()
    (defaults / "data").mkdir()
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
    env["PATH"] = f"{fake_bin}:{os.environ['PATH']}"
    env["XDG_RUNTIME_DIR"] = str(root / "runtime")
    (root / "runtime").mkdir()

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
    unrelated = config / "gtk-3.0/gtk.css"
    unrelated.symlink_to("/nix/store/" + "b" * 32 + "-user-css")
    unknown_path = config / "gtk-4.0/gtk.css"
    unknown_path.parent.mkdir(parents=True)
    unknown_target = "/nix/store/" + "d" * 32 + "-host-css"
    unknown_path.symlink_to(unknown_target)
    kitty_entry = config / "kitty/kitty.conf"
    bash_entry = root / ".bashrc"
    (root / ".profile").write_text("custom login profile\n")
    units = config / "systemd/user"
    wants = units / "graphical-session.target.wants"
    wants.mkdir(parents=True)
    unit_links = [units / "icewine.service", wants / "hypridle.service"]
    for path in unit_links:
        path.symlink_to("/nix/store/" + "1" * 32 + "-home-manager-files/"
                        + path.relative_to(root).as_posix())

    result = run("init")
    assert result.returncode == 0, result.stderr
    assert "Theme: catppuccin-mocha · Transparency: high" in result.stdout
    assert sddm_file.read_text() == "[General]\ntheme=catppuccin-mocha\n"
    assert sddm_file.stat().st_mode & 0o777 == 0o644
    assert edited.read_text() == "user edit\n"
    assert unrelated.is_symlink() and os.readlink(unrelated) == "/nix/store/" + "b" * 32 + "-user-css"
    assert unknown_path.is_symlink() and os.readlink(unknown_path) == unknown_target
    assert "conflict: preserved unrecognized symlink" in result.stderr
    assert (config / "icewine/current").is_symlink()
    nvim_theme = config / "icewine/current/nvim-theme.lua"
    assert 'local theme = "catppuccin-mocha"' in nvim_theme.read_text()
    fastfetch = json.loads((config / "icewine/current/fastfetch.jsonc").read_text())
    assert not any(item.get("key", "").endswith("Nixpkgs") for item in fastfetch["modules"] if isinstance(item, dict))
    assert tomllib.loads((config / "icewine/current/starship.toml").read_text())["git_branch"]["disabled"] is False
    assert (config / "yazi/keymap.toml").is_symlink()
    assert (config / "hypr/hyprland.lua").read_text() == "default hypr\n"
    assert not (config / "hypr/modules/Theme.lua").exists()
    assert (config / "nvim/init.lua").read_text() == "default nvim\n"
    assert kitty_entry.read_text() == "default kitty\n"
    assert os.readlink(bash_entry) == str(config / "icewine/shell/bashrc")
    assert (root / ".profile").read_text() == "custom login profile\n"
    for path in unit_links:
        assert path.is_symlink(), "Unknown units must not be retired"

    backups_before = set((state / "icewine").glob("defaults-update-*"))
    assert run("init").returncode == 0
    assert set((state / "icewine").glob("defaults-update-*")) == backups_before
    (config / "nvim/init.lua").write_text("user nvim edit\n")
    result = run("reset", "nvim")
    assert result.returncode == 0, result.stderr
    assert (config / "nvim/init.lua").read_text() == "default nvim\n"
    assert any(path.read_text() == "user nvim edit\n" for path in
               (state / "icewine").glob("defaults-reset-*/config/nvim/init.lua"))
    nano = config / "nano/nanorc"
    nano.write_text(nano.read_text() + "# user nano edit\n")
    (defaults / "config/nano/nanorc").write_text('include "/updated/nano/*.nanorc"\n')
    assert run("init", "nano").returncode == 0
    assert nano.read_text().endswith("# user nano edit\n")
    assert run("reset", "nano").returncode == 0
    assert nano.read_text() == 'include "/updated/nano/*.nanorc"\n'
    assert any(path.read_text().endswith("# user nano edit\n") for path in
               (state / "icewine").glob("defaults-reset-*/config/nano/nanorc"))
    kitty_entry.write_text("user Kitty entry edit\n")
    assert run("init").returncode == 0
    assert kitty_entry.read_text() == "user Kitty entry edit\n"
    result = run("reset", "kitty")
    assert result.returncode == 0, result.stderr
    assert kitty_entry.read_text() == "default kitty\n"
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

    # Exercise the shared implementation directly without live applications.
    module = types.ModuleType("icewine_theme")
    module.__file__ = str(script)
    importlib.machinery.SourceFileLoader(module.__name__, str(script)).exec_module(module)
    for release, glyph in (({"ID": "nixos"}, "\uf313"), ({"ID": "arch"}, "\uf303"),
                           ({"ID": "cachyos", "ID_LIKE": "arch"}, "\uf385"),
                           ({"ID": "other", "ID_LIKE": "arch"}, "\uf31a"), ({}, "\uf31a")):
        with mock.patch.object(module.platform, "freedesktop_os_release", return_value=release):
            rendered_theme = module.render_theme(assets, assets / "themes/dracula.json")
            report = json.loads(rendered_theme["fastfetch.jsonc"])
        assert json.loads(rendered_theme["palette.json"])["osGlyph"] == glyph
        assert next(item["key"] for item in report["modules"]
                    if isinstance(item, dict) and item.get("type") == "os") == f"├─ {glyph}  OS"
    with mock.patch.object(module.platform, "freedesktop_os_release", side_effect=OSError("unavailable")):
        rendered_theme = module.render_theme(assets, assets / "themes/dracula.json")
        report = json.loads(rendered_theme["fastfetch.jsonc"])
    assert json.loads(rendered_theme["palette.json"])["osGlyph"] == "\uf31a"
    assert next(item["key"] for item in report["modules"]
                if isinstance(item, dict) and item.get("type") == "os") == "├─ \uf31a  OS"
    concurrent_config = root / "concurrent-config"
    module.publish(concurrent_config, {"palette.json": "old\n"})
    rendered = concurrent_config / "icewine/rendered"
    old_generation = (concurrent_config / "icewine/current").resolve()
    unrelated = rendered / "user-files"
    unrelated.mkdir()
    external = root / "external-render"
    external.mkdir()
    (external / "keep").write_text("user data")
    (rendered / ("f" * 64)).symlink_to(external, target_is_directory=True)
    barrier = threading.Barrier(2)
    def simultaneous_publish(contents):
        barrier.wait(timeout=5)
        module.publish(concurrent_config, {"palette.json": contents})
    with ThreadPoolExecutor(max_workers=2) as publishers:
        jobs = [publishers.submit(simultaneous_publish, contents) for contents in ("first\n", "second\n")]
        for job in jobs:
            job.result(timeout=10)
    current = concurrent_config / "icewine/current"
    assert (current / "palette.json").read_text() in {"first\n", "second\n"}
    assert not old_generation.exists()
    assert [path for path in rendered.iterdir() if path.is_dir() and not path.is_symlink()
            and path != unrelated] == [current.resolve()]
    assert unrelated.is_dir() and (external / "keep").read_text() == "user data"
    previous = current.resolve()
    with mock.patch.object(Path, "rename", side_effect=PermissionError(errno.EACCES, "denied")):
        try:
            module.publish(concurrent_config, {"palette.json": "changed\n"})
        except PermissionError:
            pass
        else:
            raise AssertionError("publication must propagate non-collision errors")
    assert current.resolve() == previous and (current / "palette.json").is_file()
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
        old_mime = mask_store / ("d" * 32 + "-home-manager-files") / "config/mimeapps.list"
        old_mime.parent.mkdir(parents=True)
        old_mime.write_text("[Default Applications]\n" + "".join(
            name + "=firefox.desktop\n" for name in ("application/pdf", "application/xhtml+xml",
            "text/html", "x-scheme-handler/http", "x-scheme-handler/https")))
        mime = mask_config / "mimeapps.list"
        mime.parent.mkdir(parents=True)
        mime.symlink_to(old_mime)
        def reconcile_masks():
            module.install_defaults(str(mask_defaults), mask_config, mask_data, mask_state, False, None)
        reconcile_masks()
        mask_paths = [mask_data / "applications" / name for name in
                      ("steam.desktop", "com.valvesoftware.Steam.desktop")]
        assert all(path.is_symlink() and os.readlink(path) == str(first_mask) for path in mask_paths)
        reconcile_masks()
        assert not list(mask_state.glob("defaults-update-*"))
        os.environ["ICEWINE_STEAM_MASK_FILE"] = str(second_mask)
        reconcile_masks()
        assert all(os.readlink(path) == str(second_mask) for path in mask_paths)
        os.environ["ICEWINE_STEAM_MASK_FILE"] = ""
        reconcile_masks()
        assert all(not path.exists() and not path.is_symlink() for path in mask_paths)
        custom_target = mask_store / ("c" * 32 + "-home-manager-files") / "data/applications/steam.desktop"
        custom_target.parent.mkdir(parents=True)
        custom_target.write_text("[Desktop Entry]\nType=Application\nName=Steam\nNoDisplay=true\nHidden=true\n")
        mask_paths[0].symlink_to(custom_target)
        mask_paths[1].symlink_to(first_mask.parent / "missing-user-mask")
        launcher_path = mask_data / "applications/steam-gamescope.desktop"
        launcher_path.write_text("user Steam launcher\n")
        os.environ["ICEWINE_STEAM_MASK_FILE"] = str(first_mask)
        reconcile_masks()
        os.environ["ICEWINE_STEAM_MASK_FILE"] = ""
        reconcile_masks()
        assert os.readlink(mask_paths[0]) == str(custom_target)
        assert mask_paths[0].read_text() == custom_target.read_text()
        assert os.readlink(mask_paths[1]) == str(first_mask.parent / "missing-user-mask")
        assert launcher_path.read_text() == "user Steam launcher\n"
        assert mime.is_symlink() and mime.resolve() == old_mime
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
        # A user-substituted parent is never adopted, even with identical bytes.
        original_modules = config / "quickshell/modules"
        user_modules = root / "moved-shell-defaults"
        original_modules.rename(user_modules)
        original_modules.symlink_to(user_modules)
        (defaults / "config/quickshell/modules/Thing.qml").write_text("shell v2\n")
        with mock.patch.object(module.sys, "stderr", new_callable=io.StringIO) as errors:
            update("quickshell")
        assert "preserved symlinked parent" in errors.getvalue()
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
# Native CSS defaults and generated consumer links preserve scoped opt-outs.
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
                (config / "gtk-3.0/gtk.css").unlink(missing_ok=True)
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

# Current desktop/handheld identities support fresh scoped installation and updates.
# Old ownership records cannot authorize changing an implementation lacking them.
for handheld in (False, True):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config, data, state, defaults = (root / name for name in ("config", "data", "state/icewine", "defaults"))
        source = script.parent.parent
        for name in ("config", "data", "home"):
            (defaults / name).mkdir(parents=True)
        for relative, target in {
            "hypr/icewine": source / "hyprland",
            "quickshell/icewine": source / "quickshell",
            "kitty/icewine": source / "kitty",
        }.items():
            path = defaults / "config" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(target)
        for relative, original in {
            "hypr/hyprland.lua": "hyprland/hyprland.lua",
            "quickshell/shell.qml": "quickshell/deck/shell.qml" if handheld else "quickshell/shell.qml",
            "kitty/kitty.conf": "kitty/kitty.conf",
        }.items():
            (defaults / "config" / relative).write_bytes((source / original).read_bytes())
        env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(config), XDG_DATA_HOME=str(data),
                   XDG_STATE_HOME=str(state.parent), ICEWINE_DEFAULT_FILES=str(defaults),
                   ICEWINE_THEME_ASSETS=str(assets), ICEWINE_STEAM_MASK_FILE="",
                   ICEWINE_GTK_ENABLE="false", DBUS_SESSION_BUS_ADDRESS="", WAYLAND_DISPLAY="",
                   HYPRLAND_INSTANCE_SIGNATURE="", ICEWINE_SDDM_THEME_FILE="")
        with mock.patch.dict(os.environ, env), mock.patch.object(module, "reload_session", return_value=False), \
             mock.patch.object(module.shutil, "which", side_effect=lambda name: "/fake/ghostty" if name == "ghostty" else None):
            for app in ("hypr", "quickshell"):
                assert module.dispatch(["init", app]) == 0
            assert module.dispatch(["init"]) == 0
            assert (config / "quickshell/shell.qml").read_bytes() == (defaults / "config/quickshell/shell.qml").read_bytes()
            assert (config / "quickshell/icewine").resolve() == source / "quickshell"
            if handheld:
                continue  # Ownership/safety is shared; only this entrypoint differs.
            entry = config / "hypr/hyprland.lua"
            populated = entry.read_bytes()
            assert b'apps.terminal = "ghostty"' in populated and b"@file_manager@" not in populated
            subprocess.run(["lua", str(source / "hyprland/tests/startup.lua"), str(entry), "desktop"], env=env, check=True)
            subprocess.run(["lua", str(source / "hyprland/tests/startup.lua"), str(entry), "desktop", "empty-browser"], env=env, check=True)
            entry.write_text(entry.read_text() + "-- user overrides\n")
            assert module.dispatch(["init"]) == 0
            assert entry.read_text().endswith("-- user overrides\n")
            assert module.dispatch(["reset", "hypr"]) == 0
            assert entry.read_bytes() == populated
            # Idle is an optional sibling of the established Hyprland boundary.
            idle = defaults / "config/hypr/hypridle-icewine"
            for command in ("init", "reset"):
                idle.symlink_to(source / "hypridle")
                assert module.dispatch([command, "hypr"]) == 0
                assert (config / "hypr/hypridle-icewine").resolve() == source / "hypridle"
                idle.unlink()
                assert module.dispatch(["init", "hypr"]) == 0
                assert not (config / "hypr/hypridle-icewine").is_symlink()
            # Optional GTK, Kitty and Bash identities may be enabled alongside
            # current host defaults; the established shell identifies this record.
            for name, target, app in (
                ("gtk-3.0/icewine", source / "gtk", "gtk"),
                ("gtk-4.0/icewine", source / "gtk", "gtk"),
                ("kitty/icewine", source / "kitty", "kitty"),
                ("icewine/shell/icewine", source / "bash", "bash"),
            ):
                marker = defaults / "config" / name
                marker.unlink(missing_ok=True)
                host = marker.parent / "host.txt"
                host.parent.mkdir(parents=True, exist_ok=True)
                host.write_text("current host default\n")
                module.install_defaults(defaults, config, data, state, False, app)
                for replace in (False, True):
                    marker.symlink_to(target)
                    module.install_defaults(defaults, config, data, state, replace, app)
                    assert (config / name).resolve() == target
                    marker.unlink()
                    module.install_defaults(defaults, config, data, state, False, app)
                    assert not (config / name).is_symlink()
                marker.symlink_to(target)
                module.install_defaults(defaults, config, data, state, False, app)
            # Package updates retain link backups rather than copying implementation trees.
            replacement = root / "next-kitty"
            replacement.mkdir()
            marker = defaults / "config/kitty/icewine"
            marker.unlink()
            marker.symlink_to(replacement)
            assert module.dispatch(["init", "kitty"]) == 0
            assert (config / "kitty/icewine").resolve() == replacement
            assert any(path.is_symlink() for path in state.glob("defaults-update-*/config/kitty/icewine"))
            # Substituted current identities block both init and reset before publishing.
            marker = config / "quickshell/icewine"
            marker.unlink()
            marker.symlink_to(root / "user-implementation")
            before = (state / "default-files.json").read_bytes()
            rendered = os.readlink(config / "icewine/current")
            for command in ("init", "reset"):
                try:
                    module.dispatch([command])
                except ValueError as error:
                    assert "unknown package link" in str(error)
                else:
                    raise AssertionError("Unknown implementation identity was overwritten")
                assert (state / "default-files.json").read_bytes() == before
                assert os.readlink(config / "icewine/current") == rendered
            # No identity in a populated record: leave historical loaders/modules untouched.
            marker.unlink()
            records = module.default_records(state)
            records["config"]["files"].pop("quickshell/icewine")
            obsolete = config / "quickshell/modules/Old.qml"
            obsolete.parent.mkdir()
            obsolete.write_text("obsolete implementation\n")
            records["config"]["files"]["quickshell/modules/Old.qml"] = module.default_signature(obsolete)
            (state / "default-files.json").write_text(json.dumps(records))
            before = (state / "default-files.json").read_bytes()
            for command in ("init", "reset"):
                try:
                    module.dispatch([command])
                except ValueError as error:
                    assert "unsupported implementation ownership record" in str(error)
                else:
                    raise AssertionError("Unsupported ownership record authorized conversion")
                assert obsolete.read_text() == "obsolete implementation\n"
                assert (state / "default-files.json").read_bytes() == before
                assert os.readlink(config / "icewine/current") == rendered
print("current packaged defaults and unsupported-record preservation checks passed")

with tempfile.TemporaryDirectory() as temp:
    with mock.patch.dict(os.environ, {"XDG_STATE_HOME": temp, "HYPRLAND_INSTANCE_SIGNATURE": "developer-test"}), \
         mock.patch.object(module.subprocess, "run", return_value=types.SimpleNamespace(stdout="ok\n")) as refresh:
        module.dispatch(["autofullscreen", "off"])
        assert refresh.call_args.args[0] == ["hyprctl", "eval", 'require("icewine.modules.WindowPolicy").refresh_autofullscreen()']
        assert refresh.call_args.kwargs["check"] and refresh.call_args.kwargs["timeout"] == 10
        refresh.return_value.stdout = "policy unavailable"
        try:
            module.dispatch(["autofullscreen", "on"])
        except ValueError as error:
            assert "saved, but Hyprland policy refresh failed" in str(error)
        else:
            raise AssertionError("An unconfirmed native refresh reported success")
print("autofullscreen native refresh preserves Lua state and rejects unconfirmed IPC checks passed")

# Move a tracked immutable Neovim link to host-owned editable defaults safely.
for edited in (False, True):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        defaults, config, data, state = (root / name for name in ("defaults", "config", "data", "state"))
        (defaults / "config/nvim").mkdir(parents=True)
        (defaults / "data").mkdir()
        old = root / "implementation"
        old.mkdir()
        (old / "defaults.lua").write_text("old defaults\n")
        entry = defaults / "config/nvim/init.lua"
        entry.write_text("host entry\n")
        link = defaults / "config/nvim/icewine"
        link.symlink_to(old)
        module.install_defaults(str(defaults), config, data, state, False, None)
        if edited:
            (config / "nvim/init.lua").write_text("user edits\n")
        link.unlink()
        link.mkdir()
        (link / "defaults.lua").write_text("host defaults\n")
        module.install_defaults(str(defaults), config, data, state, False, None)
        assert not (config / "nvim/icewine").is_symlink()
        assert (config / "nvim/icewine/defaults.lua").read_text() == "host defaults\n"
        assert (config / "nvim/init.lua").read_text() == ("user edits\n" if edited else "host entry\n")
        assert any(path.is_symlink() for path in state.glob("defaults-update-*/config/nvim/icewine"))
        # Retirement must retain user edits when the host/default disappears.
        entry.unlink()
        module.install_defaults(str(defaults), config, data, state, False, None)
        assert (config / "nvim/init.lua").exists() == edited
print("PASS: Neovim host relocation and edited obsolete entry preservation")
