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

defaults_only = sys.argv[2:] == ["--defaults-only"]
source = Path(sys.argv[1])
if not defaults_only:
    source, mime_tool, open_tool, terminal_tool, default_file = map(Path, sys.argv[1:])
source = source.resolve()
manage = types.ModuleType("mime_manage")
manage.__file__ = str(source / "scripts/manage")
importlib.machinery.SourceFileLoader(manage.__name__, manage.__file__).exec_module(manage)
def test_default_apps():
    with tempfile.TemporaryDirectory(prefix="icewine default apps ", dir="/tmp") as directory:
        root = Path(directory)
        config, data, system, commands, state = (root / name for name in ("config", "data", "system", "bin", "state"))
        for path in (config, data / "applications", system / "applications", commands):
            path.mkdir(parents=True)
        terminal = commands / "xdg-terminal-exec"
        terminal.write_text(f'#!{sys.executable}\n' + '''import os,sys
from pathlib import Path
assert sys.argv[1:]==["--print-id"]
assert os.environ["XDG_CACHE_HOME"] != os.environ.get("USER_CACHE_EXAMPLE")
chosen=[]
for name in ("icewine-xdg-terminals.list","hyprland-xdg-terminals.list","xdg-terminals.list"):
 path=Path(os.environ["XDG_CONFIG_HOME"])/name
 if path.exists(): chosen += [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.strip().startswith(("#","+","-","/"))]
print(chosen[0] if chosen else "terminal.desktop")
''')
        terminal.chmod(0o755)
        exports = root / "flatpak/exports/share/applications"
        exports.mkdir(parents=True)
        env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(config), XDG_CONFIG_DIRS=str(root / "empty"),
                   XDG_DATA_HOME=str(data), XDG_DATA_DIRS=str(system) + ":" + str(exports.parent), XDG_STATE_HOME=str(state),
                   XDG_CURRENT_DESKTOP="Icewine:Hyprland", XDG_CACHE_HOME=str(root / "user-cache"),
                   USER_CACHE_EXAMPLE=str(root / "user-cache"), PATH=str(commands) + ":" + os.environ["PATH"])
        def entry(identifier, mimes=(), extra="", directory=system / "applications", name=None):
            path = directory / identifier
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("[Desktop Entry]\nType=Application\nName=" + (name or identifier) + "\nExec=never-execute %U\nMimeType=" + ";".join(mimes) + ";\n" + extra)
            return path
        all_mimes = tuple(mime for group in manage.DEFAULT_MIMES for mime in group)
        entry("browser.desktop", all_mimes, name="Browser with spaces Ω")
        entry("org.example.Flatpak.desktop", all_mimes, "NoDisplay=true\n", directory=exports, name="Flatpak browser")
        exported = exports / "org.example.Flatpak.desktop"
        exported.write_text(exported.read_text().replace("Exec=never-execute %U", "Exec=flatpak run --file-forwarding org.example.Flatpak @@u %U @@"))
        exported_bytes = exported.read_bytes()
        entry("terminal.desktop", extra="Categories=TerminalEmulator;\nActions=NewWindow;\n[Desktop Action NewWindow]\nName=New window\nExec=never-execute\n")
        entry("ignored.desktop", all_mimes, "Hidden=true\n")
        entry("tryexec.desktop", all_mimes, "TryExec=/does/not/exist\n")
        entry("nested/app.desktop", ("text/plain",))
        entry("masked.desktop", all_mimes)
        entry("masked.desktop", extra="Hidden=true\n", directory=data / "applications")
        generic = config / "mimeapps.list"
        desktop = config / "icewine-mimeapps.list"
        legacy = data / "applications/mimeapps.list"
        def roles(): return manage.default_apps_state(config, data)
        def apply(index, choice, revision=None):
            manage.main(["default-apps-apply", revision or roles()[index]["revision"], str(index), choice])
        def fails(operation, text):
            try: operation()
            except (ValueError, OSError) as error: assert text in str(error), str(error)
            else: raise AssertionError("Expected failure: " + text)
        with patch.dict(os.environ, env, clear=True):
            with patch.dict(os.environ, XDG_CURRENT_DESKTOP="Icewine:Icewine:Hyprland"):
                paths = manage.default_paths(config, data)
                assert len(paths[1]) == len(set(paths[1])) and len(paths[3]) == len(set(paths[3]))
            initial = roles()
            assert len(initial) == 8 and initial[0]["label"] == "Not set"
            browser_choices = dict(initial[0]["choices"])
            assert browser_choices["org.example.Flatpak.desktop"] == "Flatpak browser"
            assert not {"ignored.desktop", "masked.desktop", "tryexec.desktop"} & browser_choices.keys()
            assert "nested-app.desktop" in dict(initial[3]["choices"])
            # Display text is not identity: Mixed can be an ordinary installed app name.
            group = (*manage.DEFAULT_MIMES[3], *manage.DEFAULT_MIMES[5])
            first = entry("a-viewer.desktop", group, "Categories=TerminalEmulator;\n", name="A viewer")
            named_mixed = entry("selected.desktop", group, "Categories=TerminalEmulator;\n", name="Mixed")
            generic.write_text("[Default Applications]\n" + "".join(mime + "=selected.desktop;\n" for mime in group))
            terminal_selection = config / "xdg-terminals.list"
            terminal_selection.write_text("selected.desktop\n")
            uniform = roles()
            for index in (1, 3, 5):  # Terminal, single MIME, and uniform multi-MIME group.
                assert uniform[index]["label"] == "Mixed"
                assert uniform[index]["current"] == "selected.desktop"
                assert uniform[index]["choices"][0][0] != "selected.desktop"
                assert sum(identifier == uniform[index]["current"] for identifier, _ in uniform[index]["choices"]) == 1
            for path in (first, named_mixed, generic, terminal_selection): path.unlink()
            # Association rules stop at the winning desktop entry's data directory.
            shadow = entry("shadow.desktop", ("text/plain",), directory=data / "applications")
            lower_entry = entry("shadow.desktop", ("application/pdf",))
            lower_rules = system / "applications/mimeapps.list"
            lower_rules.write_text("[Added Associations]\napplication/pdf=shadow.desktop;\n[Removed Associations]\ntext/plain=shadow.desktop;\n")
            assert "shadow.desktop" not in dict(roles()[4]["choices"])
            assert "shadow.desktop" in dict(roles()[3]["choices"])
            fails(lambda: apply(4, "shadow.desktop"), "no longer available")
            apply(3, "shadow.desktop")
            assert roles()[3]["label"] == "shadow.desktop"
            assert not manage.default_ini(generic.read_bytes()).has_option("Added Associations", "text/plain")
            # Higher config rules can add support; saves then have a valid association.
            generic.write_bytes(manage.default_edit(generic.read_bytes(), "Added Associations", {"application/pdf": "shadow.desktop;"}))
            assert "shadow.desktop" in dict(roles()[4]["choices"])
            apply(4, "shadow.desktop")
            assert roles()[4]["label"] == "shadow.desktop"
            # A lower removal cannot hide advertised support from the winning user entry.
            generic.unlink()
            entry("shadow.desktop", ("application/pdf",), directory=data / "applications")
            lower_rules.write_text("[Removed Associations]\napplication/pdf=shadow.desktop;\n")
            assert "shadow.desktop" in dict(roles()[4]["choices"])
            apply(4, "shadow.desktop")
            assert roles()[4]["label"] == "shadow.desktop"
            # Same-directory rules still apply, with higher config overrides winning.
            legacy.write_text("[Removed Associations]\napplication/pdf=shadow.desktop;\n")
            assert "shadow.desktop" not in dict(roles()[4]["choices"])
            generic.write_bytes(manage.default_edit(generic.read_bytes(), "Added Associations", {"application/pdf": "shadow.desktop;"}))
            assert "shadow.desktop" in dict(roles()[4]["choices"])
            for path in (shadow, lower_entry, lower_rules, generic, legacy): path.unlink()
            # Empty inventory and stale preference remain distinct from an unset installed browser.
            with patch.object(manage, "default_inventory", return_value=({}, {})):
                assert roles()[0]["choices"] == [("@unset", "Not set")]
            generic.write_text("# keep comment\n[Default Applications]\napplication/zip=archive.desktop;\ntext/plain=missing.desktop;\n[Added Associations]\napplication/zip=archive.desktop;\n")
            assert roles()[3]["label"] == "Missing: missing.desktop"
            malformed = generic.read_bytes()
            generic.write_text("[Default Applications]\ntext/plain=a.desktop;\ntext/plain=b.desktop;\n")
            fails(roles, "Invalid desktop preference file")
            assert generic.read_text().count("text/plain=") == 2
            generic.write_bytes(malformed)
            fails(lambda: apply(4, "@browser"), "Choose a browser first.")
            before = generic.read_bytes()
            assert generic.read_bytes() == before
            desktop.write_text("# desktop comment\n[Default Applications]\nx-scheme-handler/http=org.example.Flatpak.desktop;\napplication/zip=desktop-archive.desktop;\n")
            legacy.write_text("[Default Applications]\nx-scheme-handler/http=org.example.Flatpak.desktop;\n")
            apply(0, "browser.desktop")
            assert roles()[0]["label"] == "Browser with spaces Ω"
            assert "application/zip=archive.desktop;" in generic.read_text() and "# keep comment" in generic.read_text()
            assert "application/zip=desktop-archive.desktop;" in desktop.read_text() and "# desktop comment" in desktop.read_text()
            assert "x-scheme-handler/http=" not in desktop.read_text() + legacy.read_text()
            apply(4, "@browser")
            assert roles()[4]["label"] == "Default (browser)"
            pdf_bytes = manage.default_ini(generic.read_bytes()).get("Default Applications", "application/pdf")
            apply(0, "org.example.Flatpak.desktop")
            assert manage.default_ini(generic.read_bytes()).get("Default Applications", "application/pdf") == pdf_bytes
            assert roles()[4]["label"] == "Browser with spaces Ω"
            # Apply-time revision protects both the browser identity and disappeared apps.
            revision = roles()[4]["revision"]
            apply(0, "browser.desktop")
            fails(lambda: apply(4, "@browser", revision), "changed")
            revision = roles()[0]["revision"]
            path = exports / "org.example.Flatpak.desktop"
            saved = path.read_bytes(); path.unlink()
            fails(lambda: apply(0, "org.example.Flatpak.desktop", revision), "changed")
            path.write_bytes(saved)
            # Differing set/unset media values are Mixed; a selection touches just the finite group.
            generic.write_bytes(manage.default_edit(generic.read_bytes(), "Default Applications", {"image/png": "browser.desktop;"}))
            assert roles()[5]["label"] == "Mixed" and roles()[5]["current"] == ""
            apply(5, "org.example.Flatpak.desktop")
            assert roles()[5]["label"] == "Flatpak browser"
            assert "application/zip=archive.desktop;" in generic.read_text()
            apply(5, "@unset")
            assert roles()[5]["label"] == "Not set"
            assert "application/zip=archive.desktop;" in generic.read_text()
            # Browser PDF membership may be added even when not advertised, with removals preserved.
            entry("limited-browser.desktop", manage.DEFAULT_MIMES[0])
            apply(0, "limited-browser.desktop")
            generic.write_bytes(manage.default_edit(generic.read_bytes(), "Removed Associations", {"application/pdf": "limited-browser.desktop;other.desktop;"}))
            apply(4, "@browser")
            assert roles()[4]["label"] == "Default (browser)"
            document = manage.default_ini(generic.read_bytes())
            assert "limited-browser.desktop" in document.get("Added Associations", "application/pdf")
            assert document.get("Removed Associations", "application/pdf") == "other.desktop;"
            # The selected desktop entry is checked again after staging, before any rename.
            original_generic = generic.read_bytes()
            real_sync = manage.os.fsync
            removed = False
            def disappear_during_stage(fd):
                nonlocal removed
                if not removed:
                    exported.unlink(); removed = True
                return real_sync(fd)
            with patch.object(manage.os, "fsync", side_effect=disappear_during_stage):
                fails(lambda: apply(3, "org.example.Flatpak.desktop"), "Previous settings retained")
            assert removed and generic.read_bytes() == original_generic
            exported.write_bytes(exported_bytes)
            # Strict MIME ownership is independent from terminal preference ownership.
            saved = generic.read_bytes(); generic.unlink()
            target = root / "hm-mimeapps.list"; target.write_bytes(saved); generic.symlink_to(target)
            assert roles()[0]["readonly"] and not roles()[1]["readonly"]
            fails(lambda: apply(0, "browser.desktop"), "Read Only")
            assert generic.is_symlink() and target.read_bytes() == saved
            terminal_preferences = config / "xdg-terminals.list"
            terminal_preferences.write_text("# keep terminal comment\n/execarg_compat\n-other.desktop\nterminal.desktop\n")
            terminal_override = config / "icewine-xdg-terminals.list"
            terminal_override.write_text("terminal.desktop:NewWindow\n")
            apply(1, "terminal.desktop")
            assert terminal_preferences.read_text().startswith("terminal.desktop\nterminal.desktop:NewWindow\n")
            assert "/execarg_compat\n-other.desktop" in terminal_preferences.read_text()
            assert target.read_bytes() == saved
            original_terminal = terminal_preferences.read_bytes()
            with patch.object(manage, "default_terminal_id", return_value="wrong-terminal.desktop"):
                fails(lambda: apply(1, "terminal.desktop"), "Previous settings retained")
            assert terminal_preferences.read_bytes() == original_terminal
            apply(1, "@unset")
            assert "terminal.desktop\n" not in terminal_preferences.read_text()
            assert "# keep terminal comment" in terminal_preferences.read_text()
            generic.unlink(); generic.write_bytes(saved)
            generic.chmod(0o444)
            assert roles()[3]["readonly"]
            generic.chmod(0o600)
            # A late commit failure restores each original byte, including unrelated keys.
            first, second = root / "first", root / "second"
            first.write_bytes(b"unrelated=keep\n"); second.write_bytes(b"second=keep\n")
            old_first, old_second = manage.default_snapshot(first), manage.default_snapshot(second)
            real_replace = manage.os.replace
            count = 0
            def fail_second(*args, **kwargs):
                nonlocal count
                count += 1
                if count == 2: raise OSError("injected second rename failure")
                return real_replace(*args, **kwargs)
            with patch.object(manage.os, "replace", side_effect=fail_second):
                fails(lambda: manage.default_commit([(first, old_first, b"new-first"), (second, old_second, b"new-second")]), "Previous settings retained")
            assert first.read_bytes() == old_first[4] and second.read_bytes() == old_second[4]
            # A concurrent edit must survive even if that prevents rollback.
            count = 0
            def concurrent(*args, **kwargs):
                nonlocal count
                count += 1
                if count == 2:
                    first.write_bytes(b"another writer's unrelated change")
                    raise OSError("injected failure after concurrent change")
                return real_replace(*args, **kwargs)
            with patch.object(manage.os, "replace", side_effect=concurrent):
                fails(lambda: manage.default_commit([(first, manage.default_snapshot(first), b"new-first"), (second, manage.default_snapshot(second), b"new-second")]), "recovery needs attention")
            assert first.read_bytes() == b"another writer's unrelated change"
            assert second.read_bytes() == old_second[4]
            # Reject a symlink substituted after staging; never modify its target.
            first.write_bytes(b"before")
            before = manage.default_snapshot(first)
            owned = manage.default_owned
            calls = 0
            def substitute(path):
                nonlocal calls
                calls += 1
                if calls == 2 and path == first:
                    first.unlink(); first.symlink_to(target)
                return owned(path)
            with patch.object(manage, "default_owned", side_effect=substitute):
                fails(lambda: manage.default_commit([(first, before, b"unsafe")]), "Previous settings retained")
            assert first.is_symlink() and target.read_bytes() == saved
            assert exported.read_bytes() == exported_bytes
            terminal_preferences.write_text("# terminal actions\nterminal.desktop:NewWindow\n")
            assert roles()[1]["label"] == "terminal.desktop / NewWindow"
            apply(1, "terminal.desktop:NewWindow")
            assert "terminal.desktop:NewWindow" in terminal_preferences.read_text()
            # A failed actual per-role multi-file save restores both MIME files.
            desktop.write_text("# personal desktop override\n[Default Applications]\ntext/plain=browser.desktop;\n")
            snapshot = {path: path.read_bytes() for path in (desktop, generic)}
            count = 0
            with patch.object(manage.os, "replace", side_effect=fail_second):
                fails(lambda: apply(3, "org.example.Flatpak.desktop"), "Previous settings retained")
            assert all(path.read_bytes() == contents for path, contents in snapshot.items())
            assert manage.default_edit(b"# comment without newline", "Default Applications", {"text/plain": None}) == b"# comment without newline"
            # Standard fallback appears after removing the user override, including after a restart.
            fallback = system / "applications/mimeapps.list"
            fallback.write_text("[Default Applications]\ntext/plain=browser.desktop;\n")
            apply(3, "org.example.Flatpak.desktop")
            apply(3, "@unset")
            assert roles()[3]["label"] == "Browser with spaces Ω"
            child = subprocess.run([sys.executable, str(source / "scripts/manage"), "default-apps-state"], env=dict(os.environ), capture_output=True, text=True, check=True)
            assert bytes.fromhex(child.stdout.splitlines()[3].split("\t")[3]).decode() == "Browser with spaces Ω"
            # A chosen directory handler survives unrelated Utilities Apply, even overwrite.
            apply(2, "browser.desktop")
            mime_paths = manage.default_paths(config, data)[0]
            saved_mime = {path: path.read_bytes() if path.exists() else None for path in mime_paths}
            defaults = root / "utility-defaults"
            for name in ("config", "data"): (defaults / name).mkdir(parents=True)
            previous = dict.fromkeys(manage.FEATURES, False) | {"steam": "none", "filemanager": True}
            selected = previous | {"terminal": True}
            from contextlib import ExitStack
            def utilities(overwrite=False):
                (state / "applied.json").write_text(json.dumps(previous))
                with ExitStack() as stack:
                    stack.enter_context(patch.dict(os.environ, ICEWINE_DEFAULT_FILES=str(defaults)))
                    stack.enter_context(patch.object(manage.platform, "freedesktop_os_release", return_value={"ID": "arch"}))
                    commands = stack.enter_context(patch.object(manage, "run"))
                    stack.enter_context(patch.object(manage.theme, "installed", return_value={manage.theme.DEFAULT: {}}))
                    stack.enter_context(patch.object(manage.theme, "effective", return_value=(manage.theme.DEFAULT, False)))
                    stack.enter_context(patch.object(manage.theme, "render_theme", return_value={}))
                    stack.enter_context(patch.object(manage.theme, "render_readonly", return_value=True))
                    stack.enter_context(patch.object(manage.theme, "install_defaults"))
                    stack.enter_context(patch.object(manage.theme, "install_links"))
                    manage.apply(selected, overwrite, False, previous, config, data, state)
                return [call.args[0] for call in commands.call_args_list if call.args[0][:2] == ["xdg-mime", "default"]]
            before = generic.read_bytes()
            assert not utilities() and not utilities(overwrite=True)
            assert generic.read_bytes() == before and roles()[2]["label"] == "Browser with spaces Ω"
            # Preserve explicit defaults at every supported XDG level, including stale IDs.
            for location in mime_paths:
                for path in mime_paths:
                    contents = saved_mime[path] or b""
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(manage.default_edit(contents, "Default Applications", {"inode/directory": None}))
                location.write_text("# personal source\n[Default Applications]\ninode/directory=missing-personal.desktop;\napplication/zip=keep.desktop;\n")
                before = {path: path.read_bytes() for path in mime_paths}
                assert not utilities(), location
                assert all(path.read_bytes() == contents for path, contents in before.items()), location
            # Only a genuinely unconfigured directory role gets the onboarding default.
            for path in mime_paths:
                path.write_bytes(manage.default_edit(path.read_bytes(), "Default Applications", {"inode/directory": None}))
            assert utilities() == [["xdg-mime", "default", "icewine-yazi.desktop", "inode/directory"]]
            for path, contents in saved_mime.items():
                if contents is None: path.unlink()
                else: path.write_bytes(contents)
            # A missing terminal helper blocks only Terminal, never installs one.
            terminal.unlink()
            with patch.dict(os.environ, PATH=str(commands)):
                assert shutil.which("xdg-terminal-exec") is None
                assert roles()[1]["readonly"] and not roles()[3]["readonly"]
            apply(3, "browser.desktop")
            fails(lambda: apply(3, "unlisted.desktop"), "no longer available")
            # Machine state is complete and hex-encodes Unicode/space-bearing labels.
            from contextlib import redirect_stdout
            import io
            stream = io.StringIO()
            with redirect_stdout(stream): manage.main(["default-apps-state"])
            records = [line.split("\t") for line in stream.getvalue().splitlines()]
            assert len(records) == 8 and all(len(record) == 6 for record in records)
            assert bytes.fromhex(records[0][3]).decode() == "limited-browser.desktop"
    print("PASS: real Default Apps backend inventory, explicit defaults, PDF identity, bounded groups, ownership, terminal preferences and guarded recovery")


test_default_apps()
if defaults_only:
    sys.exit(0)

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
