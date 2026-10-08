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
    log = root / "calls.jsonl"
    fake = commands / "record"
    fake.write_text(f'#!{sys.executable}\n' + '''
import json, os, sys
with open(os.environ["ICEWINE_TEST_LOG"], "a") as log:
    log.write(json.dumps([os.path.basename(sys.argv[0]), *sys.argv[1:]]) + "\\n")
sys.exit(int(os.environ.get("ICEWINE_TEST_FAIL", "0")))
''')
    fake.chmod(0o755)
    for name in ("kitty", "alacritty", "firefox", "nano", "steam", "icewine", "uwsm"):
        (commands / name).symlink_to(fake)
    for name in ("terminal", "terminal-exec", "browser", "editor", "file-manager", "steam"):
        (commands / ("icewine-" + name)).symlink_to(native / "command")
    env = dict(os.environ, PATH=str(commands) + ":" + os.environ["PATH"],
               ICEWINE_TEST_LOG=str(log))
    def run(name, *args, **extra):
        return subprocess.run([str(commands / name), *args], env=dict(env, **extra),
                              capture_output=True, text=True)
    for name, expected in {
        "terminal": ["kitty"], "terminal-exec": ["kitty", "-e"],
        "browser": ["firefox"], "editor": ["nano"],
        "file-manager": ["kitty", "-e", "yazi"], "steam": ["steam"],
    }.items():
        argument = "literal argument; $(must-not-run)"
        assert run("icewine-" + name, argument).returncode == 0
        assert json.loads(log.read_text().splitlines()[-1]) == expected + [argument]
    (commands / "kitty").unlink()
    env["PATH"] = str(commands)
    (commands / "bash").symlink_to(shutil.which("bash"))
    for name, expected in {
        "terminal": ["alacritty"], "terminal-exec": ["alacritty", "-e"],
        "file-manager": ["alacritty", "-e", "yazi"],
    }.items():
        argument = "literal argument; $(must-not-run)"
        assert run("icewine-" + name, argument).returncode == 0
        assert json.loads(log.read_text().splitlines()[-1]) == expected + [argument]
    (commands / "alacritty").unlink()
    (commands / "notify-send").symlink_to(fake)
    assert run("icewine-terminal").returncode != 0
    assert json.loads(log.read_text().splitlines()[-1])[0] == "notify-send"
    env["PATH"] = str(commands) + ":" + os.environ["PATH"]
    before = log.read_text()
    assert run("icewine-steam", ICEWINE_STEAM_ENABLED="false").returncode != 0
    assert log.read_text() == before
    session = root / "session"
    shutil.copyfile(native / "session", session)
    session.chmod(0o755)
    log.unlink()
    assert subprocess.run([str(session)], env=env).returncode == 0
    assert [json.loads(line) for line in log.read_text().splitlines()] == [
        ["icewine", "init"], ["uwsm", "start", "-eD", "Icewine:Hyprland", "-N", "Icewine", "--", "start-hyprland"]]
    log.unlink()
    assert subprocess.run([str(session)], env=dict(env, ICEWINE_TEST_FAIL="1")).returncode != 0
    assert [json.loads(line) for line in log.read_text().splitlines()] == [["icewine", "init"]]
print("PASS: literal launcher argv, disabled Steam and init-before-session failure handling")

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

desktop, fish, sddm = map(Path, sys.argv[2:5])
payload = desktop / "usr/share/icewine"
defaults = payload / "defaults"
assert not (defaults / "home").exists(), "Native package must not replace login shells"
assert not (desktop / "usr/share/fish").exists(), "Arch's shell must remain user-managed"
assert not (desktop / "etc/sddm.conf.d").exists(), "SDDM selection must remain optional"
assert (desktop / "etc/pam.d/icewine").read_text().splitlines()[1:] == [
    "auth include system-auth", "account include system-auth"]
assert "OnlyShowIn=Icewine;" in (desktop / "etc/xdg/autostart/icewine.desktop").read_text()
assert not list((desktop / "usr/lib/systemd/user").glob("*.wants")), "No globally enabled Icewine services"
mount = defaults / "config/yazi/plugins/mount.yazi"
assert {path.name for path in mount.iterdir()} == {"main.lua", "cross.lua", "sudo.lua", "LICENSE", "README.md"}
for name in ("main.lua", "cross.lua", "sudo.lua"):
    subprocess.run(["luac", "-p", str(mount / name)], check=True)
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    config, data, state = (root / name for name in ("config", "data", "state"))
    test_defaults = root / "defaults"
    shutil.copytree(defaults, test_defaults, symlinks=True)
    for path in test_defaults.rglob("*"):
        if path.is_symlink():
            target = os.readlink(path)
            assert target.startswith("/usr/share/icewine/")
            path.unlink()
            path.symlink_to(payload / target.removeprefix("/usr/share/icewine/"))
    env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(config), XDG_DATA_HOME=str(data),
               XDG_STATE_HOME=str(state), ICEWINE_THEME_ASSETS=str(payload / "theme"),
               ICEWINE_DEFAULT_FILES=str(test_defaults))
    for name in ("DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE"):
        env.pop(name, None)
    init = [sys.executable, str(desktop / "usr/lib/icewine/theme"), "init"]
    subprocess.run(init, env=env, check=True, stdout=subprocess.DEVNULL)
    assert (config / "quickshell/icewine/Desktop.qml").is_file()
    assert not (config / "nvim/init.lua").exists()
    assert not (config / "nvim/icewine").exists()
    assert (config / "nano/nanorc").read_text() == 'include "/usr/share/nano/*.nanorc"\n'
    assert (config / "yazi/plugins/mount.yazi/sudo.lua").is_file()
    edited = config / "kitty/kitty.conf"
    edited.write_text(edited.read_text() + "# user override\n")
    subprocess.run(init, env=env, check=True, stdout=subprocess.DEVNULL)
    assert edited.read_text().endswith("# user override\n")
    subprocess.run(["lua", str(source / "hyprland/tests/startup.lua"),
                    str(config / "hypr/hyprland.lua"), "desktop"], env=env, check=True)
assert (sddm / "usr/share/sddm/themes/icewine/theme/Palette.qml").read_text() == subprocess.check_output(
    [sys.executable, str(native / "sddm-palette.py")], text=True)
subprocess.run([sys.executable, str(source / "tests/arch-fish.py"), str(fish)], check=True)
print("PASS: native payload, complete upstream mount source, init preservation and desktop startup")
