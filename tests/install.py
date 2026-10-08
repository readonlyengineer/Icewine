#!/usr/bin/env python3
"""Check installer orchestration with fake host commands; no build or installation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    checkout = root / "checkout with spaces"
    checkout.mkdir()
    shutil.copy2(source / "install.sh", checkout / "install.sh")
    commands = root / "bin"
    commands.mkdir()
    log = root / "calls.jsonl"
    fake = commands / "record"
    fake.write_text("#!" + sys.executable + "\n" + r'''
import json, os, sys
from pathlib import Path
name, args = Path(sys.argv[0]).name, sys.argv[1:]
with open(os.environ["INSTALL_TEST_LOG"], "a") as log:
    log.write(json.dumps([name, *args]) + "\n")
if name == "id": print(os.environ.get("INSTALL_TEST_UID", "1000"))
elif name == "pacman" and args[:1] == ["-Qq"]:
    sys.exit(0 if args[1] in os.environ.get("INSTALL_TEST_TERMINALS", "").split() else 1)
elif name == "python": print(os.environ["INSTALL_TEST_DISTRO"])
elif name == "git":
    os.execv(os.environ["INSTALL_TEST_GIT"], ["git", "-C", os.environ["INSTALL_TEST_SOURCE"], *args])
elif name == "makepkg" and args == ["-sf"]:
    assert Path("PKGBUILD").is_file() and Path("icewine.tar.gz").is_file()
elif name == "makepkg" and args == ["--packagelist"]:
    for name in ("icewine", "icewine-cachyos-fish", "icewine-sddm", "icewine-debug", "icewine-cachyos-fish-debug"):
        print(str(Path.cwd() / "packages with spaces" / (name + "-0.1-1-x86_64.pkg.tar.zst")))
elif name == "sudo" and args[:2] == ["install", "-Dm644"]:
    Path(os.environ["INSTALL_TEST_SDDM"]).write_text(Path(args[-2]).read_text())
elif name == "sudo" and args == ["systemctl", "enable", "sddm.service"] and os.environ.get("INSTALL_TEST_ENABLE_FAIL"):
    sys.exit(1)
elif name == "sudo" and args[:2] == ["pacman", "-R"] and os.environ.get("INSTALL_TEST_REMOVE_FAIL"):
    sys.exit(1)
elif name == "sudo" and args[1] == "-Syu" and os.environ.get("INSTALL_TEST_FAIL"):
    sys.exit(1)
''')
    fake.chmod(0o755)
    for name in ("id", "python", "git", "makepkg", "sudo", "icewine", "pacman"):
        (commands / name).symlink_to(fake)
    env = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ["PATH"],
               INSTALL_TEST_LOG=str(log), INSTALL_TEST_GIT=shutil.which("git"),
               INSTALL_TEST_SOURCE=str(source), INSTALL_TEST_SDDM=str(root / "sddm.conf"))
    for distro, expected in (("arch", ["icewine", "icewine-sddm"]),
                             ("cachyos", ["icewine", "icewine-cachyos-fish", "icewine-sddm"])):
        log.unlink(missing_ok=True)
        result = subprocess.run(["bash", str(checkout / "install.sh")],
                                env=dict(env, INSTALL_TEST_DISTRO=distro), input="1\n", capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        assert ["makepkg", "-sf"] in calls
        install = next(call for call in calls if call[:3] == ["sudo", "pacman", "-U"])
        assert [Path(path).name.removesuffix("-0.1-1-x86_64.pkg.tar.zst") for path in install[3:]] == expected
        directory = ["sudo", "install", "-d", "-m0755", "-o", "1000", "-g", "1000", "/var/lib/icewine/sddm"]
        config = next(call for call in calls if call[:3] == ["sudo", "install", "-Dm644"])
        assert config[-1] == "/etc/sddm.conf.d/90-icewine.conf"
        assert (root / "sddm.conf").read_text() == "[General]\nDisplayServer=x11\nInputMethod=qtvirtualkeyboard\n[Theme]\nCurrent=icewine\n"
        assert calls.index(directory) < calls.index(config) < calls.index(["icewine", "init"])
        assert calls[-2:] == [["sudo", "systemctl", "enable", "sddm.service"],
                              ["sudo", "systemctl", "set-default", "graphical.target"]]
        assert not Path(install[3]).parent.parent.exists(), "Temporary build directory was retained"
    for choice, wanted, unwanted in (
        ("invalid\n1\n", ["kitty"], ["alacritty"]),
        ("2\n", ["alacritty"], ["kitty"]),
        ("3\n", ["kitty", "alacritty"], []),
        ("4\n", [], ["kitty", "alacritty"]),
    ):
        log.unlink()
        result = subprocess.run(["bash", str(checkout / "install.sh")],
                                env=dict(env, INSTALL_TEST_DISTRO="cachyos",
                                         INSTALL_TEST_TERMINALS="kitty alacritty"),
                                input=choice, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        installs = [call for call in calls if call[:4] == ["sudo", "pacman", "-S", "--needed"]]
        removals = [call for call in calls if call[:3] == ["sudo", "pacman", "-R"]]
        assert installs == ([["sudo", "pacman", "-S", "--needed", *wanted]] if wanted else [])
        assert removals == ([["sudo", "pacman", "-R", *unwanted]] if unwanted else [])
    log.unlink()
    result = subprocess.run(["bash", str(checkout / "install.sh")],
                            env=dict(env, INSTALL_TEST_DISTRO="arch"),
                            input="", capture_output=True, text=True)
    assert result.returncode != 0
    assert not any(json.loads(line)[0] == "sudo" for line in log.read_text().splitlines())
    log.unlink()
    result = subprocess.run(["bash", str(checkout / "install.sh")],
                            env=dict(env, INSTALL_TEST_DISTRO="cachyos",
                                     INSTALL_TEST_TERMINALS="alacritty", INSTALL_TEST_REMOVE_FAIL="1"),
                            input="1\n", capture_output=True, text=True)
    assert result.returncode != 0
    assert json.loads(log.read_text().splitlines()[-1]) == ["sudo", "pacman", "-R", "alacritty"]
    for failure in ({"INSTALL_TEST_UID": "0"}, {"INSTALL_TEST_FAIL": "1"}):
        log.unlink()
        result = subprocess.run(["bash", str(checkout / "install.sh")],
                                env=dict(env, INSTALL_TEST_DISTRO="cachyos", **failure), input="1\n", capture_output=True, text=True)
        assert result.returncode != 0
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        assert not any(call[0] in ("git", "makepkg", "icewine") for call in calls)
    log.unlink()
    result = subprocess.run(["bash", str(checkout / "install.sh")],
                            env=dict(env, INSTALL_TEST_DISTRO="cachyos", INSTALL_TEST_ENABLE_FAIL="1"),
                            input="1\n", capture_output=True, text=True)
    assert result.returncode != 0
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert calls[-1] == ["sudo", "systemctl", "enable", "sddm.service"]
print("PASS: Arch/CachyOS selection, SDDM setup, cleanup and failure handling")
