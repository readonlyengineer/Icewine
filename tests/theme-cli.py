#!/usr/bin/env python3
"""Theme rendering and runtime changes never deploy user dotfiles."""
import errno
import hashlib
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


# Public append-only slot contract, independent of the renderer's declaration.
EXPECTED_TERMINAL_ROLES = tuple("""
    backgroundDark red green yellow blue magenta cyan foregroundDark
    blackBright redBright greenBright yellowBright blueBright magentaBright cyanBright foreground
    orange redDark highlight muted secondaryHighlight error purple teal background border caution
    highlightDark info mutedAlt mutedBright selection success surface tertiaryHighlight warning
    rosewater flamingo sapphire lavender crust foregroundAlt blueDark
    redNeutral greenNeutral yellowNeutral blueNeutral magentaNeutral cyanNeutral orangeNeutral
    redFaded greenFaded yellowFaded blueFaded magentaFaded cyanFaded orangeFaded
    redCanonicalBright greenCanonicalBright yellowCanonicalBright blueCanonicalBright
    magentaCanonicalBright cyanCanonicalBright orangeCanonicalBright foregroundCanonicalBright
    backgroundHard backgroundBase background4 foregroundHard foregroundBase foregroundSoft
    backgroundDarker backgroundLighter lineHighlight blue1 blue2 blue5 blue6 blue7
    green2 magenta2 tealCanonical gitAdd gitChange gitDelete
""".split())
assert theme.TERMINAL_ROLES == EXPECTED_TERMINAL_ROLES
assert len(set(EXPECTED_TERMINAL_ROLES)) == len(EXPECTED_TERMINAL_ROLES) == 85


def check_indexed_output(files, colours, git_enabled, nixpkgs):
    slots = {int(index): colour for index, colour in
             re.findall(r"(?m)^color(\d+) #([0-9a-f]{6})$", files["kitty.conf"])}
    roles = EXPECTED_TERMINAL_ROLES
    assert set(slots) == set(range(len(roles))) and len(roles) <= 256
    # Public ANSI and the original two extended colours must not be repurposed.
    ansi = ("backgroundDark red green yellow blue magenta cyan foregroundDark blackBright "
            "redBright greenBright yellowBright blueBright magentaBright cyanBright foreground orange redDark").split()
    assert [slots[i] for i in range(18)] == [colours[role] for role in ansi]
    # Every supplied colour, including canonical additions, is available by role.
    for role, colour in colours.items():
        if role != "appearance" and not role.endswith("Rgb"):
            assert slots[roles.index(role)] == colour, role
    assert set(slots.values()) <= set(colours.values())  # no fabricated variants

    def resolve(code):
        match = re.fullmatch(r"38;5;(\d+)", code)
        assert match, code
        return int(match[1]), slots[int(match[1])]

    report = json.loads(files["fastfetch.jsonc"])
    for key, role, index in (("1", "highlight", 18), ("2", "secondaryHighlight", 20)):
        assert resolve(report["logo"]["color"][key]) == (index, colours[role])
    headings = []
    commands = []
    for item in report["modules"]:
        if not isinstance(item, dict):
            continue
        if "keyColor" in item:
            assert resolve(item["keyColor"]) == (19, colours["muted"])
        if item["type"] == "custom":
            headings.extend(re.findall(r"\{#([^}]+)\}", item["format"]))
        if item["type"] == "command":
            commands.append(item)
            # Existing command warnings use normal ANSI yellow, not baked RGB.
            assert set(re.findall(r"\\033\[([\d;]+)m", item["text"])) <= {"0", "33"}
    assert len(headings) == 3
    assert all(resolve(code) == (18, colours["highlight"]) for code in headings)
    assert len(commands) == (2 if nixpkgs else 1)
    assert any(item["key"].endswith("Nixpkgs") for item in commands) == nixpkgs
    prompt = tomllib.loads(files["starship.toml"])
    # Stable role indices, not RGB equality, preserve past output across themes.
    for module, role, index in (("directory", "highlight", 18), ("time", "muted", 19),
                               ("cmd_duration", "muted", 19), ("git_branch", "magenta", 5),
                               ("git_commit", "green", 2), ("git_state", "yellow", 3),
                               ("git_status", "red", 1)):
        assert prompt[module]["style"] == f"bold fg:{index}"
        assert slots[index] == colours[role]
        if module.startswith("git_"):
            assert prompt[module]["disabled"] == (not git_enabled)
    assert prompt["git_metrics"]["disabled"] is True  # keep the existing opt-out
    assert ("$git_branch" in prompt["format"]) == git_enabled
    for key, role, index in (("success_symbol", "highlight", 18), ("error_symbol", "error", 21)):
        assert re.findall(r"\(bold fg:(\d+)\)", prompt["character"][key]) == [str(index)] * 2
        assert slots[index] == colours[role]
    for contents in (files["starship.toml"], files["fastfetch.jsonc"]):
        assert not re.search(r"#[0-9a-fA-F]{6}|(?:38|48);2;", contents), contents


