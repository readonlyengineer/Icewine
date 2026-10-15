#!/usr/bin/env python3
"""Theme rendering and runtime changes never deploy user dotfiles."""
import errno
import fcntl
import pty
import select
import struct
import termios
import time
import io
import re
import signal
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest import mock
import importlib.machinery
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import types
from unittest.mock import patch

script, dispatcher, assets = map(lambda path: Path(path).resolve(), sys.argv[1:4])
os.environ["ICEWINE_THEME_ASSETS"] = str(assets)
theme = types.ModuleType("icewine_theme")
theme.__file__ = str(script)
importlib.machinery.SourceFileLoader(theme.__name__, str(script)).exec_module(theme)
for theme_id, palette in theme.installed(assets).items():
    for level in theme.TRANSPARENCY:
        rendered = theme.render_theme(assets, palette, level)
        assert json.loads(rendered["palette.json"])["themeId"] == theme_id
        btop = dict(re.findall(r'^theme\[(\w+)\]="(#[0-9a-fA-F]{6})"$', rendered["btop.theme"], re.M))
        colours = json.loads(palette.read_text())
        assert len(btop) == 48 and btop["main_bg"] == "#" + colours["background"]
        assert btop["main_fg"] == "#" + colours["foreground"]
        assert btop["cpu_box"] == "#" + colours["highlight"]
        assert btop["selected_bg"] == "#" + colours["selection"]
        assert btop["temp_end"] == "#" + colours["error"]
        assert json.loads(rendered["fastfetch.jsonc"])["modules"]
        assert "git_branch" in tomllib.loads(rendered["starship.toml"])
        assert tomllib.loads(rendered["yazi-theme.toml"])
        assert 'gtk-theme-name=Icewine-' + theme_id in rendered["gtk-settings.ini"]
with patch.dict(os.environ, ICEWINE_NIXPKGS_LAST_MODIFIED="1790821943", ICEWINE_THEME_GIT_ENABLE="false"):
    rendered = theme.render_theme(assets, assets / "themes/dracula.json")
    assert any(item.get("key", "").endswith("Nixpkgs") for item in json.loads(rendered["fastfetch.jsonc"])["modules"] if isinstance(item, dict))
    assert tomllib.loads(rendered["starship.toml"])["git_branch"]["disabled"]
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    config, state = root / "config", root / "state"
    env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(config), XDG_STATE_HOME=str(state),
               XDG_DATA_HOME=str(root / "data"), ICEWINE_THEME_ASSETS=str(assets), ICEWINE_GTK_ENABLE="false",
               ICEWINE_THEME_POLICY="", ICEWINE_SDDM_THEME_FILE="", WAYLAND_DISPLAY="", HYPRLAND_INSTANCE_SIGNATURE="")
    def run(*argv):
        return subprocess.run([sys.executable, str(script), *argv], env=env, capture_output=True, text=True)
    result = run("theme", "dracula")
    assert result.returncode == 0, result.stderr
    assert (state / "icewine/theme").read_text() == "dracula\n"
    assert json.loads((config / "icewine/current/palette.json").read_text())["themeId"] == "dracula"
    assert not (config / "yazi").exists() and not (config / "gtk-3.0").exists()
    assert not (config / "btop").exists()  # Optional app is never deployed implicitly.
    btop_theme = config / "icewine/current/btop.theme"
    dark_theme = btop_theme.read_bytes()
    btop_dir = config / "btop"
    (btop_dir / "themes").mkdir(parents=True)
    # Configured application fixture; explicit deployment is covered by install.py.
    btop_config = btop_dir / "btop.conf"
    preferences = 'color_theme = "icewine"\nupdate_ms = 500\nvim_keys = true\n'
    btop_config.write_text(preferences)
    selected_theme = btop_dir / "themes/icewine.theme"
    selected_theme.symlink_to(btop_theme)
    assert run("theme", "gruvbox-light").returncode == 0
    assert selected_theme.read_bytes() != dark_theme
    assert 'theme[main_bg]="#f2e5bc"' in selected_theme.read_text()
    assert btop_config.read_text() == preferences
    previous = (config / "icewine/current").resolve()
    with patch.object(Path, "write_text", side_effect=PermissionError(errno.EACCES, "btop publish denied")):
        try:
            theme.publish(config, {"btop.theme": "changed"})
        except PermissionError:
            pass
        else:
            raise AssertionError("failed btop publication reported success")
    assert (config / "icewine/current").resolve() == previous
    assert selected_theme.is_file() and btop_config.read_text() == preferences
    bad_assets = root / "bad-assets"
    shutil.copytree(assets, bad_assets)
    (bad_assets / "templates/btop.theme.in").chmod((bad_assets / "templates/btop.theme.in").stat().st_mode | 0o200)
    (bad_assets / "templates/btop.theme.in").write_text('theme[main_bg]="@missingBtopColour@"\n')
    bad = subprocess.run([sys.executable, str(script), "apply"],
                         env=dict(env, ICEWINE_THEME_ASSETS=str(bad_assets)), capture_output=True, text=True)
    assert bad.returncode != 0 and "unknown template value: missingBtopColour" in bad.stderr
    assert (config / "icewine/current").resolve() == previous
    assert btop_config.read_text() == preferences
    opt_out = preferences.replace('"icewine"', '"Default"')
    btop_config.write_text(opt_out)
    assert run("theme", "dracula").returncode == 0
    assert btop_config.read_text() == opt_out and selected_theme.read_bytes() == dark_theme
    assert not (state / "icewine/default-files.json").exists()
    assert run("transparency", "off").returncode == 0
    assert "off" in run("transparency").stdout
    assert "dracula" in run("theme", "status").stdout
    before = (state / "icewine/theme").read_bytes()
    assert run("theme", "missing").returncode != 0
    assert (state / "icewine/theme").read_bytes() == before
    for old in ("init", "reset"):
        assert run(old).returncode != 0
    with patch.dict(os.environ, env), patch.object(theme.subprocess, "run", return_value=types.SimpleNamespace(stdout="ok\n")) as refresh:
        os.environ["HYPRLAND_INSTANCE_SIGNATURE"] = "developer-test"
        theme.dispatch(["autofullscreen", "on"])
        assert refresh.call_args.args[0][0:2] == ["hyprctl", "eval"]
        refresh.return_value.stdout = "failed"
        try:
            theme.dispatch(["autofullscreen", "off"])
        except ValueError as error:
            assert "refresh failed" in str(error)
        else:
            raise AssertionError("Unconfirmed refresh reported success")
