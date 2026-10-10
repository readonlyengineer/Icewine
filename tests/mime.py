#!/usr/bin/env python3
"""Exercise real generic XDG tools and the real Apply boundary in an isolated home."""
import importlib.machinery
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
from unittest.mock import patch

source, mime_tool, open_tool, terminal_tool, default_file = map(Path, sys.argv[1:])
source = source.resolve()
manage = types.ModuleType("mime_manage")
manage.__file__ = str(source / "scripts/manage")
importlib.machinery.SourceFileLoader(manage.__name__, manage.__file__).exec_module(manage)
with tempfile.TemporaryDirectory(prefix="icewine mime with spaces ") as directory:
    root = Path(directory)
    config, data, packages, commands = (root / name for name in ("config", "data", "packages", "bin"))
    for path in (config, data / "applications", packages / "applications", commands):
        path.mkdir(parents=True)
    defaults = root / "defaults"
    for name in ("config", "data"):
        (defaults / name).mkdir(parents=True)
    log = root / "terminal.json"
    recorder = commands / "host-terminal"
    recorder.write_text(f"#!{sys.executable}\nimport json,sys\nfrom pathlib import Path\nPath({str(log)!r}).write_text(json.dumps(sys.argv[1:]))\n")
    recorder.chmod(0o755)
    (commands / "xdg-terminal-exec").symlink_to(terminal_tool.resolve())
    yazi = commands / "yazi"
    yazi.write_text("#!/bin/sh\nexit 0\n")
    yazi.chmod(0o755)
    (packages / "applications/host-terminal.desktop").write_text("[Desktop Entry]\nType=Application\nName=Host terminal\nExec=host-terminal\nTerminal=false\nCategories=TerminalEmulator;\nTerminalArgExec=-e\n")
    shutil.copyfile(source / "packaging/arch/icewine-yazi.desktop", packages / "applications/icewine-yazi.desktop")
    shutil.copyfile(default_file, packages / "applications/mimeapps.list")
    (config / "xdg-terminals.list").write_text("host-terminal.desktop\n")
    hm = root / "home-manager-mimeapps.list"
    hm.write_text("[Default Applications]\nimage/png=imv.desktop;\n")
    (config / "mimeapps.list").symlink_to(hm)
    selected = dict.fromkeys(manage.FEATURES, False) | {"steam": "none", "filemanager": True}
    env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(config), XDG_DATA_HOME=str(data),
               XDG_STATE_HOME=str(root / "state"), XDG_CACHE_HOME=str(root / "cache"),
               XDG_DATA_DIRS=str(packages), XDG_CONFIG_DIRS=str(root / "empty"),
               XDG_CURRENT_DESKTOP="Icewine:Hyprland", DISPLAY=":123", DE="generic",
               ICEWINE_DEFAULT_FILES=str(defaults), ICEWINE_THEME_ASSETS=str(source / "theme/assets"),
               ICEWINE_THEME_POLICY="", ICEWINE_MANAGE_SELECTIONS=json.dumps(selected),
               PATH=str(commands) + ":" + os.environ["PATH"], NIXOS_XDG_OPEN_USE_PORTAL="")
    before = hm.read_bytes()
    with patch.dict(os.environ, env):
        for overwrite in (False, True, True):
            manage.main(["apply", *[f"{name}={str(value).lower()}" for name, value in selected.items()],
                         "overwrite=" + str(overwrite).lower()])
            assert (config / "mimeapps.list").is_symlink() and hm.read_bytes() == before
    def run(tool, *args):
        result = subprocess.run([str(tool), *args], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr + result.stdout
        return result.stdout.strip()
    assert run(mime_tool, "query", "default", "inode/directory") == "icewine-yazi.desktop"
    target = root / "directory with spaces"
    target.mkdir()
    run(open_tool, str(target))
    assert json.loads(log.read_text()) == ["-e", "yazi", str(target)]
    # Confirm the target writer actually follows symlinks, not just a subprocess mock.
    run(mime_tool, "default", "icewine-yazi.desktop", "inode/directory")
    assert (config / "mimeapps.list").is_symlink()
    assert b"inode/directory=icewine-yazi.desktop" in hm.read_bytes()
    # Arch Apply writes a mutable user MIME file; disabled integration never rewrites it.
    (config / "mimeapps.list").unlink()
    (config / "mimeapps.list").write_text("[Default Applications]\nimage/png=imv.desktop;\n")
    env.pop("ICEWINE_MANAGE_SELECTIONS")
    real_run = manage.run
    def host_boundary(argv):
        if argv[:2] != ["sudo", "pacman"]:
            real_run([str(mime_tool), *argv[1:]] if argv[0] == "xdg-mime" else argv)
    with patch.dict(os.environ, env, clear=True), patch.object(manage.platform, "freedesktop_os_release", return_value={"ID": "arch"}), patch.object(manage, "run", side_effect=host_boundary):
        manage.main(["apply", *[f"{name}={str(value).lower()}" for name, value in selected.items()], "overwrite=false"])
        saved = (config / "mimeapps.list").read_bytes()
        selected["filemanager"] = False
        manage.main(["apply", *[f"{name}={str(value).lower()}" for name, value in selected.items()], "overwrite=false"])
        assert (config / "mimeapps.list").read_bytes() == saved
print("PASS: real MIME ownership, per-user fallback, host terminal, spaced directory and Arch opt-out")
