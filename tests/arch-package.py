#!/usr/bin/env python3
"""Direct native launcher checks; pass makepkg roots to also check built payloads."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import importlib.machinery
import vdf

source = Path(sys.argv[1]).resolve()
native = source / "packaging/arch"

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    commands = root / "bin"
    commands.mkdir()
    (commands / "bash").symlink_to(shutil.which("bash"))
    log = root / "calls.jsonl"
    fake = commands / "record"
    fake.write_text(f'#!{sys.executable}\n' + '''
import json, os, sys
with open(os.environ["ICEWINE_TEST_LOG"], "a") as log:
    log.write(json.dumps([os.path.basename(sys.argv[0]), *sys.argv[1:]]) + "\\n")
sys.exit(int(os.environ.get("ICEWINE_TEST_FAIL", "0")))
''')
    fake.chmod(0o755)
    for name in ("nano", "steam", "icewine", "uwsm"):
        (commands / name).symlink_to(fake)
    for name in ("editor", "steam"):
        (commands / ("icewine-" + name)).symlink_to(native / "command")
    env = dict(os.environ, PATH=str(commands) + ":" + os.environ["PATH"],
               HOME=str(root), XDG_CONFIG_HOME=str(root / "config"), ICEWINE_TEST_LOG=str(log))
    env.pop("EDITOR", None)
    env.pop("VISUAL", None)
    def run(name, *args, **extra):
        return subprocess.run([str(commands / name), *args], env=dict(env, **extra),
                              capture_output=True, text=True)
    for name, expected in {
        "editor": ["nano"],
        "steam": ["steam"],
    }.items():
        argument = "literal argument; $(must-not-run)"
        assert run("icewine-" + name, argument).returncode == 0
        assert json.loads(log.read_text().splitlines()[-1]) == expected + [argument]
    for overrides, expected in (({}, ("icewine-editor", "icewine-editor")),
                                 ({"EDITOR": "my-editor", "VISUAL": "my-visual"}, ("my-editor", "my-visual"))):
        result = subprocess.run(["bash", "-c", 'source "$1"; printf "%s\\n%s\\n" "$EDITOR" "$VISUAL"',
                                 "session", str(source / "session/env")], env=dict(env, **overrides),
                                capture_output=True, text=True)
        assert result.returncode == 0 and tuple(result.stdout.splitlines()) == expected
    before = log.read_text()
    assert run("icewine-steam", ICEWINE_STEAM_ENABLED="false").returncode != 0
    assert log.read_text() == before
    session = root / "session"
    shutil.copyfile(native / "session", session)
    session.chmod(0o755)
    log.unlink()
    assert subprocess.run([str(session)], env=env).returncode == 0
    assert [json.loads(line) for line in log.read_text().splitlines()] == [
        ["uwsm", "start", "-eD", "Icewine:Hyprland", "-N", "Icewine", "--", "start-hyprland"]]
    log.unlink()
    assert subprocess.run([str(session)], env=dict(env, ICEWINE_TEST_FAIL="1")).returncode != 0
    assert [json.loads(line) for line in log.read_text().splitlines()] == [["uwsm", "start", "-eD", "Icewine:Hyprland", "-N", "Icewine", "--", "start-hyprland"]]
print("PASS: literal launchers, disabled Steam and session without implicit deployment")

shortcuts = importlib.machinery.SourceFileLoader("shortcuts", str(source / "quickshell/tools/steam-shortcuts")).load_module()
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "shortcuts.vdf"
    path.write_bytes(vdf.binary_dumps({"shortcuts": {
        "0": {"exe": '\"/games/My Game\"', "launchoptions": '--flag \"two words\"'},
        "1": {"exe": "bad; command", "launchoptions": ""},
    }}))
    assert shortcuts.commands(path) == [["/games/My Game", "--flag", "two words"]]
print("PASS: real python-vdf shortcut binary API and literal command filtering")

if len(sys.argv) == 2:
    sys.exit(0)

desktop, session, sddm = map(Path, sys.argv[2:5])
payload = desktop / "usr/share/icewine"
defaults = payload / "defaults"
assert (desktop / "usr/bin/icewine-manage").is_file()
assert not (desktop / "usr/share/wayland-sessions").exists()
assert not (desktop / "usr/lib/systemd/user").exists()
assert not (desktop / "etc/pam.d/icewine").exists()
assert not (desktop / "etc/sddm.conf.d").exists()
assert not (desktop / "usr/share/fish").exists()
assert (session / "usr/share/wayland-sessions/icewine.desktop").is_file()
assert (session / "etc/pam.d/icewine").read_text().splitlines()[1:] == [
    "auth include system-auth", "account include system-auth"]
assert "OnlyShowIn=Icewine;" in (session / "etc/xdg/autostart/icewine.desktop").read_text()
assert not list((session / "usr/lib/systemd/user").glob("*.wants"))
mount = defaults / "config/yazi/plugins/mount.yazi"
assert {path.name for path in mount.iterdir()} == {"main.lua", "cross.lua", "sudo.lua", "LICENSE", "README.md"}
for name in ("main.lua", "cross.lua", "sudo.lua"):
    subprocess.run(["luac", "-p", str(mount / name)], check=True)
assert (sddm / "usr/share/sddm/themes/icewine/theme/Palette.qml").read_text() == subprocess.check_output(
    [sys.executable, str(native / "sddm-palette.py")], text=True)
subprocess.run([sys.executable, str(source / "tests/manager-tty.py"), str(desktop / "usr/bin/icewine-manage")], check=True)
print("PASS: base/session/login payload separation and real manager TTY interaction")
