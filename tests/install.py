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
    btop_default = defaults / "config/btop/btop.conf"
    btop_default.parent.mkdir(parents=True)
    btop_default.write_bytes((source / "theme/assets/templates/btop.conf").read_bytes())
    (defaults / "config/hypr/icewine").symlink_to(source / "hyprland")
    (defaults / "config/quickshell/icewine").symlink_to(source / "quickshell")
    (defaults / "data/wallpapers").mkdir()
    (defaults / "data/wallpapers/default.jpg").write_bytes(b"\xff\xd8binary wallpaper")
    config, data, state = (root / name for name in ("config", "data", "state/icewine"))
    env = dict(HOME=str(root), XDG_CONFIG_HOME=str(config), XDG_DATA_HOME=str(data),
               XDG_STATE_HOME=str(state.parent), ICEWINE_DEFAULT_FILES=str(defaults),
               ICEWINE_THEME_ASSETS=str(source / "theme/assets"), ICEWINE_THEME_POLICY="")
    false = dict.fromkeys(manage.FEATURES, False) | {"steam": "none"}
    def apply(features=(), overwrite=False, readonly=False, steam="none"):
        selected = {name: name in features for name in manage.FEATURES} | {"steam": steam}
        extra = {"ICEWINE_MANAGE_SELECTIONS": json.dumps(selected)} if readonly else {}
        with patch.dict(os.environ, dict(env, **extra)), patch.object(manage.platform, "freedesktop_os_release", return_value={"ID": "arch"}):
            manage.main(["apply", *[f"{name}={str(bit).lower()}" for name, bit in reversed(list(selected.items()))], f"overwrite={str(overwrite).lower()}"])
        return selected
    # Invalid named requests fail before any filesystem or package operation.
    valid = [f"{name}={"none" if name == "steam" else "false"}" for name in manage.FEATURES] + ["overwrite=false"]
    with patch.dict(os.environ, env), patch.object(manage.platform, "freedesktop_os_release", return_value={"ID": "arch"}), patch.object(manage, "apply", side_effect=AssertionError("invalid request applied")):
        for request in (valid + ["terminal=true"], valid + ["unknown=false"], valid + ["texteditor=true"],
                        valid[1:], valid[:-1], ["terminal=1", *valid[1:]]):
            try:
                manage.main(["apply", *request])
            except ValueError:
                pass
            else:
                raise AssertionError(f"Accepted invalid request: {request}")
        assert not state.exists()
    # Widgets save independently: no packages, services, dotfile deployment or
    # utility/appearance writes. Stale drafts and failed writes cannot win.
    widget_config, widget_saved = root / "widgets/config", root / "widgets/state/icewine"
    settings = widget_config / "quickshell/config/Settings.qml"
    settings.parent.mkdir(parents=True)
    settings.write_bytes((source / "quickshell/config/Settings.qml").read_bytes())
    entry = widget_config / "quickshell/shell.qml"
    entry.write_bytes((source / "quickshell/shell.qml").read_bytes())
    widget_env = env | {"ICEWINE_WIDGET_SHELLS": str(source / "quickshell/shell.qml"), "XDG_CONFIG_HOME": str(widget_config), "XDG_STATE_HOME": str(widget_saved.parent), "ICEWINE_WIDGET_SETTINGS": str(source / "quickshell/config/Settings.qml"),
                        "ICEWINE_WIDGET_POLICY": "{}"}
    with patch.dict(os.environ, widget_env), patch.object(manage.platform, "freedesktop_os_release", return_value={"ID": "arch"}), \
            patch.object(manage.subprocess, "run", side_effect=AssertionError("widget save ran host command")):
        def widget_status():
            with contextlib.redirect_stdout(io.StringIO()) as output:
                manage.main(["widgets-state"])
            return dict(field.split("=") for field in output.getvalue().split())
        def save_widgets(revision, toasts="false", switcher="false"):
            manage.main(["widgets-apply", "revision=" + revision,
                         "notificationToasts=" + toasts, "windowSwitcher=" + switcher])
        initial = widget_status()
        assert initial["supported"] == "true"
        assert initial["notificationToasts"] == initial["windowSwitcher"] == "true:user"
        # Do not save yet: widget_saved remains absent (Cancel's backend contract).
        assert not (widget_saved / "widgets.json").exists()
        # A draft loaded while absent must not overwrite malformed empty state.
        widget_saved.mkdir(parents=True, exist_ok=True)
        (widget_saved / "widgets.json").write_bytes(b"")
        try: save_widgets(initial["revision"])
        except json.JSONDecodeError: pass
        else: raise AssertionError("accepted present-empty widget state")
        assert (widget_saved / "widgets.json").read_bytes() == b""
        (widget_saved / "widgets.json").unlink()
        save_widgets(initial["revision"])
        assert widget_status()["windowSwitcher"] == "false:user"
        before = (widget_saved / "widgets.json").read_bytes()
        for request in (
                lambda: save_widgets(initial["revision"], "true"),
                lambda: manage.main(["widgets-apply", "revision=" + widget_status()["revision"], "unknown=false", "windowSwitcher=false"])):
            try: request()
            except ValueError: pass
            else: raise AssertionError("accepted stale/invalid widget save")
            assert (widget_saved / "widgets.json").read_bytes() == before
        with patch.dict(os.environ, {"ICEWINE_WIDGET_POLICY": '{"notificationToasts":true,"windowSwitcher":null}'}):
            assert widget_status()["notificationToasts"] == "true:policy"
            try: save_widgets(widget_status()["revision"])
            except ValueError: pass
            else: raise AssertionError("mutable widget_saved overrode Nix policy")
            save_widgets(widget_status()["revision"], "true", "true")
            assert json.loads((widget_saved / "widgets.json").read_text()) == {"notificationToasts": False, "windowSwitcher": True}
        before = (widget_saved / "widgets.json").read_bytes()
        with patch.object(manage.theme, "atomic_text", side_effect=PermissionError("fixture save denied")):
            try: save_widgets(widget_status()["revision"], "true", "true")
            except PermissionError: pass
            else: raise AssertionError("failed widget save reported success")
        assert (widget_saved / "widgets.json").read_bytes() == before
        settings.write_text("// user custom settings\n")
        assert widget_status()["supported"] == "false"
        try: save_widgets(widget_status()["revision"])
        except ValueError: pass
        else: raise AssertionError("custom settings promised live delivery")
        settings.write_bytes((source / "quickshell/config/Settings.qml").read_bytes())
        (widget_saved / "widgets.json").write_text('{"windowSwitcher":"false"}')
        try: widget_status()
        except ValueError: pass
        else: raise AssertionError("accepted malformed widget preference")
        (widget_saved / "widgets.json").unlink()
        (widget_saved / "widgets.json").symlink_to(root / "other.json")
        assert widget_status()["windowSwitcher"] == "true:symlink"
        try: save_widgets(widget_status()["revision"])
        except ValueError as error: assert "read-only symlink" in str(error)
        else: raise AssertionError("replaced dangling widget link")
        assert (widget_saved / "widgets.json").is_symlink() and not (root / "other.json").exists()
        (root / "other.json").write_text('{"windowSwitcher":false}')
        assert widget_status()["windowSwitcher"] == "false:symlink"
        try: save_widgets(widget_status()["revision"])
        except ValueError: pass
        else: raise AssertionError("replaced declarative widget preferences")
        assert (root / "other.json").read_text() == '{"windowSwitcher":false}'
        (widget_saved / "widgets.json").unlink()
        # Widget saves do not depend on host package support or utility state.
        with patch.object(manage.platform, "freedesktop_os_release", return_value={"ID": "nixos"}):
            save_widgets(widget_status()["revision"])
            assert widget_status()["windowSwitcher"] == "false:user"
        outside_state = root / "outside-widget-state"
        widget_saved.rename(outside_state)
        widget_saved.symlink_to(outside_state)
        before = (outside_state / "widgets.json").read_bytes()
        assert widget_status()["windowSwitcher"] == "false:symlink"
        try: save_widgets(widget_status()["revision"], "true", "true")
        except ValueError: pass
        else: raise AssertionError("saved widgets through linked state directory")
        assert (outside_state / "widgets.json").read_bytes() == before
        widget_saved.unlink()
        outside_state.rename(widget_saved)
        # A linked theme locks only that appearance action; queries never write.
        (widget_saved / "theme").symlink_to(root / "absent-declared-theme")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            manage.main(["file-state"])
        assert dict(field.split("=") for field in output.getvalue().split()) == {
            "theme": "true", "transparency": "false", "wallpaper": "false", "monitors": "false", "layout": "false"}
        # Backend host policy cannot be bypassed by directly invoking Apply.
        with patch.object(manage.platform, "freedesktop_os_release", return_value={"ID": "nixos"}):
            try: manage.apply(false, False, False, false, widget_config, data, widget_saved)
            except ValueError as error: assert "Arch/CachyOS" in str(error)
            else: raise AssertionError("NixOS reached native package operations")
    if sys.argv[2:] == ["--widgets-only"]:
        print("PASS: focused widget state/Save, absent versus empty, failed-write preservation and policy")
        sys.exit(0)



    # Merely querying state does not even create the state directory.
    with patch.dict(os.environ, env), patch.object(manage.platform, "freedesktop_os_release", return_value={"ID": "arch"}), patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as commands:
        manage.main(["state"])
        assert not state.exists() and not commands.called
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as commands:
        apply()
        assert not commands.called
    assert (config / "quickshell/icewine").is_symlink()
    assert not (config / "hypr").exists() and not (config / "kitty").exists()
    assert not (config / "btop").exists()
    # Local split packages bootstrap from archives with literal spaced paths;
    # signatures are not mistaken for a second archive.
    archives = root / "package archives"
    archives.mkdir()
    session_archive = archives / "icewine-session-0.1-1-x86_64.pkg.tar.zst"
    (archives / "icewine-session-0.1-1-x86_64.pkg.tar.zst.sig").touch()
    widget_preferences = state / "widgets.json"
    widget_preferences.write_text('{"notificationToasts":false,"windowSwitcher":true}\n')
    saved_widget_preferences = widget_preferences.read_bytes()
    # Commit B retains 0.1-1: an installed commit A must not skip the new archive.
    session_archive.write_bytes(b"prepared commit B, same package version")
    with patch.dict(os.environ, ICEWINE_PACKAGE_DIR=str(archives)), patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as commands:
        apply(("desktop",))
        assert [call.args[0] for call in commands.call_args_list] == [
            ["sudo", "pacman", "-U", str(session_archive)]]
        assert widget_preferences.read_bytes() == saved_widget_preferences
    # A prepared directory need not supply unrelated/private dependency archives.
    with patch.dict(os.environ, ICEWINE_PACKAGE_DIR=str(archives), ICEWINE_HANDHELD_DEFAULT_FILES=str(defaults)), \
         patch.object(manage, "handheld_policy"), patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as commands:
        apply(("desktop", "gamescope", "handheld"), steam="native")
        calls = [call.args[0] for call in commands.call_args_list]
        assert ["sudo", "pacman", "-U", str(session_archive)] in calls
        assert not any(call[:3] == ["sudo", "pacman", "-S"] and "icewine-keyboard" in call for call in calls)
    with patch.dict(os.environ, ICEWINE_PACKAGE_DIR=str(archives), ICEWINE_HANDHELD_DEFAULT_FILES=str(defaults)), \
         patch.object(manage, "handheld_policy"), patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)) as commands:
        apply(("desktop", "gamescope", "handheld"), steam="native")
        calls = [call.args[0] for call in commands.call_args_list]
        transaction = next(call for call in calls if call[:3] == ["sudo", "pacman", "-S"])
        assert {"icewine-handheld", "icewine-controller-idle"} <= set(transaction[4:])
        assert "icewine-keyboard" not in transaction
        assert ["sudo", "pacman", "-U", str(session_archive)] in calls
    # Without prepared archives, retain installed checks/repository acquisition.
    with patch.dict(os.environ, ICEWINE_PACKAGE_DIR=""), patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)) as commands:
        apply(("desktop",))
        assert ["sudo", "pacman", "-S", "--needed", "icewine-session"] in [call.args[0] for call in commands.call_args_list]
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
        assert dict(field.split("=") for field in saved.getvalue().split()) == (
            dict.fromkeys(manage.FEATURES, "false") | {"steam": "none", "readonly": "false", "terminal": "true"})
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
        assert kitty.is_symlink() and kitty.read_text() == "keep me\n"
        assert target.read_text() == "keep me\n"
        # An edited deselected entry remains; untouched Icewine files retire.
        kitty.unlink()
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
    for client, gamescope in [("none", False), ("native", False), ("native", True), ("flatpak", True)]:
        with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as commands:
            apply(("gamescope",) if gamescope else (), steam=client)
        calls = [call.args[0] for call in commands.call_args_list]
        packages = [package for call in calls if call[:4] == ["sudo", "pacman", "-S", "--needed"] for package in call[4:]]
        assert ("steam" in packages) == (client == "native")
        assert any(call[:2] == ["flatpak", "install"] for call in calls) == (client == "flatpak")
        assert ("gamescope" in packages) == gamescope
        assert "bazaar" not in packages
        assert (data / "applications/steam-gamescope.desktop").exists() == gamescope
        assert not any("-R" in call or "uninstall" in call for call in calls)
    # Handheld transitions stop the live shell, idle/OSK/routing before policy
    # removal. Failure cannot persist a successful new selection.
    handheld = false | {"desktop": True, "steam": "native", "gamescope": True, "handheld": True}
    (state / "manage.json").write_text(json.dumps(handheld))
    (state / "applied.json").write_text(json.dumps(handheld))
    events = []
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)), \
         patch.object(manage, "run", side_effect=lambda argv: events.append(argv)), \
         patch.object(manage, "handheld_policy", side_effect=lambda *args: events.append(["policy", args[-1]])):
        apply()
    assert events.index(["systemctl", "--user", "stop", "icewine.service"]) < events.index(["systemctl", "--user", "disable", "--now", *manage.HANDHELD_UNITS]) < events.index(["policy", False])
    before = (state / "manage.json").read_bytes()
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)), \
         patch.object(manage, "run", side_effect=lambda argv: (_ for _ in ()).throw(subprocess.CalledProcessError(1, argv)) if "daemon-reload" in argv else None):
        try:
            apply(steam="native")
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError("Failed runtime transition reported success")
    assert (state / "manage.json").read_bytes() == before
    # Exercise the real native Steam wrapper during shell restart, while the
    # successful selection on disk still intentionally describes the old client.
    original_run = subprocess.run
    wrapper_bin = root / "restart-bin"
    wrapper_bin.mkdir()
    (wrapper_bin / "icewine-steam").symlink_to(source / "packaging/arch/command")
    client_log = root / "restart-client.json"
    fake_client = wrapper_bin / "steam"
    fake_client.write_text("#!" + sys.executable + "\nimport json,sys; open(" + repr(str(client_log)) + ", 'w').write(json.dumps(sys.argv[1:]))\n")
    fake_client.chmod(0o755)
    backend = wrapper_bin / "icewine-manage-backend"
    backend.write_text("#!" + sys.executable + "\nimport json; print(' '.join(k+'='+str(v).lower() for k,v in json.load(open(" + repr(str(state / "manage.json")) + ")).items()))\n")
    backend.chmod(0o755)
    session = {}
    def restart(argv):
        if argv[:3] == ["systemctl", "--user", "set-environment"]:
            session.update(field.split("=", 1) for field in argv[3:])
        if argv == ["systemctl", "--user", "start", "icewine.service"]:
            assert json.loads((state / "manage.json").read_text())["steam"] == "none"
            result = original_run(["bash", str(wrapper_bin / "icewine-steam"), "literal argument"],
                                  env=os.environ | session | {"PATH": str(wrapper_bin) + ":" + os.environ["PATH"]}, capture_output=True, text=True)
            assert result.returncode == 0, result.stderr
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)), patch.object(manage, "run", side_effect=restart):
        apply(steam="native")
    assert json.loads(client_log.read_text()) == ["literal argument"]
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
        apply()
    # A real policy install is simulated in a private path. The idle-helper failure
    # leaves no enabled/running helpers or owned policy; a following none Apply
    # retains those actual clean outcomes rather than merely preserving JSON.
    rules = root / "failure-handheld.rules"
    enabled, running = set(), set()
    session.clear()
    def fail_handheld_start(argv):
        if argv[:3] == ["sudo", "install", "-Dm644"]:
            shutil.copyfile(argv[3], argv[4])
        elif argv[:2] == ["sudo", "unlink"]:
            Path(argv[2]).unlink()
        elif argv[:3] == ["systemctl", "--user", "set-environment"]:
            session.update(field.split("=", 1) for field in argv[3:])
        elif argv[:3] == ["systemctl", "--user", "enable"]:
            enabled.update(argv[3:])
        elif argv[:4] == ["systemctl", "--user", "disable", "--now"]:
            enabled.difference_update(argv[4:]); running.difference_update(argv[4:])
        elif argv[:3] == ["systemctl", "--user", "start"] and "icewine-controller-idle.service" in argv:
            running.add("icewine-inputplumber-hyprland.service")
            raise subprocess.CalledProcessError(1, argv)
    with patch.object(manage, "HANDHELD_RULES", rules), \
         patch.dict(os.environ, ICEWINE_INPUTPLUMBER_ASSETS=str(source / "inputplumber"), ICEWINE_HANDHELD_DEFAULT_FILES=str(defaults)), \
         patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)), \
         patch.object(manage, "run", side_effect=fail_handheld_start):
        try:
            apply(("desktop", "gamescope", "handheld"), steam="native")
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError("Failed idle-helper start reported success")
        assert not enabled and not running and not rules.exists()
        assert not (state / "handheld-rules.sha256").exists()
        assert session["ICEWINE_STEAM_CLIENT"] == "none"
        assert session["ICEWINE_HANDHELD_ENABLED"] == "false"
        assert session["ICEWINE_GAMESCOPE_ENABLED"] == "false"
        assert json.loads((state / "manage.json").read_text()) == false
        apply()
        assert not enabled and not running and not rules.exists()
    # If systemd cannot stop the helpers, retain their permission for restore;
    # the ownership record makes a later none Apply retry actual teardown.
    fail_stop = True
    def interrupted_teardown(argv):
        if fail_stop and argv[:4] == ["systemctl", "--user", "disable", "--now"]:
            raise subprocess.CalledProcessError(1, argv)
        fail_handheld_start(argv)
    with patch.object(manage, "HANDHELD_RULES", rules), \
         patch.dict(os.environ, ICEWINE_INPUTPLUMBER_ASSETS=str(source / "inputplumber"), ICEWINE_HANDHELD_DEFAULT_FILES=str(defaults)), \
         patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)), \
         patch.object(manage, "run", side_effect=interrupted_teardown):
        try:
            apply(("desktop", "gamescope", "handheld"), steam="native")
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError("Failed helper transition reported success")
        assert enabled and running and rules.exists()
        assert (state / "handheld-rules.sha256").exists()
        fail_stop = False
        apply()
        assert not enabled and not running and not rules.exists()
        assert not (state / "handheld-rules.sha256").exists()
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
        apply(("desktop",), overwrite=True)
    assert locale.is_symlink() and target.read_text() == "keep me\n"
    locale.unlink()
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
        apply()
    before = (state / "manage.json").read_bytes()
    with patch.object(manage.subprocess, "run", side_effect=subprocess.CalledProcessError(1, ["pacman"])):
        try:
            apply(("terminal",))
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError("Failed install reported success")
    assert (state / "manage.json").read_bytes() == before
    assert not (config / "nano/nanorc").exists()
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as commands:
        apply(("filemanager",))
        assert commands.call_args_list[-1].args[0] == ["xdg-mime", "default", "icewine-yazi.desktop", "inode/directory"]
        assert commands.call_args_list[-1].kwargs["env"]["XDG_CURRENT_DESKTOP"] == "X-Generic"
    mime_source = root / "home-manager-mimeapps.list"
    mime_source.write_text("[Default Applications]\nimage/png=imv.desktop;\n")
    mime = config / "mimeapps.list"
    mime.symlink_to(mime_source)
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as commands:
        apply(("filemanager",))
        assert not any(call.args[0][0] == "xdg-mime" for call in commands.call_args_list)
        commands.reset_mock()
        apply(("filemanager", "shellExtras"), readonly=True)
        assert not commands.called
        assert not (config / "nano/nanorc").exists()
        assert not (root / ".bashrc").exists()
        assert (config / "yazi/theme.toml").is_symlink()
        (defaults / "config/yazi/yazi.toml").write_text("updated yazi\n")
        apply(("filemanager", "shellExtras"), readonly=True)
        assert (config / "yazi/yazi.toml").read_text() == "yazi\n"
        apply(("filemanager", "shellExtras"), overwrite=True, readonly=True)
        assert (config / "yazi/yazi.toml").read_text() == "updated yazi\n"
        assert mime.is_symlink() and mime.resolve() == mime_source
        assert mime_source.read_text() == "[Default Applications]\nimage/png=imv.desktop;\n"
        commands.reset_mock()
        apply(("shellExtras",), overwrite=True, readonly=True)
        assert not commands.called
        assert not (config / "yazi/theme.toml").is_symlink()
        (root / ".bashrc").write_text("user shell\n")
        apply(("shellExtras",), overwrite=True, readonly=True)
        assert (root / ".bashrc").read_text() == "user shell\n"
    # Shell Extras uses the same editable-default/link/retirement ownership path.
    btop = config / "btop/btop.conf"
    btop_link = config / "btop/themes/icewine.theme"
    assert btop.read_bytes() == btop_default.read_bytes()
    assert btop_link.is_symlink() and btop_link.resolve() == (config / "icewine/current/btop.theme").resolve()
    preferences = btop.read_text() + "update_ms = 500\nvim_keys = true\n"
    btop.write_text(preferences)
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
        # An existing default/custom selection must change on explicit Apply only.
        for existing, expected in (
            ('# color_theme = "Default"\ncolor_theme = "Default"\n',
             '# color_theme = "Default"\ncolor_theme = "icewine"\nupdate_ms = 500\nvim_keys = true'),
            ('color_theme="custom"\ncolor_theme = "Default"\n',
             'color_theme="icewine"\ncolor_theme = "icewine"\nupdate_ms = 500\nvim_keys = true'),
            ('', 'update_ms = 500\nvim_keys = true\ncolor_theme = "icewine"\n'),
        ):
            personal = existing + "update_ms = 500\nvim_keys = true"  # No final newline.
            btop.write_text(personal)
            btop.chmod(0o600)
            apply(("shellExtras",), readonly=True)
            selected = btop.read_text()
            assert selected == expected
            assert btop.stat().st_mode & 0o777 == 0o600
            apply(("shellExtras",), readonly=True)
            assert btop.read_text() == selected  # Repeated Apply is stable.
            apply((), readonly=True)
            assert btop.read_text() == selected  # Personal config is never retired.
        personal_config = root / "personal-btop.conf"
        personal_config.write_text('color_theme = "Default"\nupdate_ms = 500\n')
        btop.unlink()
        btop.symlink_to(personal_config)
        apply(("shellExtras",), readonly=True)
        assert btop.is_symlink() and personal_config.read_text() == 'color_theme = "Default"\nupdate_ms = 500\n'
        btop.unlink()
        btop.write_text(preferences)
        apply(("shellExtras",), readonly=True)
        assert btop.read_text() == preferences
        apply(("shellExtras",), overwrite=True, readonly=True)
        assert btop.read_bytes() == btop_default.read_bytes()
        btop.write_text(preferences)
        apply((), readonly=True)
        assert btop.read_text() == preferences and not btop_link.exists() and not btop_link.is_symlink()
        apply(("shellExtras",), readonly=True)
        assert btop.read_text() == preferences and btop_link.is_symlink()
    assert not list((config / "btop").rglob("*.bak*"))
    stable = root / "installed-implementation"
    old, new = root / "old-implementation", root / "new-implementation"
    for directory, text in ((old, "old implementation"), (new, "new implementation")):
        (directory / "hyprland").mkdir(parents=True)
        (directory / "hyprland/icewine.lua").write_text(text)
    stable.symlink_to(old, target_is_directory=True)
    shipped = defaults / "config/hypr/icewine"
    shipped.unlink()
    shipped.symlink_to(stable / "hyprland")
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
        apply(("desktop",), readonly=True)
    entry = config / "hypr/hyprland.lua"
    entry.write_text("user entry\n")
    stable.unlink()
    stable.symlink_to(new, target_is_directory=True)
    assert (config / "hypr/icewine/icewine.lua").read_text() == "new implementation"
    assert entry.read_text() == "user entry\n"

    # Only the exact previous saved schema is accepted, and its editor bit is
    # discarded without changing the remaining utility identities or dotfiles.
    nano = config / "nano/nanorc"
    nano.parent.mkdir()
    nano.write_text("user nano\n")
    (root / ".nanorc").write_text("home nano\n")
    nvim = config / "nvim/init.lua"
    nvim.parent.mkdir()
    nvim.symlink_to(target)
    (defaults / "config/nvim").mkdir()
    (defaults / "config/nvim/init.lua").write_text("obsolete default\n")
    records = manage.theme.default_records(state)
    for path in (nano, nvim):
        records["config"]["files"][str(path.relative_to(config))] = manage.theme.default_signature(path)
    manage.theme.atomic_text(state / "default-files.json", json.dumps(records))
    selected = dict.fromkeys(("desktop", "terminal", "filemanager", "gaming", "flatpak", "login", "shellExtras"), False) | {"terminal": True, "gaming": True, "shellExtras": True}
    migrated = false | {"terminal": True, "steam": "native", "gamescope": True, "shellExtras": True}
    for bit in (False, True):
        legacy = selected | {"texteditor": bit, "login": True}
        for name in ("manage.json", "applied.json"):
            (state / name).write_text(json.dumps(legacy))
        with patch.dict(os.environ, env), patch.object(manage.platform, "freedesktop_os_release", return_value={"ID": "arch"}), contextlib.redirect_stdout(io.StringIO()) as saved:
            manage.main(["state"])
            assert dict(field.split("=") for field in saved.getvalue().split()) == {"readonly": "false", **{name: str(value).lower() for name, value in migrated.items()}}
        assert json.loads((state / "manage.json").read_text()) == legacy
        with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as commands:
            apply(("desktop", "terminal", "filemanager", "gamescope", "shellExtras"), overwrite=True, steam="native")
            assert not any("nano" in call.args[0] for call in commands.call_args_list)
        assert json.loads((state / "manage.json").read_text()) == false | {"desktop": True, "terminal": True, "filemanager": True, "steam": "native", "gamescope": True, "shellExtras": True}
        assert nano.read_text() == "user nano\n" and (root / ".nanorc").read_text() == "home nano\n"
        assert nvim.is_symlink() and nvim.resolve() == target
        assert target.read_text() == "keep me\n"
    for invalid in (selected | {"texteditor": 1}, selected | {"unknown": False},
                    selected | {"texteditor": True, "unknown": False},
                    {name: value for name, value in selected.items() if name != "terminal"}):
        (state / "manage.json").write_text(json.dumps(invalid))
        with patch.dict(os.environ, env), patch.object(manage.platform, "freedesktop_os_release", return_value={"ID": "arch"}):
            try:
                manage.selections(state)
            except ValueError:
                pass
            else:
                raise AssertionError(f"Accepted malformed saved state: {invalid}")
    # Legacy compatibility applies to persisted state only, never current requests.
    with patch.dict(os.environ, dict(env, ICEWINE_MANAGE_SELECTIONS=json.dumps(selected | {"texteditor": True}))):
        try:
            manage.selections(state)
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted obsolete declared selections")
    (state / "manage.json").write_text(json.dumps(false))
    (state / "applied.json").write_text(json.dumps(false))
    with patch.dict(os.environ, dict(env, ICEWINE_MANAGE_SELECTIONS=json.dumps(false))):
        try:
            manage.main(["apply", *[f"{name}={"none" if name == "steam" else str(name == 'desktop').lower()}" for name in manage.FEATURES], "overwrite=false"])
        except ValueError as error:
            assert "read-only" in str(error)
        else:
            raise AssertionError("NixOS choices were editable")
    # Overwrite preserves linked leaves and parents while unrelated files work.
    unrelated = root / "outside kitty"
    unrelated.mkdir()
    (unrelated / "kitty.conf").write_text("outside\n")
    shutil.rmtree(config / "kitty")
    (config / "kitty").symlink_to(unrelated)
    with patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
        apply(("terminal",), overwrite=True)
    assert (unrelated / "kitty.conf").read_text() == "outside\n"
    rules = root / "handheld.rules"
    with patch.object(manage, "HANDHELD_RULES", rules), patch.object(manage, "run") as host, patch.dict(os.environ, ICEWINE_INPUTPLUMBER_ASSETS=str(source / "inputplumber")):
        rules.write_text("unrelated policy\n")
        try:
            manage.handheld_policy(state, True)
        except ValueError:
            pass
        else:
            raise AssertionError("Unrelated handheld policy was overwritten")
        assert not host.called
        rules.unlink()
        manage.handheld_policy(state, True)
        assert host.call_args.args[0][:3] == ["sudo", "install", "-Dm644"]
        rules.write_text("edited user policy\n")
        host.reset_mock()
        manage.handheld_policy(state, False)
        assert not host.called and rules.read_text() == "edited user policy\n"
        rules.write_text("owned policy\n")
        (state / "handheld-rules.sha256").write_text(manage.theme.default_signature(rules))
        manage.handheld_policy(state, False)
        host.assert_called_once_with(["sudo", "unlink", str(rules)])
    with patch.object(manage, "run") as host:
        apply(("login",), readonly=True)
        assert not any(call.args[0][0] == "icewine-wallpaper" for call in host.call_args_list)
        assert (data / "wallpapers/default.jpg").exists()
    with patch.object(manage, "run") as host:
        try:
            apply(("login",), readonly=False)
        except ValueError as error:
            assert "belongs to the host" in str(error)
        else:
            raise AssertionError("Arch Apply accepted retired login integration")
        assert not host.called

