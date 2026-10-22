#!/usr/bin/env python3
"""Check the real login preflight against isolated systemd/pacman state."""
import importlib.machinery
from pathlib import Path
import subprocess
import sys
import tempfile
import types
from unittest.mock import patch

source = Path(sys.argv[1]).resolve()
manage = types.ModuleType("icewine_manage")
manage.__file__ = str(source / "scripts/manage")
importlib.machinery.SourceFileLoader(manage.__name__, manage.__file__).exec_module(manage)

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    etc = root / "etc/systemd/system"
    run_dir = root / "run/systemd/system"
    usr = root / "usr/lib/systemd/system"
    for directory in (etc, run_dir, usr):
        directory.mkdir(parents=True)
    (usr / "greetd.service").write_text("[Service]\n")
    installed = set()
    active = set()
    calls = []

    def host_path(value):
        return root / str(value).lstrip("/")

    def command(argv, **kwargs):
        calls.append(argv)
        if argv[:2] == ["pacman", "-Qq"]:
            return subprocess.CompletedProcess(argv, 0 if argv[2] in installed else 1)
        if argv[:3] == ["systemctl", "is-active", "--quiet"]:
            return subprocess.CompletedProcess(argv, 0 if argv[3] in active else 3)
        raise AssertionError(argv)

    def check(ok):
        calls.clear()
        try:
            manage.onboarding_login()
        except ValueError:
            assert not ok
        else:
            assert ok

    with patch.object(manage, "Path", side_effect=host_path), patch.object(manage.subprocess, "run", side_effect=command):
        check(True)
        installed.add("greetd")
        check(False)
        installed.clear()
        active.add("display-manager.service")
        check(False)
        active.clear()
        (etc / "greetd.service.d").mkdir()
        check(False)
        (etc / "greetd.service.d").rmdir()
        (etc / "display-manager.service").symlink_to(usr / "greetd.service")
        check(False)
        installed.add("icewine-login")
        check(True)
        (etc / "display-manager.service").unlink()
        (etc / "display-manager.service").symlink_to(usr / "other.service")
        check(False)
print("PASS: fresh/retry login preflight and competing login/override refusal")
