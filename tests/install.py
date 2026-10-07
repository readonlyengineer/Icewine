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
elif name == "python": print(os.environ["INSTALL_TEST_DISTRO"])
elif name == "git":
    os.execv(os.environ["INSTALL_TEST_GIT"], ["git", "-C", os.environ["INSTALL_TEST_SOURCE"], *args])
elif name == "makepkg" and args == ["-sf"]:
    assert Path("PKGBUILD").is_file() and Path("icewine.tar.gz").is_file()
elif name == "makepkg" and args == ["--packagelist"]:
    for name in ("icewine", "icewine-cachyos-fish", "icewine-sddm", "icewine-debug", "icewine-cachyos-fish-debug"):
        print(str(Path.cwd() / "packages with spaces" / (name + "-0.1-1-x86_64.pkg.tar.zst")))
elif name == "sudo" and args[1] == "-Syu" and os.environ.get("INSTALL_TEST_FAIL"):
    sys.exit(1)
''')
    fake.chmod(0o755)
    for name in ("id", "python", "git", "makepkg", "sudo", "icewine"):
        (commands / name).symlink_to(fake)
    env = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ["PATH"],
               INSTALL_TEST_LOG=str(log), INSTALL_TEST_GIT=shutil.which("git"),
               INSTALL_TEST_SOURCE=str(source))
    for distro, expected in (("arch", ["icewine"]), ("cachyos", ["icewine", "icewine-cachyos-fish"])):
        log.unlink(missing_ok=True)
        result = subprocess.run(["bash", str(checkout / "install.sh")],
                                env=dict(env, INSTALL_TEST_DISTRO=distro), capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        assert ["makepkg", "-sf"] in calls
        install = next(call for call in calls if call[:3] == ["sudo", "pacman", "-U"])
        assert [Path(path).name.removesuffix("-0.1-1-x86_64.pkg.tar.zst") for path in install[3:]] == expected
        assert calls[-1] == ["icewine", "init"]
        assert not Path(install[3]).parent.parent.exists(), "Temporary build directory was retained"
    for failure in ({"INSTALL_TEST_UID": "0"}, {"INSTALL_TEST_FAIL": "1"}):
        log.unlink()
        result = subprocess.run(["bash", str(checkout / "install.sh")],
                                env=dict(env, INSTALL_TEST_DISTRO="cachyos", **failure), capture_output=True, text=True)
        assert result.returncode != 0
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        assert not any(call[0] in ("git", "makepkg", "icewine") for call in calls)
print("PASS: Arch/CachyOS selection, literal paths, cleanup and failure-before-build")