for theme_id, palette in theme.installed(assets).items():
    for level in theme.TRANSPARENCY:
        rendered = theme.render_theme(assets, palette, level)
        assert json.loads(rendered["palette.json"])["themeId"] == theme_id
        assert "window_alert_on_bell no\n" in rendered["kitty-base.conf"]
        assert "bell_path /usr/share/sounds/freedesktop/stereo/bell.oga\n" in rendered["kitty-base.conf"]
        assert "/nix/store/" not in rendered["kitty-base.conf"]
        assert not any(line.startswith(("window_alert_on_bell ", "bell_path "))
                       for line in rendered["kitty.conf"].splitlines())
        assert json.loads(rendered["palette.json"])["keyboardOpacity"] == {"off":1.0,"low":0.8,"med":0.6,"high":0.4}[level]
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
        for git_enabled in (True, False):
            for nixpkgs in (True, False):
                env = dict(os.environ, ICEWINE_THEME_GIT_ENABLE=str(git_enabled).lower())
                env.pop("ICEWINE_NIXPKGS_LAST_MODIFIED", None)
                if nixpkgs:
                    env["ICEWINE_NIXPKGS_LAST_MODIFIED"] = "1790821943"
                with patch.dict(os.environ, env, clear=True):
                    files = theme.render_theme(assets, palette, level)
                check_indexed_output(files, colours, git_enabled, nixpkgs)

