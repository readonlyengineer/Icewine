#!/usr/bin/env python3
"""Exercise explicit Apply with isolated dotfiles and mocked host operations."""
import errno
import contextlib
import io
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

source = Path(sys.argv[1]).resolve()
manage = types.ModuleType("icewine_manage")
manage.__file__ = str(source / "scripts/manage")
importlib.machinery.SourceFileLoader(manage.__name__, manage.__file__).exec_module(manage)

with tempfile.TemporaryDirectory(prefix="icewine manager with spaces ") as temporary:
    root = Path(temporary)
    defaults = root / "defaults"
    for folder in ("config", "data", "home"):
        (defaults / folder).mkdir(parents=True)
    for name, text in {
        "config/quickshell/shell.qml": "shell\n", "config/hypr/hyprland.lua": "hypr\n",
        "config/kitty/kitty.conf": "kitty\n", "config/nano/nanorc": "nano\n",
        "config/yazi/yazi.toml": "yazi\n", "home/.bashrc": "shell extras\n",
        "data/applications/steam-gamescope.desktop": "steam launcher\n",
    }.items():
        path = defaults / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    (defaults / "config/hypr/icewine").symlink_to(source / "hyprland")
    (defaults / "config/quickshell/icewine").symlink_to(source / "quickshell")
    (defaults / "data/wallpapers").mkdir()
    (defaults / "data/wallpapers/default.jpg").write_bytes(b"\xff\xd8binary wallpaper")
    config, data, state = (root / name for name in ("config", "data", "state/icewine"))
    env = dict(HOME=str(root), XDG_CONFIG_HOME=str(config), XDG_DATA_HOME=str(data),
               XDG_STATE_HOME=str(state.parent), ICEWINE_DEFAULT_FILES=str(defaults),
               ICEWINE_THEME_ASSETS=str(source / "theme/assets"), ICEWINE_THEME_POLICY="")
    false = dict.fromkeys(manage.FEATURES, False)
    def apply(features=(), overwrite=False, readonly=False):
        selected = {name: name in features for name in manage.FEATURES}
        extra = {"ICEWINE_MANAGE_SELECTIONS": json.dumps(selected)} if readonly else {}
        with patch.dict(os.environ, dict(env, **extra)), patch.object(manage.platform, "freedesktop_os_release", return_value={"ID": "arch"}):
            manage.main(["apply", *[str(int(selected[name])) for name in manage.FEATURES], str(int(overwrite))])
        return selected
    # Merely querying state does not even create the state directory.
    with patch.dict(os.environ, env), patch.object(manage.platform, "freedesktop_os_release", return_value={"ID": "arch"}), patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as commands:
        manage.main(["state"])
        assert not state.exists() and not commands.called
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as commands:
        apply()
        assert not commands.called
    assert (config / "quickshell/icewine").is_symlink()
    assert not (config / "hypr").exists() and not (config / "kitty").exists()
    # Local split packages bootstrap from archives with literal spaced paths;
    # signatures are not mistaken for a second archive.
    archives = root / "package archives"
    archives.mkdir()
    (archives / "icewine-session-0.1-1-x86_64.pkg.tar.zst").touch()
    (archives / "icewine-session-0.1-1-x86_64.pkg.tar.zst.sig").touch()
    with patch.dict(os.environ, ICEWINE_PACKAGE_DIR=str(archives)), patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)) as commands:
        apply(("desktop",))
        assert [call.args[0] for call in commands.call_args_list] == [
            ["pacman", "-Qq", "icewine-session"],
            ["sudo", "pacman", "-U", "--needed", str(archives / "icewine-session-0.1-1-x86_64.pkg.tar.zst")]]
    # Theme switches maintain runtime GTK artifacts without redeploying dotfiles.
    mocha = data / "themes/Icewine-catppuccin-mocha/gtk-3.0/gtk.css"
    assert mocha.is_file()
    css = config / "gtk-3.0/gtk.css"
    css.parent.mkdir(parents=True, exist_ok=True)
    css.unlink(missing_ok=True)
    css.write_text("user CSS\n")
    with patch.dict(os.environ, dict(env, ICEWINE_GTK_ENABLE="true", WAYLAND_DISPLAY="", DBUS_SESSION_BUS_ADDRESS="", HYPRLAND_INSTANCE_SIGNATURE="")), \
         patch.object(manage.theme, "reload_session", return_value=False), \
         patch.object(manage.theme, "install_flatpak_theme"), patch.object(manage.theme, "sync_gtk_settings", return_value=True):
        assert manage.theme.main(["theme", "dracula"]) == 0
    dracula = data / "themes/Icewine-dracula/gtk-3.0/gtk.css"
    assert dracula.is_file() and dracula.is_symlink()
    assert dracula.resolve() == (config / "icewine/current/gtk3-theme.css").resolve()
    assert css.read_text() == "user CSS\n"
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
        apply()

    assert (data / "wallpapers/default.jpg").read_bytes().startswith(b"\xff\xd8")
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as commands:
        apply(("terminal",))
        assert commands.call_args_list[0].args[0] == ["sudo", "pacman", "-S", "--needed", "kitty"]
    with patch.dict(os.environ, env), patch.object(manage.platform, "freedesktop_os_release", return_value={"ID": "arch"}), contextlib.redirect_stdout(io.StringIO()) as saved:
        manage.main(["state"])
        assert saved.getvalue().strip() == "0 0 1 0 0 0 0 0 0"
    kitty = config / "kitty/kitty.conf"
    kitty.write_text("my edits\n")
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
        apply(("terminal",))
        assert kitty.read_text() == "my edits\n"
        apply(("terminal",), overwrite=True)
        assert kitty.read_text() == "kitty\n"
        assert not list(state.glob("*reset*")) and not list(state.glob("*backup*"))
        target = root / "unrelated"
        target.write_text("keep me\n")
        kitty.unlink()
        kitty.symlink_to(target)
        apply(("terminal",), overwrite=True)
        assert not kitty.is_symlink() and kitty.read_text() == "kitty\n"
        assert target.read_text() == "keep me\n"
        # An edited deselected entry remains; untouched Icewine files retire.
        kitty.write_text("keep user edits\n")
        apply()
        assert kitty.read_text() == "keep user edits\n"
        apply(("terminal",), overwrite=True)
        apply()
        assert not kitty.exists()
        apply(("desktop",))
        apply()
        assert not (config / "hypr/icewine").is_symlink()
        assert (config / "hypr/hyprland.lua").read_text() == "hypr\n"
    with patch.dict(os.environ, ICEWINE_GTK_ENABLE="false"), patch.object(manage.theme, "install_gtk_theme", side_effect=AssertionError("disabled GTK installed")):
        apply(("desktop",), readonly=True)
    for features, steam, flatpak in [(("gaming",), True, False), (("gaming", "flatpak"), False, True), (("flatpak",), False, False)]:
        with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as commands:
            apply(features)
        calls = [call.args[0] for call in commands.call_args_list]
        packages = next(call for call in calls if call[:2] == ["sudo", "pacman"])[4:]
        assert ("steam" in packages) == steam
        assert any(call[:2] == ["flatpak", "install"] for call in calls) == flatpak
        assert ("gamescope" in packages) == ("gaming" in features)
        assert ("bazaar" in packages) == ("flatpak" in features)
        assert not any("-R" in call or "uninstall" in call for call in calls)
    # Host persistence may bind-mount a single file; overwrite must not rely
    # on rename succeeding, and a leaf symlink must never reach its target.
    locale = config / "user-dirs.locale"
    (defaults / "config/user-dirs.locale").write_text("default locale\n")
    locale.write_text("edited locale\n")
    original_replace = manage.theme.os.replace
    def busy(source, destination):
        if destination == locale:
            raise OSError(errno.EBUSY, "bind mount")
        return original_replace(source, destination)
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)), patch.object(manage.theme.os, "replace", side_effect=busy):
        apply(("desktop",), overwrite=True)
    assert locale.read_text() == "default locale\n"
    locale.unlink()
    locale.symlink_to(target)
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)), patch.object(manage.theme.os, "replace", side_effect=busy):
        try:
            apply(("desktop",), overwrite=True)
        except OSError as error:
            assert error.errno == errno.EBUSY
        else:
            raise AssertionError("Busy symlink reached unrelated target")
    assert target.read_text() == "keep me\n"
    locale.unlink()
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
        apply()
    before = (state / "manage.json").read_bytes()
    with patch.object(manage.subprocess, "run", side_effect=subprocess.CalledProcessError(1, ["pacman"])):
        try:
            apply(("texteditor",))
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError("Failed install reported success")
    assert (state / "manage.json").read_bytes() == before
    assert not (config / "nano/nanorc").exists()
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as commands:
        apply(("texteditor", "filemanager", "shellExtras"), readonly=True)
        assert not commands.called
        assert (config / "nano/nanorc").read_text() == "nano\n"
        assert (root / ".bashrc").read_text() == "shell extras\n"
        assert (config / "yazi/theme.toml").is_symlink()
        # Package defaults change; repeated Apply preserves even untouched mutable files.
        (defaults / "config/nano/nanorc").write_text("updated nano\n")
        apply(("texteditor", "filemanager", "shellExtras"), readonly=True)
        assert (config / "nano/nanorc").read_text() == "nano\n"
        apply(("texteditor",), overwrite=True, readonly=True)
        assert (config / "nano/nanorc").read_text() == "updated nano\n"
        assert not (config / "yazi/theme.toml").is_symlink()
    with patch.dict(os.environ, dict(env, ICEWINE_MANAGE_SELECTIONS=json.dumps(false))):
        try:
            manage.main(["apply", "1", *("0" for _ in range(8))])
        except ValueError as error:
            assert "read-only" in str(error)
        else:
            raise AssertionError("NixOS choices were editable")
    # Overwrite may replace a leaf symlink but cannot traverse a symlinked parent.
    unrelated = root / "outside kitty"
    unrelated.mkdir()
    (unrelated / "kitty.conf").write_text("outside\n")
    shutil.rmtree(config / "kitty")
    (config / "kitty").symlink_to(unrelated)
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
        apply(("terminal",), overwrite=True)
    assert (unrelated / "kitty.conf").read_text() == "outside\n"
    login_config = root / "sddm.conf"
    with patch.object(manage, "LOGIN_CONFIG", login_config), patch.object(manage, "run") as host:
        login_config.write_text("unrelated login policy\n")
        try:
            manage.login(state, True)
        except ValueError:
            pass
        else:
            raise AssertionError("Unrelated login policy was overwritten")
        assert not host.called
        login_config.write_text(manage.LOGIN_CONTENTS)
        (state / "login.sha256").write_text(manage.theme.default_signature(login_config))
        manage.login(state, False)
        host.assert_called_once_with(["sudo", "unlink", str(login_config)])
        assert not (state / "login.sha256").exists()