print("PASS: palette rendering, theme changes, no implicit deployment and runtime refresh")

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
    config, state = root / "config", root / "state"
    runtime = root / "runtime"
    runtime.mkdir()
    fake_bin = root / "bin"
    fake_bin.mkdir()
    (fake_bin / "ya").write_text("#!/bin/sh\nexit 0\n")
    (fake_bin / "ya").chmod(0o755)
    sddm_file = root / "sddm/theme.ini"
    kdeglobals = root / "sddm/kdeglobals"
    env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(config), XDG_STATE_HOME=str(state),
               XDG_DATA_HOME=str(root / "data"), ICEWINE_THEME_ASSETS=str(assets), ICEWINE_GTK_ENABLE="false",
               ICEWINE_THEME_POLICY="", ICEWINE_SDDM_THEME_FILE=str(sddm_file), ICEWINE_SDDM_KDEGLOBALS_FILE=str(kdeglobals), WAYLAND_DISPLAY="",
               HYPRLAND_INSTANCE_SIGNATURE="", DBUS_SESSION_BUS_ADDRESS="", XDG_RUNTIME_DIR=str(runtime),
               PATH=str(fake_bin)+":"+os.environ["PATH"])
    def run(*argv, policy=""):
        return subprocess.run([sys.executable, str(script), *argv], env=dict(env, ICEWINE_THEME_POLICY=policy), capture_output=True, text=True)
    assert run("theme", "catppuccin-mocha").returncode == 0
    nvim_theme = config / "icewine/current/nvim-theme.lua"
    kitty_entry = config / "kitty/kitty.conf"
    kitty_entry.parent.mkdir()
    (config / "yazi").mkdir()
    command = fake_bin / "icewine-theme"
    command.write_text("#!/bin/sh\nprintf '%s\n' \"$@\"\n")
    command.chmod(0o755)
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
    # Every shipped palette renders app-native files, including light mode.
    kitty_entry.write_text("user Kitty theme edit\n")
    for theme_id, background, appearance in [
        ("tokyo-night", "13131a", "dark"), ("dracula", "1d1e27", "dark"),
        ("nord", "282e38", "dark"), ("gruvbox-light", "f2e5bc", "light"),
        ("gruvbox-dark", "232323", "dark"),
        ("catppuccin-latte", "eff1f5", "light"),
        ("catppuccin-frappe", "242735", "dark"),
        ("catppuccin-macchiato", "1a1c2a", "dark"),
        ("catppuccin-mocha", "151521", "dark"),
    ]:
        result = run("theme", theme_id)
        assert result.returncode == 0, result.stderr
        assert sddm_file.read_text() == f"[General]\ntheme={theme_id}\n"
        if theme_id == "dracula":
            assert kdeglobals.read_bytes() == (config / "icewine/current/kdeglobals").read_bytes()
            assert kdeglobals.stat().st_mode & 0o777 == 0o644

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
    env["ICEWINE_SDDM_KDEGLOBALS_FILE"] = str(blocked / "kdeglobals")
    result = run("apply")
    assert result.returncode == 0 and "Pending: SDDM colours will not update" in result.stderr
    assert blocked.read_text() == "keep me\n"
    env["ICEWINE_SDDM_KDEGLOBALS_FILE"] = str(kdeglobals)

    # Opacity is independent of theme selection and survives reapplication.
    saved_theme = (state / "icewine/theme").read_text()
    for level, kitty_opacity, inactive_opacity in [
        ("off", "1.00", "1.00"), ("low", "0.80", "1.00"),
        ("med", "0.60", "1.00"), ("high", "0.40", "1.00"),
    ]:
        result = run("transparency", level)
        assert result.returncode == 0, result.stderr
        assert (state / "icewine/theme").read_text() == saved_theme
        assert (state / "icewine/transparency").read_text() == level + "\n"
        for command_args in [("apply",)]:
            assert run(*command_args).returncode == 0
            assert f"background_opacity {kitty_opacity}\n" in (current / "kitty.conf").read_text()
            assert f"inactive_opacity = {inactive_opacity}" in (current / "Theme.lua").read_text()
    assert run("theme", "dracula").returncode == 0
    assert "Transparency: high" in run("transparency").stdout
    previous = os.readlink(current)
    assert run("transparency", "invalid").returncode != 0
    assert os.readlink(current) == previous
    assert (state / "icewine/transparency").read_text() == "high\n"
    (state / "icewine/transparency").write_text("broken\n")
    assert run("apply").returncode != 0
    assert os.readlink(current) == previous
    assert run("transparency", "off").returncode == 0
    assert run("transparency", "high").returncode == 0
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
        with mock.patch.dict(os.environ, env):
            failed = module.reload_session(config, app)
        assert failed == (app == "yazi"), app
        assert command_log.read_text() == expected, app
    (fake_bin / "ya").write_text(yazi_command)
    command_log.write_text("")
    result = run("apply")
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
    assert result.stdout == "Theme: dracula · Transparency: high\n"
    (fake_bin / "ya").write_text(
        yazi_command + "echo 'Cannot emit command: Permission denied (os error 13)' >&2\nexit 2\n")
    command_log.write_text("")
    result = run("apply")
    assert result.returncode == 1 and "Failed: Yazi theme reload" in result.stderr
    assert "Permission denied (os error 13)" in result.stderr
    assert "qs ipc call theme refresh" in command_log.read_text()
    (fake_bin / "ya").write_text(
        yazi_command + "echo 'Cannot emit command: Connection refused (os error 111)' >&2\nexit 1\n")
    for args in (("transparency", "high"), ("apply",)):
        command_log.write_text("")
        result = run(*args)
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines()[-1] == "Theme: dracula · Transparency: high"
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