# Immutable legacy fields: the extension must not silently recolour other consumers.
legacy_hashes = {
    "catppuccin-frappe": "c1da231070bd072e96dd66548ada05f5ef4b401c8b87b0e7e098c79c01a89d9b",
    "catppuccin-latte": "45d8560c5d89c2be6c91b049b770afbf17c6e0470b624a5ba702926541cec9f4",
    "catppuccin-macchiato": "eb62bb3278d2b3e3ce317f6df91a8dc87df2e1f6a67ba424c3934bfb1c409958",
    "catppuccin-mocha": "91f1256f6cb9211cdd46614f8a8856976f65a7b959ea3e2a99f2f06b865967ca",
    "dracula": "49dd91f0748912dcc060aed03aca9dfd8a9e8716d1f71ca7665ff571a4e6d53b",
    "gruvbox-dark": "09431d82351c975d09e0c88d8ec5d3b237c88d4b74efa13b7089fd954aabb378",
    "gruvbox-light": "50c9c7bece546514ac3a5f70dadd629e3e005f5d3027f1b0574a3748b691cea6",
    "nord": "ee05c8f2f9e6fec10412d33886767c9d3d279be7f0aa6517a4cf9b4da3fd918d",
    "tokyo-night": "56f650eb83942b6d6f1e34aff155851e670ab26c4255a5098a306d3144cbe7ef",
}
assert set(theme.installed(assets)) == set(legacy_hashes)
catppuccin_additions = {
    "catppuccin-latte": "dc8a78 dd7878 209fb5 7287fd dce0e8",
    "catppuccin-frappe": "f2d5cf eebebe 85c1dc babbf1 232634",
    "catppuccin-macchiato": "f4dbd6 f0c6c6 7dc4e4 b7bdf8 181926",
    "catppuccin-mocha": "f5e0dc f2cdcd 74c7ec b4befe 11111b",
}
for theme_id, palette in theme.installed(assets).items():
    data = json.loads(palette.read_text())
    assert {key for key in data if key != "appearance" and not key.endswith("Rgb")} == set(EXPECTED_TERMINAL_ROLES)
    legacy = {key: value for key, value in data.items()
              if key in EXPECTED_TERMINAL_ROLES[:36] or key == "appearance" or key.endswith("Rgb")}
    assert len(legacy) == 42
    assert hashlib.sha256(json.dumps(legacy, sort_keys=True).encode()).hexdigest() == legacy_hashes[theme_id]
    expected_unique = 26 if theme_id.startswith("catppuccin-") else {
        "nord": 16, "gruvbox-dark": 36, "gruvbox-light": 36, "dracula": 34, "tokyo-night": 40,
    }[theme_id]
    assert len({v for v in data.values() if re.fullmatch(r"[0-9a-f]{6}", v)}) == expected_unique
    if theme_id.startswith("catppuccin-"):
        assert [data[key] for key in ("rosewater", "flamingo", "sapphire", "lavender", "crust")] == catppuccin_additions[theme_id].split()
    if theme_id == "nord":
        assert data["foregroundAlt"] == "e5e9f0" and data["blueDark"] == "5e81ac"
    if theme_id.startswith("gruvbox-"):
        # Both canonical base neutrals must resolve through the public slot, not the soft UI background.
        expected_base = "282828" if theme_id == "gruvbox-dark" else "fbf1c7"
        assert data["backgroundBase"] == expected_base
        kitty = theme.render_theme(assets, palette)["kitty.conf"]
        assert re.search(rf"(?m)^color66 #{expected_base}$", kitty)
        # Canonical neutral/bright/faded hue families and neutral ramps.
        canonical = """cc241d 98971a d79921 458588 b16286 689d6a d65d0e
            fb4934 b8bb26 fabd2f 83a598 d3869b 8ec07c fe8019
            9d0006 79740e b57614 076678 8f3f71 427b58 af3a03
            1d2021 282828 32302f 3c3836 504945 665c54 7c6f64 928374
            f9f5d7 fbf1c7 f2e5bc ebdbb2 d5c4a1 bdae93 a89984"""
        assert set(canonical.split()) <= set(data.values())
    if theme_id == "tokyo-night":
        additions = dict(zip(
            "backgroundDarker blue1 blue2 blue5 blue6 blue7 green2 magenta2 tealCanonical gitAdd gitChange gitDelete".split(),
            "0c0e14 2ac3de 0db9d7 89ddff b4f9f8 394b70 41a6b5 ff007c 1abc9c 449dab 6183bb 914c54".split()))
        assert all(data[key] == value for key, value in additions.items())
        assert not {"24283b", "1f2335", "1b1e2d"} & set(data.values())  # storm backgrounds
    if theme_id == "dracula":
        assert data["redBright"] == "ff7777" and data["redCanonicalBright"] == "ff6e6e"
        additions = dict(zip(
            "redCanonicalBright greenCanonicalBright yellowCanonicalBright blueCanonicalBright magentaCanonicalBright cyanCanonicalBright foregroundCanonicalBright backgroundLighter backgroundDarker lineHighlight".split(),
            "ff6e6e 69ff94 ffffa5 d6acff ff92df a4ffff ffffff 424450 191a21 353747".split()))
        assert all(data[key] == value for key, value in additions.items())

with tempfile.TemporaryDirectory() as temporary:
    palette = Path(temporary) / "invalid.json"
    valid = json.loads((assets / "themes/catppuccin-mocha.json").read_text())
    for changed in ({"highlight": None}, {"gitDelete": None}, {"rosewater": "bad hex"}, {"newColour": "abcdef"},
                    {"appearance": "invalid"}):
        data = valid | changed
        for key, value in changed.items():
            if value is None:
                del data[key]
        palette.write_text(json.dumps(data))
        try:
            theme.render_theme(assets, palette)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid/incomplete palette accepted: {changed}")