# HOME participates in deployment independently of XDG roots.
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    outside = root / "external home"
    outside.mkdir()
    (outside / ".bashrc").write_text("external shell config\n")
    home = root / "home link"
    home.symlink_to(outside)
    declared = dict.fromkeys(manage.FEATURES, False)
    declared["shellExtras"] = True
    env = dict(HOME=str(home), XDG_CONFIG_HOME=str(root / "config"), XDG_DATA_HOME=str(root / "data"),
               XDG_STATE_HOME=str(root / "state"), ICEWINE_MANAGE_SELECTIONS=json.dumps(declared))
    with patch.dict(os.environ, env), patch.object(manage.subprocess, "run", side_effect=AssertionError("host operation before root validation")):
        try:
            manage.main(["apply", "0", "0", "0", "0", "0", "0", "0", "1", "1"])
        except ValueError as error:
            assert "symlinked deployment root" in str(error)
        else:
            raise AssertionError("Apply followed symlinked HOME")
    assert (outside / ".bashrc").read_text() == "external shell config\n"
    assert not (root / "state").exists() and not (root / "config").exists()

# Public setup entry points are gone; manager routes unchanged literal arguments.
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    command = root / "icewine-manage"
    command.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
    command.chmod(0o755)
    env = dict(os.environ, PATH=str(root) + ":" + os.environ["PATH"])
    for old in ("init", "reset"):
        assert subprocess.run(["bash", str(source / "scripts/icewine"), old], env=env, capture_output=True).returncode == 2
    assert subprocess.run(["bash", str(source / "scripts/icewine"), "manage", "literal space"], env=env, capture_output=True, text=True).stdout == "literal space\n"
print("PASS: explicit Apply, selections, ownership, overwrite, failures and read-only NixOS")

module_options = (source / "modules/default.nix").read_text() + (source / "modules/login.nix").read_text()
for name in manage.FEATURES:
    assert name + ".enable = lib.mkEnableOption" in module_options or name + " = {" in module_options
assert len(manage.FEATURES) == 8
assert "[(&str, &str); 8]" in (source / "manager/src/main.rs").read_text()
print("PASS: utility option parity and local split-package bootstrap")