print("PASS: retained contrast, opacity, concurrent publication, reload failure and pidfd ownership coverage")

# Optional native smoke check; btop remains outside mandatory test dependencies.
# Run: python3 tests/theme-cli.py scripts/theme scripts/icewine theme/assets /path/to/btop
if len(sys.argv) > 4:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config = root / "config"
        defaults = root / "defaults"
        (defaults / "config/btop").mkdir(parents=True)
        (defaults / "config/btop/btop.conf").write_bytes((assets / "templates/btop.conf").read_bytes())
        (config / "btop").mkdir(parents=True)
        selected = config / "btop/themes/icewine.theme"
        env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(config),
                   XDG_STATE_HOME=str(root / "state"), XDG_DATA_HOME=str(root / "data"),
                   TERM="xterm-256color", LANG="C.UTF-8")
        for theme_id, background in [("dracula", b"48;2;40;42;54m"),
                                     ("gruvbox-light", b"48;2;242;229;188m")]:
            theme.publish(config, theme.render_theme(assets, assets / "themes" / (theme_id + ".json")))
            (config / "btop/btop.conf").write_text('color_theme = "Default"\nupdate_ms = 500\n')
            with patch.dict(os.environ, dict(env, ICEWINE_DEFAULT_FILES=str(defaults), ICEWINE_THEME_SKIP="")):
                theme.install_defaults(defaults, config, root / "data", root / "state/icewine", False, "btop")
                theme.install_links(config, root / "state/icewine", False, "btop")
            assert (config / "btop/btop.conf").read_text() == 'color_theme = "icewine"\nupdate_ms = 500\n'
            assert selected.is_symlink() and selected.resolve() == (config / "icewine/current/btop.theme").resolve()
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 35, 120, 0, 0))
            process = subprocess.Popen([sys.argv[4], "--debug", "--no-tty"],
                                       stdin=slave, stdout=slave, stderr=slave, env=env,
                                       start_new_session=True)
            os.close(slave)
            output = b""
            try:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline and process.poll() is None:
                    if select.select([master], [], [], 0.1)[0]:
                        try:
                            output += os.read(master, 65536)
                        except OSError:
                            break
                    if background in output:
                        break
                os.write(master, b"q")
                assert process.wait(timeout=5) == 0
                assert background in output, "btop did not render the generated background: " + theme_id
                log = (root / "state/btop.log").read_text()
                assert "Loading theme file:" in log and "icewine.theme" in log
                assert not any(message in log for message in (
                    "Missing color value", "Invalid RGB", "Invalid size of hex", "Hex value missing"))
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)
    print("PASS: native btop theme discovery, palette rendering and reopen after change")