print("PASS: complete stable terminal palette roles and indexed Starship/Fastfetch in all 144 variants")
with patch.dict(os.environ, ICEWINE_NIXPKGS_LAST_MODIFIED="1790821943", ICEWINE_THEME_GIT_ENABLE="false"):
    rendered = theme.render_theme(assets, assets / "themes/dracula.json")
    assert any(item.get("key", "").endswith("Nixpkgs") for item in json.loads(rendered["fastfetch.jsonc"])["modules"] if isinstance(item, dict))
    assert tomllib.loads(rendered["starship.toml"])["git_branch"]["disabled"]
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    config, state = root / "config", root / "state"
    env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(config), XDG_STATE_HOME=str(state),
               XDG_DATA_HOME=str(root / "data"), ICEWINE_THEME_ASSETS=str(assets), ICEWINE_GTK_ENABLE="false",
               ICEWINE_THEME_POLICY="", WAYLAND_DISPLAY="", HYPRLAND_INSTANCE_SIGNATURE="")
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
    env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(config), XDG_STATE_HOME=str(state),
               XDG_DATA_HOME=str(root / "data"), ICEWINE_THEME_ASSETS=str(assets), ICEWINE_GTK_ENABLE="false",
               ICEWINE_THEME_POLICY="", WAYLAND_DISPLAY="",
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
    # File ownership is action-specific, independent of the host distribution.
    for name, old, new in (("theme", "catppuccin-mocha", "dracula"),
                           ("transparency", "high", "low"),
                           ("layout", "scrolling", "master"),
                           ("autofullscreen", "off", "on")):
        path = state / "icewine" / name
        original = path.read_bytes() if path.exists() else None
        path.unlink(missing_ok=True)
        declared = root / ("declared-" + name)
        declared.write_text(old + "\n")
        path.symlink_to(declared)
        assert run(name).returncode == 0
        rejected = run(name, new)
        assert rejected.returncode == 0, rejected.stderr
        assert path.is_symlink() and declared.read_text() == new + "\n"
        declared.chmod(0o444)
        denied = run(name, old)
        assert denied.returncode == 1 and declared.read_text() == new + "\n"
        declared.chmod(0o600)
        if name == "theme":
            assert run("transparency", "low").returncode == 0
        declared.unlink()
        assert run(name, new).returncode == 1
        assert path.is_symlink() and not declared.exists()
        path.unlink()
        if original is not None: path.write_bytes(original)
    directory = state / "icewine"
    external_state = root / "external-state"
    directory.rename(external_state)
    directory.symlink_to(external_state)
    assert run("layout", "master").returncode == 1
    assert not (external_state / "layout").exists()
    directory.unlink()
    external_state.rename(directory)
    # A link introduced during an atomic write is preserved too.
    race = directory / "layout"
    outside = root / "race-target"
    outside.write_text("preserve\n")
    def link_during_write(fd):
        race.symlink_to(outside)
    with mock.patch.object(module.os, "fsync", side_effect=link_during_write):
        try: module.atomic_text(race, "master\n")
        except ValueError: pass
        else: raise AssertionError("atomic write replaced a newly introduced link")
    assert race.is_symlink() and outside.read_text() == "preserve\n"
    race.unlink()
    assert not list(directory.glob(".icewine-*"))
    race.write_text("before\n")
    race.chmod(0o640)
    with mock.patch.object(module.os, "replace", side_effect=PermissionError("commit denied")):
        try: module.atomic_text(race, "after\n", setting=True)
        except PermissionError: pass
        else: raise AssertionError("setting commit failure ignored")
    assert race.read_text() == "before\n" and race.stat().st_mode & 0o777 == 0o640
    race.unlink()
    original_target = directory / "original-target"
    original_target.write_text("before\n")
    race.symlink_to(original_target)
    def retarget_during_write(fd):
        race.unlink()
        race.symlink_to(outside)
    with mock.patch.object(module.os, "fsync", side_effect=retarget_during_write):
        try: module.atomic_text(race, "after\n", setting=True)
        except ValueError: pass
        else: raise AssertionError("setting followed a changed link")
    assert original_target.read_text() == "before\n" and outside.read_text() == "preserve\n"
    race.unlink()
    original_target.unlink()

    protected_config = root / "protected-config"
    protected_current = protected_config / "icewine/current"
    protected_current.parent.mkdir(parents=True)
    protected_current.symlink_to(external)
    try: module.publish(protected_config, {"palette.json": "changed"})
    except ValueError: pass
    else: raise AssertionError("publication replaced an external current link")
    assert protected_current.is_symlink() and os.readlink(protected_current) == str(external)
    assert (external / "keep").read_text() == "user data"
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

        current = config / "icewine/current"
        assert f"background #{background}\n" in (current / "kitty.conf").read_text()
        assert kitty_entry.read_text() == "user Kitty theme edit\n"
        assert f'vim.opt.background = "{appearance}"' in nvim_theme.read_text()
        assert json.loads((current / "palette.json").read_text())["dark"] == (appearance == "dark")
        assert not (current / "Palette.qml").exists()
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
    assert 'local theme = "gruvbox-light"' in nvim_theme.read_text()
    assert run("theme", "not-installed").returncode != 0
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
    for failure in (None, "kitty", "nvim", "yazi"):
        (fake_bin / "ya").write_text(yazi_command + ("exit 2\n" if failure == "yazi" else ""))
        command_log.write_text("")
        with mock.patch.dict(os.environ, env), \
             mock.patch.object(module, "signal_reload",
                               side_effect=[failure == "kitty", failure == "nvim"]) as reload:
            failed = module.reload_session(config)
        assert failed == (failure is not None), failure
        assert reload.call_args_list == [mock.call("kitty", config, str(runtime)),
                                         mock.call("nvim", config, str(runtime))]
        assert command_log.read_text().splitlines() == [
            "hyprctl reload", "ya emit-to 0 app:theme", "qs ipc call theme refresh"], failure
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
    def process(pid, name, arguments, *, config_home=str(config), runtime_dir=str(runtime), kitty_config="", appname=None, editor_defaults=None):
        entry = proc / str(pid)
        entry.mkdir()
        (entry / "comm").write_text(name + "\n")
        (entry / "cmdline").write_bytes(b"\0".join(arg.encode() for arg in arguments) + b"\0")
        environment = f"HOME={root}\0XDG_CONFIG_HOME={config_home}\0XDG_RUNTIME_DIR={runtime_dir}\0KITTY_CONFIG_DIRECTORY={kitty_config}\0"
        if appname is not None: environment += f"NVIM_APPNAME={appname}\0"
        if editor_defaults is not None: environment += f"ICEWINE_NVIM_DEFAULTS={editor_defaults}\0"
        (entry / "environ").write_bytes(environment.encode())
    process(123, "kitty", ["kitty"])
    process(124, "kitty", ["kitty"], runtime_dir="/other-session")
    process(125, "kitty", ["kitty", "--config", "/other/kitty.conf"])
    process(126, "nvim", ["nvim", "notes.md"])
    process(127, "nvim", ["nvim", "-uNONE"])
    # Nixpkgs wraps Kitty's ELF executable but preserves the public argv[0].
    process(128, ".kitty-wrapped", ["/nix/store/example-kitty/bin/kitty"])
    process(129, ".kitty-wrapped", ["kitty"], runtime_dir="/other-session")
    process(130, ".kitty-wrapped", ["kitty", "--config=/other/kitty.conf"])
    process(131, ".kitty-wrapped", ["other-program"])
    process(132, ".kitty-wrapped", ["kitty"], kitty_config=str(root / "custom-kitty"))
    process(133, ".kitty-wrapped", ["kitty"], kitty_config=str(config / "kitty"))
    process(134, "kitty", ["kitty"], kitty_config=str(root / "custom-kitty"))
    process(135, ".kitty-wrapped", ["kitty"], config_home=str(root / "other-config"))
    process(136, ".kitty-wrapped", ["kitty", "-obackground=red"])
    process(137, ".kitty-wrapped", ["kitty"], kitty_config="relative-kitty")
    arch_init = "/usr/share/icewine/editor/init.lua"
    process(138, "nvim", ["nvim", "-u", arch_init, "notes.md"], appname="icewine-nvim")
    process(139, "nvim", ["nvim"], appname="icewine-nvim")
    process(140, "nvim", ["nvim", "-u", "/personal/init.lua"], appname="icewine-nvim")
    process(141, "nvim", ["nvim", "-u", arch_init], appname="nvim")
    process(142, "nvim", ["nvim", "-u", arch_init], appname="icewine-nvim", runtime_dir="/other-session")
    process(143, "nvim", ["nvim", "-u", arch_init], appname="icewine-nvim", config_home=str(root / "other-config"))
    # Actual native Nix wrapper argv: unwrapped nvim + provider-disable --cmd,
    # then the explicit shipped init. Also cover the wrapped executable identity.
    nix_init = str(root / "store/source-init.lua")
    nix_defaults = str(root / "store/source-defaults.lua")
    providers = "lua vim.g.loaded_node_provider=0;vim.g.loaded_perl_provider=0;vim.g.loaded_ruby_provider=0;vim.g.loaded_python3_provider=0"
    nix_argv = ["/nix/store/example-neovim-unwrapped/bin/nvim", "--cmd", providers, "-u", nix_init]
    process(144, "nvim", nix_argv + ["notes.md"], appname="icewine-nvim", editor_defaults=nix_defaults)
    process(145, ".nvim-wrapped", ["/nix/store/example-neovim/bin/.nvim-wrapped", *nix_argv[1:]], appname="icewine-nvim", editor_defaults=nix_defaults)
    process(146, "nvim", nix_argv + ["-u", "/personal/init.lua"], appname="icewine-nvim", editor_defaults=nix_defaults)
    process(147, "nvim", ["nvim", "--cmd", "lua print('custom startup')", "-u", nix_init], appname="icewine-nvim", editor_defaults=nix_defaults)
    process(148, "nvim", nix_argv + ["--headless"], appname="icewine-nvim", editor_defaults=nix_defaults)
    process(149, "nvim", nix_argv, appname="icewine-nvim", editor_defaults="/personal/defaults.lua")
    process(150, ".nvim-wrapped", ["nvim", "notes.md"])
    process(151, "other-program", nix_argv, appname="icewine-nvim", editor_defaults=nix_defaults)
    delivered = []
    fd_pids = {}
    def open_pid(pid):
        fd = os.open(os.devnull, os.O_RDONLY)
        fd_pids[fd] = pid
        return fd
    def send(fd, number):
        delivered.append((fd_pids[fd], number))
    with mock.patch.object(module, "PROC", proc), \
         mock.patch.object(module.os, "pidfd_open", open_pid, create=True), \
         mock.patch.object(module.signal, "pidfd_send_signal", send, create=True):
        assert module.signal_reload("kitty", config, str(runtime)) is False
        assert module.signal_reload("nvim", config, str(runtime)) is False
        assert sorted(delivered) == [(pid, signal.SIGUSR1) for pid in (123, 126, 128, 133, 138)], delivered
        delivered.clear()
        with mock.patch.dict(os.environ, ICEWINE_EDITOR_INIT=nix_init, ICEWINE_EDITOR_DEFAULTS=nix_defaults):
            assert module.signal_reload("nvim", config, str(runtime)) is False
        assert sorted(delivered) == [(pid, signal.SIGUSR1) for pid in (126, 144, 145)], delivered
        with mock.patch.object(module.signal, "pidfd_send_signal", mock.Mock(side_effect=ProcessLookupError)):
            assert module.signal_reload("kitty", config, str(runtime)) is False
        with mock.patch.object(module.signal, "pidfd_send_signal", mock.Mock(side_effect=PermissionError)):
            assert module.signal_reload("kitty", config, str(runtime)) is True
    with mock.patch.object(module, "PROC", proc), \
         mock.patch.object(module.os, "getuid", return_value=os.getuid() + 1), \
         mock.patch.object(module.os, "pidfd_open", side_effect=AssertionError("other user"), create=True):
        assert module.signal_reload("kitty", config, str(runtime)) is False
        assert module.signal_reload("nvim", config, str(runtime)) is False


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
