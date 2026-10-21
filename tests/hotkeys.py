#!/usr/bin/env python3
"""Direct backend/real Lua-loader regression: python3 tests/hotkeys.py."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ROWS = [line.split("\t") for line in (ROOT / "hyprland/modules/Bindings.tsv").read_text().splitlines()]
DEFAULTS = {row[0]: row[3] for row in ROWS}
KINDS = {row[0]: row[4] for row in ROWS}


class Hotkeys(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state/icewine"
        self.state.mkdir(parents=True)
        self.path = self.state / "hotkeys"
        self.env = dict(os.environ, HOME=str(self.root), XDG_CONFIG_HOME=str(self.root / "config"),
                        XDG_STATE_HOME=str(self.root / "state"), PATH=str(self.root) + ":" + os.environ["PATH"],
                        HOTKEY_TEST_ROOT=str(self.root), HOTKEY_TEST_SOURCE=str(ROOT), HOTKEY_TEST_PYTHON=sys.executable)
        (self.root / "active").write_text(self.snapshot())
        hyprctl = self.root / "hyprctl"
        hyprctl.write_text('#!' + sys.executable + '\n' + '''import json,os,subprocess,sys
from pathlib import Path
root=Path(os.environ["HOTKEY_TEST_ROOT"])
args=sys.argv[1:]
with (root/"calls").open("a") as stream: stream.write(json.dumps(args)+"\\n")
mode=(root/"mode").read_text() if (root/"mode").exists() else ""
count=int((root/"count").read_text()) if (root/"count").exists() else 0
if args == ["-j","binds"]:
 rows=json.loads((root/"active").read_text())
 if (root/"extra").exists(): rows+=json.loads((root/"extra").read_text())
 print(json.dumps(rows))
elif args == ["configerrors"]: print("config error" if mode=="errors" and count==1 else "")
elif args == ["reload"]:
 count+=1; (root/"count").write_text(str(count))
 if mode != "ignore" or count != 1:
  output=subprocess.check_output(["lua","hyprland/tests/hotkeys.lua"],cwd=os.environ["HOTKEY_TEST_SOURCE"])
  (root/"active").write_bytes(output)
 print("ok")
 if mode == "fail-always" or mode == "fail" and count == 1: sys.exit(1)
else: sys.exit("Unexpected compositor call")
''')
        hyprctl.chmod(0o755)
        self.dotfile = self.root / "config/hypr/hyprland.lua"
        self.dotfile.parent.mkdir(parents=True)
        self.dotfile.write_text('-- custom entry; never rewrite\n')

    def snapshot(self):
        return subprocess.check_output(["lua", "hyprland/tests/hotkeys.lua"], cwd=ROOT, env=self.env, text=True).splitlines()[-1]

    def request(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/manage"), *args], env=self.env,
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        self.assertEqual(self.dotfile.read_text(), '-- custom entry; never rewrite\n')
        return result.stdout + result.stderr

    def fields(self):
        return dict(field.split("=", 1) for field in self.request("hotkeys-state").splitlines()[0].split())

    def save(self, name, chord, ok=True):
        return self.request("hotkeys-apply", self.fields()["revision"], name, chord, ok=ok)

    def effective(self):
        return {row["description"].removeprefix("icewine:"): (row["modmask"], row["key"])
                for row in json.loads((self.root / "active").read_text()) if row["description"].removeprefix("icewine:") in DEFAULTS}

    def test_save_restart_reset_all_actions_and_special_flags(self):
        self.assertEqual(self.fields() | DEFAULTS, self.fields())
        for name in DEFAULTS:
            # Each member is editable; keep native drag and hold/release semantics.
            chord = "CTRL+ALT+MOUSE:274" if KINDS[name] == "mouse" else "SUPER+SHIFT+CTRL+ALT+F12"
            self.save(name, chord)
            self.assertEqual(self.fields()[name], chord)
            active = json.loads((self.root / "active").read_text())
            row = next(row for row in active if row["description"] == "icewine:" + name)
            self.assertEqual((row["modmask"], row["key"].upper()), (12, "MOUSE:274") if KINDS[name] == "mouse" else (77, "F12"))
            # A fresh real Lua loader sees the persisted preference and original callbacks.
            ordered = lambda rows: sorted(rows, key=lambda row: (row["modmask"], row["key"]))
            self.assertEqual(ordered(json.loads(self.snapshot())), ordered(active))
            self.save(name, "default")
        self.assertEqual(self.path.read_bytes(), b"")
        for name, chord in DEFAULTS.items(): self.assertEqual(self.fields()[name], chord)

    def test_saved_tab_actions_preserve_preview_direction_precedence(self):
        for saved in ({}, {"launcher": "TAB"}, {"launcher": "SHIFT+TAB"},
                      {"terminal": "TAB"}, {"taskbar": "SHIFT+TAB"},
                      {"terminal": "TAB", "taskbar": "SHIFT+TAB"}):
            with self.subTest(saved=saved):
                contents = "".join(name + "=" + chord + "\n" for name, chord in saved.items())
                self.path.write_text(contents)
                rows = json.loads(self.snapshot())  # Real preference loader and registration fixture.
                for name, chord in saved.items():
                    row = next(row for row in rows if row["description"] == "icewine:" + name)
                    self.assertEqual((row["modmask"], row["key"].upper()), (int(chord.startswith("SHIFT+")), "TAB"))
                for chord, description in (("TAB", "icewine:preview-tab"), ("SHIFT+TAB", "icewine:preview-backtab")):
                    self.assertEqual(sum(row["description"] == description for row in rows),
                                     0 if chord in saved.values() else 1)
                self.assertEqual(self.path.read_text(), contents)

    def test_hold_modifiers_and_input_kinds(self):
        self.save("taskbar", "CTRL+ALT+F1")
        rows = json.loads(self.snapshot())
        helpers = [row for row in rows if row["description"].startswith("icewine:taskbar-modifier-")]
        self.assertEqual({row["key"].upper() for row in helpers}, {"SUPER_L", "SUPER_R", "SHIFT_L", "SHIFT_R", "CONTROL_L", "CONTROL_R", "ALT_L", "ALT_R"})
        self.assertTrue(all(row["non_consuming"] for row in helpers))
        # Both chord edges remain global dispatchers; transparent primary + each
        # modifier side retain the existing QML press/release lifecycle.
        for name, chord in (("taskbar", "F2"), ("taskbar", "SUPER+MOUSE_DOWN"),
                            ("switcher", "SUPER+MOUSE:274"), ("drag_move", "SUPER+F2"), ("launcher", "SUPER+MOUSE:274")):
            self.assertIn("need" if name == "drag_move" or name == "taskbar" else "Use", self.save(name, chord, ok=False))
        self.save("taskbar", "default")

    def test_tampered_semantics_and_release_helpers_fail_closed(self):
        original = (self.root / "active").read_text()
        for name, flag in (("cycle", "repeat"), ("drag_move", "mouse"), ("volume_up", "locked"),
                           ("taskbar-modifier-SUPER_L", "non_consuming")):
            rows = json.loads(original)
            row = next(row for row in rows if row["description"] == "icewine:" + name)
            row[flag] = not row[flag]
            (self.root / "active").write_text(json.dumps(rows))
            self.assertEqual(self.fields()["readonly"], "true")
            self.save("launcher", "SUPER+F1", ok=False)
            self.assertFalse(self.path.exists())
        (self.root / "active").write_text(original)

    def test_conditional_browser_is_unavailable_without_invented_live_chord(self):
        self.env["HOTKEY_TEST_NO_BROWSER"] = "true"
        (self.root / "active").write_text(self.snapshot())
        def check(browser, alt):
            fields = self.fields()
            self.assertEqual((fields["browser"], fields["readonly"], fields["live"]), (browser, "false", "true"))
            self.assertIn("browser\tApplications\tBrowser (if configured)\tSUPER+B\tpress\tfalse", self.request("hotkeys-state"))
            rows = json.loads(self.snapshot())  # Fresh loader reads persisted preferences.
            self.assertFalse(any(row["description"] == "icewine:browser" for row in rows))
            helpers = {row["key"].upper() for row in rows if row["description"].startswith("icewine:taskbar-modifier-ALT_")}
            self.assertEqual(helpers, {"ALT_L", "ALT_R"} if alt else set())

        self.save("cycle", "F1")  # Remove the only shipped Alt chord.
        check("SUPER+B", False)
        self.save("browser", "ALT+F2")  # Unavailable Browser now contributes Alt alone.
        self.assertIn("browser=ALT+F2\n", self.path.read_text())
        check("ALT+F2", True)
        self.save("launcher", "SUPER+F3")  # Existing saved Browser also validates on other edits.
        check("ALT+F2", True)
        self.save("browser", "default")
        self.assertNotIn("browser=", self.path.read_text())
        check("SUPER+B", False)
        self.save("launcher", "default")
        self.save("cycle", "default")
        self.assertEqual(self.path.read_bytes(), b"")
        check("SUPER+B", True)

    def test_lua_drag_native_json_state_and_rebinding(self):
        # Native 0.56.2 Lua bindings use __lua with mouse=false, even for drag
        # dispatchers. An opts.mouse-reflecting snapshot masked rejection of all edits.
        rows = json.loads(self.snapshot())
        for name in ("drag_move", "drag_resize"):
            row = next(row for row in rows if row["description"] == "icewine:" + name)
            self.assertEqual((row["dispatcher"], row["mouse"], row["release"]), ("__lua", False, False))
        self.assertEqual((self.fields()["readonly"], self.fields()["live"]), ("false", "true"))
        self.save("launcher", "SUPER+F1")
        for name in ("drag_move", "drag_resize"):
            self.save(name, "CTRL+MOUSE:274")
            self.assertEqual(self.fields()[name], "CTRL+MOUSE:274")
            row = next(row for row in json.loads(self.snapshot()) if row["description"] == "icewine:" + name)
            self.assertEqual((row["key"], row["mouse"], row["release"]), ("mouse:274", False, False))
            self.save(name, "SUPER+F2", ok=False)  # Kind restriction survives native flag correction.
            self.save(name, "default")

    def test_empty_or_unset_state_home_uses_home_fallback(self):
        explicit_path = self.path
        self.state = self.root / ".local/state/icewine"
        self.path = self.state / "hotkeys"
        for value in ("", None):
            with self.subTest(XDG_STATE_HOME=value):
                if value is None: self.env.pop("XDG_STATE_HOME", None)
                else: self.env["XDG_STATE_HOME"] = value
                self.save("launcher", "Super+Alt+F1")
                self.assertEqual(self.path.read_text(), "launcher=SUPER+ALT+F1\n")
                self.assertFalse(explicit_path.exists())
                fields = self.fields()
                self.assertEqual((fields["launcher"], fields["readonly"], fields["live"]), ("SUPER+ALT+F1", "false", "true"))
                rows = json.loads(self.snapshot())  # New real Lua loader, same environment.
                launcher = next(row for row in rows if row["description"] == "icewine:launcher")
                self.assertEqual((launcher["modmask"], launcher["key"]), (72, "F1"))
                self.save("launcher", "default")
                self.assertEqual(self.path.read_bytes(), b"")

    def test_invalid_and_actual_collisions_do_not_write_or_reload(self):
        for chord in ("Super+Super+T", "Super+F13", "Super+code:28", "Super+T;exec bad", "Super+", "Super+W", "Super+Q", "Super+E"):
            self.save("launcher", chord, ok=False)
            self.assertFalse(self.path.exists())
        self.assertFalse((self.root / "count").exists())
        # JSON cannot expose ignore_mods or keycode resolution; reserve conservatively.
        for extra in ({"key": "T", "modmask": 0, "submap": "custom"}, {"keycode": 28}, {"key": "SUPER+code:28", "keycode": 0}, {"catch_all": True}):
            (self.root / "extra").write_text(json.dumps([extra]))
            self.assertIn("conflict", self.save("launcher", "Super+Alt+T", ok=False))
        self.assertFalse(self.path.exists())

    def test_stale_revision_and_readonly_policy_preserve_files(self):
        revision = self.fields()["revision"]
        self.path.write_text("terminal=SUPER+ALT+T\n")
        self.assertIn("changed", self.request("hotkeys-apply", revision, "launcher", "Super+F1", ok=False))
        self.path.write_bytes(b"")
        self.path.chmod(0o444)
        self.assertEqual(self.fields()["readonly"], "true")
        self.save("launcher", "Super+F1", ok=False)
        self.assertEqual(self.path.read_bytes(), b"")
        self.path.chmod(0o644)
        self.state.chmod(0o555)
        self.assertEqual(self.fields()["readonly"], "true")
        self.save("launcher", "Super+F1", ok=False)
        self.state.chmod(0o755)

    def test_writable_symlink_uses_preference_helper(self):
        target = self.root / "preferences"
        target.write_bytes(b"")
        self.path.symlink_to(target)
        self.save("launcher", "Super+F1")
        self.assertTrue(self.path.is_symlink())
        self.assertEqual(target.read_text(), "launcher=SUPER+F1\n")
        target.chmod(0o444)
        self.assertEqual(self.fields()["readonly"], "true")
        self.save("launcher", "Super+F2", ok=False)

    def test_failed_delivery_and_failed_verification_restore_known_mapping(self):
        for mode in ("fail", "ignore", "errors"):
            (self.root / "count").write_text("0")
            (self.root / "mode").write_text(mode)
            self.assertIn("previous bindings restored", self.save("launcher", "Super+F1", ok=False))
            self.assertEqual(self.path.read_bytes(), b"")
            self.assertEqual(self.fields()["launcher"], DEFAULTS["launcher"])
            self.assertEqual(self.effective()["launcher"], (64, "SPACE"))
        (self.root / "mode").write_text("fail-always")
        self.assertIn("recovery needs attention", self.save("launcher", "Super+F1", ok=False))
        self.assertEqual(self.path.read_bytes(), b"")

    def test_live_values_take_precedence_and_drift_is_readonly(self):
        self.save("launcher", "Super+F1")
        rows = json.loads((self.root / "active").read_text())
        next(row for row in rows if row["description"] == "icewine:launcher")["key"] = "F2"
        (self.root / "active").write_text(json.dumps(rows))
        fields = self.fields()
        self.assertEqual((fields["launcher"], fields["readonly"], fields["live"]), ("SUPER+F2", "true", "true"))
        before = self.path.read_bytes()
        self.assertIn("differ", self.save("launcher", "Super+F3", ok=False))
        self.assertEqual(self.path.read_bytes(), before)

    def test_unmanaged_session_and_bad_preferences_fail_closed(self):
        (self.root / "active").write_text("[]")
        self.assertEqual(self.fields()["readonly"], "true")
        self.save("launcher", "Super+F1", ok=False)
        self.assertFalse(self.path.exists())
        for raw in ("launcher=SUPER+E\n", "launcher=SUPER+F1\nlauncher=SUPER+F2\n", "unknown=SUPER+F1\n", "launcher=SUPER+F01\n", "launcher=Super+F1\n", "os.execute('bad')\n"):
            self.path.write_text(raw)
            self.request("hotkeys-state", ok=False)
            rows = json.loads(self.snapshot())
            self.assertEqual(next(row["key"] for row in rows if row["description"] == "icewine:launcher"), "SPACE")


if __name__ == "__main__": unittest.main()