# HOME participates in deployment independently of XDG roots.
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    outside = root / "external home"
    outside.mkdir()
    (outside / ".bashrc").write_text("external shell config\n")
    home = root / "home link"
    home.symlink_to(outside)
    declared = dict.fromkeys(manage.FEATURES, False) | {"steam": "none"}
    declared["shellExtras"] = True
    defaults = root / "defaults"
    for name in ("config", "data", "home"):
        (defaults / name).mkdir(parents=True)
    (defaults / "home/.bashrc").write_text("default shell\n")
    env = dict(HOME=str(home), XDG_CONFIG_HOME=str(root / "config"), XDG_DATA_HOME=str(root / "data"),
               XDG_STATE_HOME=str(root / "state"), ICEWINE_MANAGE_SELECTIONS=json.dumps(declared),
               ICEWINE_DEFAULT_FILES=str(defaults), ICEWINE_THEME_ASSETS=str(source / "theme/assets"), ICEWINE_GTK_ENABLE="false")
    with patch.dict(os.environ, env), patch.object(manage.subprocess, "run", side_effect=AssertionError("host operation before root validation")):
        manage.main(["apply", *[f"{name}={str(bit).lower()}" for name, bit in declared.items()], "overwrite=true"])
    assert (outside / ".bashrc").read_text() == "external shell config\n"
    assert (root / "state/icewine/applied.json").is_file()
    assert (root / "config/icewine/current").is_symlink()

# Manager routes unchanged literal arguments.
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    command = root / "icewine-manage"
    command.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
    command.chmod(0o755)
    env = dict(os.environ, PATH=str(root) + ":" + os.environ["PATH"])
    assert subprocess.run(["bash", str(source / "scripts/icewine"), "manage", "literal space"], env=env, capture_output=True, text=True).stdout == "literal space\n"
print("PASS: explicit Apply, selections, ownership, overwrite, failures and read-only NixOS")

