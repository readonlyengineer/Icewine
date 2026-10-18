#!/usr/bin/env python3
"""Drive the built Ratatui frontend through a pseudo-TTY, without host changes."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import pty
import re
import select
import struct
import subprocess
import sys
import tempfile
import termios
import time

def rendered_frames(output, size, check_contrast=False):
    # Ratatui emits positioned cell deltas, not complete text on page changes.
    # Replay its cursor/clear commands; retain completed draws for assertions.
    rows, columns = size
    screen = [[" "] * columns for _ in range(rows)]
    x = y = 0
    foreground = background = None
    frames = []
    for token in re.split(r"(\x1b\[[0-?]*[ -/]*[@-~])", output.decode(errors="replace")):
        if token.startswith("\x1b["):
            command, args = token[-1], token[2:-1]
            if command in ("H", "f"):
                position = [int(value or 1) for value in args.split(";")]
                y, x = position[0] - 1, (position[1] if len(position) > 1 else 1) - 1
            elif (command == "J" and args == "2") or token == "\x1b[?1049h":
                screen = [[" "] * columns for _ in range(rows)]
            elif command == "m":
                codes = [int(value or 0) for value in args.split(";")]
                while codes:
                    code = codes.pop(0)
                    if code == 0: foreground = background = None
                    elif code == 39: foreground = None
                    elif code == 49: background = None
                    # Fixed manager palette emits indexed SGR; extend only
                    # when a real palette or transport needs another encoding.
                    elif code in (38, 48) and len(codes) >= 2 and codes[0] == 5:
                        codes.pop(0)
                        colour = codes.pop(0)
                        if code == 38: foreground = colour
                        else: background = colour
            elif token == "\x1b[?25l":
                frames.append("\n".join("".join(row) for row in screen).encode())
        else:
            for char in token:
                if char == "\r": x = 0
                elif char == "\n": y += 1
                elif char >= " ":
                    if check_contrast and char != " " and background is not None:
                        assert foreground != background, f"Invisible {char!r} at ({y+1}, {x+1}): fg=bg={background}"
                    if 0 <= y < rows and 0 <= x < columns: screen[y][x] = char
                    x += 1
    return frames

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("binary", type=Path)
parser.add_argument("--export-frames", type=Path, help="write complete text frames and raw terminal cells for developer inspection")
parser.add_argument("--frames-only", action="store_true", help="capture representative visual states without repeating the semantic suite")
options = parser.parse_args()
if options.frames_only and not options.export_frames: parser.error("--frames-only requires --export-frames")
binary = options.binary.resolve()
if options.export_frames: options.export_frames.mkdir(parents=True, exist_ok=True)
capture_number = 0
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    backend = root / "icewine-manage-backend"
    backend.write_text('#!' + sys.executable + '\n' + '''import json,os,sys
with open(os.environ["TUI_LOG"],"a") as stream: stream.write(json.dumps(sys.argv[1:])+"\\n")
if sys.argv[1:] == ["state"]: print(os.environ["TUI_STATE"])
elif sys.argv[1:] == ["file-state"]: print(os.environ["TUI_FILE_STATE"])
elif sys.argv[1:] == ["widgets-state"]:
 if os.environ["TUI_WIDGET_POLICY"] == "invalid":
  print("invalid cardStacks policy; Widgets are read-only",file=sys.stderr); sys.exit(1)
 with open(os.environ["TUI_WIDGETS"]) as stream: saved=json.load(stream)
 print("supported="+os.environ["TUI_WIDGET_SUPPORTED"], "revision="+"a"*64, *[
  name+"="+(saved[name] if name in ("cardStacks","barBehaviour","barLocation") else str(saved[name]).lower())+":"+("symlink" if os.environ["TUI_WIDGET_LINKED"] == "1" else "policy" if name in os.environ["TUI_WIDGET_POLICY"].split(",") else "user")
  for name in ("notificationToasts","windowSwitcher","cardStacks","barBehaviour","barLocation")])
elif sys.argv[1] == "widgets-apply":
 if os.environ["TUI_WIDGET_FAIL"] == "1":
  print("Widget preferences changed; reopen the manager before saving",file=sys.stderr); sys.exit(1)
 saved=dict(field.split("=") for field in sys.argv[3:])
 with open(os.environ["TUI_WIDGETS"],"w") as stream: json.dump({name:value if name in ("cardStacks","barBehaviour","barLocation") else value=="true" for name,value in saved.items()},stream)
 print("Widget preferences saved; the shipped shell watches this file.")
elif sys.argv[1:] and sys.argv[1] == "apply": sys.exit(int(os.environ["TUI_APPLY_EXIT"]))
''')
    backend.chmod(0o755)
    tool_log = root / "tools"
    icewine = root / "icewine"
    icewine.write_text('#!' + sys.executable + '\n' + '''import json,os,sys
args=sys.argv[1:]
with open(os.environ["TUI_TOOLS"],"a") as stream: stream.write(json.dumps(["icewine",*args])+"\\n")
with open(os.environ["TUI_APPEARANCE"]) as stream: saved=json.load(stream)
if args == ["theme"]:
 print("Installed: dracula, tokyo-night")
 print("Effective: " + saved["theme"] + (" (Nix policy)" if os.environ["TUI_POLICY"] == "1" else ""))
elif args == ["layout"]: print("Layout: " + saved["layout"] + " (desktop fallback)")
elif args == ["transparency"]: print("Transparency: " + saved["transparency"] + " (off, low, med, high)")
elif args[0] in ("theme", "transparency", "layout"):
 saved[args[0]]=args[1]
 with open(os.environ["TUI_APPEARANCE"],"w") as stream: json.dump(saved,stream)
 if os.environ["TUI_DELIVERY_FAIL"] == "1":
  print("live delivery failed after saving selection", file=sys.stderr); sys.exit(1)
elif os.environ["TUI_COMMAND_FAIL"] == "1":
 print("invalid image; saved preference unchanged", file=sys.stderr); sys.exit(1)
''')
    icewine.chmod(0o755)
    for tool in ("yazi", "hyprmon", "sudo", "icewine-manage"):
        executable = root / tool
        executable.write_text('#!' + sys.executable + '\n' + '''import json,os,sys,termios
assert os.isatty(0)
assert termios.tcgetattr(0)[3] & termios.ICANON, "manager did not release raw mode"
with open(os.environ["TUI_TOOLS"],"a") as stream: stream.write(json.dumps([os.path.basename(sys.argv[0]),*sys.argv[1:]])+"\\n")
if os.path.basename(sys.argv[0]) == "yazi":
 with open(sys.argv[2],"w") as stream: stream.write(os.environ["TUI_PICK"])
 sys.exit(int(os.environ["TUI_PICK_EXIT"]))
sys.exit(int(os.environ["TUI_APPLY_EXIT"] if os.path.basename(sys.argv[0]) == "sudo" else os.environ["TUI_HYPRMON_EXIT"]))
''')
        executable.chmod(0o755)
    log = root / "calls"
    def run(keys, state, valid=True, policy=False, pick="", pick_exit=0, hyprmon_exit=0, auth=False, command_fail=False, delivery_fail=False, size=(24, 100), path=None, widgets=None, widget_policy="", widget_supported=True, widget_fail=False, capture="run", layout="scrolling", confirm=True, apply_exit=0, bootstrap=False, incomplete=False, file_state="theme=false transparency=false wallpaper=false monitors=false layout=false", widget_linked=False):
        global last_output, last_frames, last_widget_calls, capture_number
        log.unlink(missing_ok=True)
        tool_log.unlink(missing_ok=True)
        appearance_state = root / "appearance-state"
        appearance_state.write_text(json.dumps({"theme": "tokyo-night", "transparency": "med", "layout": layout}))
        data = root / "data/icewine/wallpapers"
        data.mkdir(parents=True, exist_ok=True)
        (data / "auth.img").unlink(missing_ok=True)
        if auth: (data / "auth.img").write_bytes(b"fixture")
        widgets_state = root / "widgets-state"
        widgets_state.write_text(json.dumps({"notificationToasts": True, "windowSwitcher": True,
            "cardStacks": "launcher/launcher,background,layout;media/media;audio/audio,bluetooth;network/network,tailscale,ssh;notifications/notifications,clipboard;battery/battery,performance", "barBehaviour": "keyboard", "barLocation": "above"} | (widgets or {})))
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", *size, 0, 0))
        env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(root / "config"), TERM="xterm", PATH=path if path is not None else str(root)+":"+os.environ["PATH"], TUI_LOG=str(log), TUI_STATE=state,
                   TUI_APPLY_EXIT=str(apply_exit), TUI_WIDGETS=str(widgets_state), TUI_WIDGET_SUPPORTED=str(widget_supported).lower(),
                   TUI_FILE_STATE=file_state, TUI_WIDGET_LINKED=str(int(widget_linked)),
                   TUI_WIDGET_POLICY=widget_policy, TUI_WIDGET_FAIL=str(int(widget_fail)), TUI_TOOLS=str(tool_log), TUI_POLICY=str(int(policy)),
                   TUI_PICK=pick, TUI_PICK_EXIT=str(pick_exit), TUI_HYPRMON_EXIT=str(hyprmon_exit),
                   TUI_COMMAND_FAIL=str(int(command_fail)), TUI_DELIVERY_FAIL=str(int(delivery_fail)),
                   TUI_APPEARANCE=str(appearance_state), XDG_DATA_HOME=str(root / "data"), XDG_STATE_HOME=str(root / "state"),
                   ICEWINE_WALLPAPER_DATA_HOME=str(root / "data"), TMPDIR=str(root))
        arguments = [str(binary)]
        if bootstrap:
            package_dir = root / "packages"
            package_dir.mkdir(exist_ok=True)
            (package_dir / "source-revision").write_text("a"*40+"\n")
            archive = package_dir / "icewine-0.1-1-x86_64.pkg.tar.zst"
            archive.unlink(missing_ok=True)
            if not incomplete: archive.write_bytes(b"synthetic package")
            arguments += ["--bootstrap", str(package_dir), "a"*40]
        process = subprocess.Popen(arguments, stdin=slave, stdout=slave, stderr=slave, env=env)
        os.close(slave)
        output = bytearray()
        deadline = time.monotonic() + 10
        sent = False
        reviewed = False
        stop_reason = "child-exit"
        while process.poll() is None and time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    output.extend(os.read(master, 65536))
                except OSError as error:
                    stop_reason = f"read-error:{error.errno}"
                    break
            frames = rendered_frames(output, size)
            rendered = b"\n".join(frames)
            if sent and not reviewed and b"Icewine: planned changes" in rendered:
                os.write(master, b"i" if confirm else b"\x1b")
                reviewed = True
            if not sent and frames:
                assert (b"Icewine needs an 80 x 24 terminal." if size[1] < 80 or size[0] < 24 else
                        b"Icewine onboarding: base package" if bootstrap else
                        b"Icewine Installer (1/3) | Tab: Appearance") in rendered
                os.write(master, keys)
                sent = True
        forced_kill = process.poll() is None
        if forced_kill:
            if stop_reason == "child-exit": stop_reason = "deadline"
            process.kill()
        code = process.wait()
        while select.select([master], [], [], 0)[0]:
            try: output.extend(os.read(master, 65536))
            except OSError: break
        diagnostic = {"binary": str(binary), "size": size, "keys_hex": keys.hex(),
            "exit": code, "forced_kill": forced_kill, "stop_reason": stop_reason,
            "sent": sent, "reviewed": reviewed,
            "mock_calls": log.read_text().splitlines() if log.exists() else [],
            "tool_calls": tool_log.read_text().splitlines() if tool_log.exists() else []}
        if options.export_frames:
            capture_number += 1
            directory = options.export_frames / f"{capture_number:03d}-{capture}-{size[1]}x{size[0]}"
            directory.mkdir()
            (directory / "terminal.ansi").write_bytes(output)
            (directory / "capture.json").write_text(json.dumps(diagnostic, indent=2)+"\n")
        # Preserve the child outcome before either contrast or ICANON assertions.
        last_frames = rendered_frames(output, size, check_contrast=not options.frames_only)
        rendered = b"\n".join(last_frames)
        if options.export_frames:
            diagnostic["frames"] = len(last_frames)
            (directory / "capture.json").write_text(json.dumps(diagnostic, indent=2)+"\n")
            for index, frame in enumerate(last_frames):
                (directory / f"{index:03d}.txt").write_bytes(frame + b"\n")
        if sent:
            assert termios.tcgetattr(master)[3] & termios.ICANON, "terminal raw mode was not restored: " + json.dumps(diagnostic)
        os.close(master)
        last_output = rendered
        assert code == (0 if valid and apply_exit == 0 else 1), output.decode(errors="replace")
        if bootstrap:
            if not valid:
                assert not sent and b"preparation incomplete" in output
                return []
            if size[1] < 80 or size[0] < 24:
                assert sent and b"Resize to continue; Esc: cancel." in rendered
            else:
                assert sent
            return [] if not tool_log.exists() else [json.loads(line) for line in tool_log.read_text().splitlines()]
        if not valid:
            assert not sent
            return [json.loads(line) for line in log.read_text().splitlines()]
        assert sent, output.decode(errors="replace")
        if size[1] < 80 or size[0] < 24:
            assert b"Resize to continue; Esc: cancel." in rendered
        else:
            assert b"Icewine Installer" in rendered
            assert b"Overwrite existing dotfiles" in rendered
            assert b"[ Apply ]" in rendered and b"[ Cancel ]" in rendered
            assert (b"Utility selections are read-only" in rendered) == ("readonly=true" in state.split())
        all_calls = [json.loads(line) for line in log.read_text().splitlines()]
        last_widget_calls = [call for call in all_calls if call[0].startswith("widgets-")]
        return [call for call in all_calls if not call[0].startswith("widgets-") and call[0] != "file-state"]
    ids = ("desktop", "terminal", "filemanager", "steam", "gamescope", "handheld", "login", "shellExtras")
    visible = 5 # Arch hides Login; Steam none hides its two children.
    def state(readonly=False, **selected):
        # Deliberately shuffle fields: identity must not depend on wire order.
        return " ".join([f"{name}={str(selected.get(name, "none" if name == "steam" else False)).lower()}" for name in reversed(ids)]
                        + [f"readonly={str(readonly).lower()}"])
    def applied(calls):
        assert calls[0] == ["state"] and calls[1][0] == "apply" and len(calls) == 2
        fields = dict(field.split("=") for field in calls[1][1:])
        assert len(fields) == len(ids) + 1 and set(fields) == {*ids, "overwrite"}
        return fields
    if options.frames_only:
        tab, down = b"\t", b"\x1b[B"
        for size in ((24, 80), (36, 120)):
            run(tab + b"\x1b", state(), size=size, capture="pages")
            run(tab + b"\x1b", state(readonly=True, desktop=True, steam="native", gamescope=True, handheld=True),
                policy=True, auth=True, size=size, capture="readonly-auth")
            run(tab*2+b" s\x1b", state(), size=size, capture="widgets-save")
            if size[1] != 80: continue
            run(down*3+b"\x1b[C"+down*5+b"\x1b", state(desktop=True), size=size, capture="installer-actions")
            (root / "hyprmon").rename(root / "hyprmon-hidden")
            try:
                run(tab+down*3+b"\r\x1b", state(), size=size, path=str(root), capture="monitor-error")
            finally: (root / "hyprmon-hidden").rename(root / "hyprmon")
            run(tab+down*2+b"\r\x1b", state(), size=size, command_fail=True,
                pick=str(root/"picture with spaces.png")+"\n", capture="picker-error")
            run(tab*2+b" s\x1b", state(), size=size, widget_fail=True, capture="widgets-error")
            run(tab*2+b"\x1b", state(), size=size, widget_supported=False, capture="widgets-unavailable")
            run(tab*2+b"\x1b", state(), size=size, widget_policy="notificationToasts,windowSwitcher", capture="widgets-policy")
        print("PASS: completed visual frames exported; semantic suite not run")
        sys.exit(0)
    no_tty = subprocess.run([str(binary)], stdin=subprocess.DEVNULL, capture_output=True)
    assert no_tty.returncode == 1 and b"A terminal is required" in no_tty.stderr
    assert run(b"", "", valid=False, bootstrap=True, incomplete=True) == []
    assert run(b"\x1b", "", bootstrap=True) == []
    assert run(b"\x03", "", bootstrap=True) == []
    assert run(b"i\x1b", "", bootstrap=True, size=(24, 79)) == []
    calls = run(b"i", "", bootstrap=True)
    assert calls[0][:3] == ["sudo", "pacman", "-U"] and len(calls)==2
    assert calls[1] == ["icewine-manage"]
    calls = run(b"i", "", bootstrap=True, apply_exit=1)
    assert len(calls)==1 and calls[0][0] == "sudo"
    assert run(b" \x1b", state()) == [["state"]]
    assert run(b"\x1b[B"*(visible+2)+b"\r", state()) == [["state"]]
    expected = dict.fromkeys(ids, "false") | {"steam": "none", "desktop": "true", "overwrite": "false"}
    assert applied(run(b" "+b"\x1b[B"*(visible+1)+b"\r", state())) == expected
    assert run(b" "+b"\x1b[B"*(visible+1)+b"\r", state(), confirm=False) == [["state"]]
    assert applied(run(b" "+b"\x1b[B"*(visible+1)+b"\r", state(), apply_exit=1))["desktop"] == "true"
    # A second row toggles its own ID, not the backend's second field.
    expected["desktop"], expected["terminal"] = "false", "true"
    assert applied(run(b"\x1b[B "+b"\x1b[B"*visible+b"\r", state())) == expected
    # Right selects native, defaults Gamescope on and leaves Handheld off.
    chosen = applied(run(b"\x1b[B"*3+b"\x1b[C"+b"\x1b[B"*4+b"\r", state()))
    assert chosen["steam"] == "native" and chosen["gamescope"] == "true" and chosen["handheld"] == "false"
    # Flatpak skips unsupported Handheld; Gamescope may be turned off.
    chosen = applied(run(b"\x1b[B"*3+b"\x1b[C\x1b[C\x1b[B "+b"\x1b[B"*3+b"\r", state()))
    assert chosen["steam"] == "flatpak" and chosen["gamescope"] == "false" and chosen["handheld"] == "false"
    # Native+desktop allows Handheld; turning desktop off clears it.
    chosen = applied(run(b" \x1b[B\x1b[B\x1b[B\x1b[C\x1b[B\x1b[B "+b"\x1b[B"*3+b"\r", state()))
    assert chosen["handheld"] == "true"
    chosen = applied(run(b" "+b"\x1b[B"*7+b"\r", state(desktop=True, steam="native", gamescope=True, handheld=True)))
    assert chosen["desktop"] == "false" and chosen["handheld"] == "false"
    # Reverse navigation from the first control reaches Cancel.
    assert run(b"\x1b[Z\r", state()) == [["state"]]
    # NixOS focus skips utility rows; Space only checks overwrite.
    expected = dict.fromkeys(ids, "false") | {"steam": "none", "desktop": "true", "overwrite": "true"}
    assert applied(run(b" \x1b[B\r", state(readonly=True, desktop=True))) == expected
    assert applied(run(b"\x1b[B\r", state(readonly=True, desktop=True)))["overwrite"] == "false"
    for invalid in (state() + " terminal=true", state().replace("terminal=false", "unknown=false"),
                    state().replace("terminal=false", ""), state().replace("terminal=false", "terminal=1"),
                    state(steam="invalid"), state(handheld=True), state(gamescope=True),
                    state(steam="flatpak", desktop=True, gamescope=True, handheld=True)):
        assert run(b"", invalid, valid=False) == [["state"]]
    def tools():
        return [json.loads(line) for line in tool_log.read_text().splitlines()]
    tab = b"\t"
    down = b"\x1b[B"
    # Without the size guard, Tab/Right would immediately change Appearance.
    assert run(tab+b"\x1b[C\x1b", state(), size=(20, 70)) == [["state"]]
    assert not any(len(call) > 2 or call[0] != "icewine" for call in tools()), "hidden control acted"
    # Page changes preserve utility focus and pending selections; appearance is live.
    chosen = applied(run(b" \x1b[B" + tab + b"\x1b[C\x1b[B\x1b[C" + tab*2 + b" " + tab + b"\x1b[C" + tab*2 + down*visible+b"\r", state()))
    assert chosen["desktop"] == "true" and chosen["terminal"] == "true"
    assert ["icewine", "theme", "dracula"] in tools()
    assert ["icewine", "transparency", "high"] in tools()
    assert ["icewine", "transparency", "off"] in tools(), "appearance focus was not preserved"
    assert b"Tab: page" in last_output
    assert b"Up/down: move" in last_output
    assert b"Appearance updates immediately." in last_output
    # The navigation affordance and controls fit a conventional 80-column TTY
    # as well as the wider default; exercise a round trip at both sizes.
    for size in ((24, 80), (24, 100), (36, 120)):
        assert run(tab + tab + tab + b"\x1b", state(), size=size) == [["state"]]
        assert any(b"Icewine Appearance (2/3) | Tab: Widgets" in frame for frame in last_frames)
        assert b"Icewine Installer (1/3) | Tab: Appearance" in last_frames[-1]
        for frame in last_frames:
            if b"Icewine " in frame:
                assert b"Tab: page" in frame and b"Esc: cancel" in frame
                assert b"[ Cancel ]" in frame
        appearance_frames = [frame for frame in last_frames if b"Icewine Appearance" in frame]
        assert any(b"Configure monitors" in frame for frame in appearance_frames)
    # The tallest Appearance form fits the minimum and wider reference panels.
    for size in ((24, 80), (36, 120)):
        assert run(tab + down*4 + b"\x1b[C\x1b", state(), auth=True, size=size) == [["state"]]
        assert ["icewine", "layout", "dwindle"] in tools()
        labels = (b"Theme", b"Transparency", b"Wallpaper",
                  b"Configure monitors", b"Desktop layout default", b"[ Apply ]", b"[ Cancel ]",
                  b"Tab: page", b"Esc: cancel")
        assert any(b"Icewine Appearance" in frame and all(label in frame for label in labels)
                   for frame in last_frames), (size, last_frames)
    # Overwrite survives page switches and Apply works from either page.
    for finish in (tab*2 + down + b"\r", down*5 + b"\r"):
        assert applied(run(down*visible + b" " + tab + finish, state()))["overwrite"] == "true"

    # Widget Cancel discards a draft after page navigation; Save commits only
    # widgets while an Installer draft remains pending. Width matrices belong
    # to the shared visual checks.
    assert run(tab*2+b" "+tab*3+b"\x1b", state(), size=(24, 80)) == [["state"]]
    assert not any(call[0] == "widgets-apply" for call in last_widget_calls)
    assert b"Icewine Widgets (3/3)" in last_output
    assert run(b" "+tab*2+b" s\x1b", state(), size=(24, 80)) == [["state"]]
    save = next(call for call in last_widget_calls if call[0] == "widgets-apply")
    assert save[2:4] == ["notificationToasts=false", "windowSwitcher=true"]
    # A preloaded effective mixed policy skips its owned row. Persistence itself
    # is exercised by the real backend, not this reset-per-run mock.
    assert run(tab*2+b" s\x1b", state(readonly=True),
               widgets={"notificationToasts": False, "windowSwitcher": False},
               widget_policy="notificationToasts") == [["state"]]
    save = next(call for call in last_widget_calls if call[0] == "widgets-apply")
    assert save[2:4] == ["notificationToasts=false", "windowSwitcher=true"]
    assert run(tab*2+b" s\x1b", state(), widget_fail=True) == [["state"]]
    assert any(call[0] == "widgets-apply" for call in last_widget_calls)
    assert b"preferences changed" in last_output and b"Widget preferences saved" not in last_output
    # Unavailable card rows remain focusable for inspection; Space/Enter do
    # nothing there. Save is disabled too; cancel explicitly rather than waiting.
    assert run(tab*2+b" \rs\x1b", state(), widget_supported=False) == [["state"]]
    assert not any(call[0] == "widgets-apply" for call in last_widget_calls)
    assert b"Unavailable" in last_output
    # Real key handling edits one in-memory draft; persistence validation is
    # covered by install.py against the real backend rather than this TTY mock.
    def saved_stacks():
        call = next(call for call in last_widget_calls if call[0] == "widgets-apply")
        return next(field.removeprefix("cardStacks=") for field in call if field.startswith("cardStacks="))
    right, left, delete = b"\x1b[C", b"\x1b[D", b"\x1b[3~"
    for size in ((24, 80), (36, 120)):
        # Reorder a member, move it to another stack, make it that stack's
        # icon, and move that stack before the original one.
        run(tab*2+down*4+b"+"+right+b"-[s\x1b", state(), size=size,
            widgets={"cardStacks": "a/launcher,background,layout,media;b/audio"})
        assert saved_stacks() == "b/launcher,audio;a/background,layout,media"
        assert any(b"1. b / 1 icon (primary)" in frame for frame in last_frames)
        # New stack, join an existing stack, and move a new singleton stack.
        run(tab*2+down*4+b" "+down+right+down+b"n[s\x1b", state(), size=size,
            widgets={"cardStacks": ""})
        assert saved_stacks() == "stack-2/layout;stack-1/launcher,background"
        # Removing the configured first member makes the next member the icon;
        # disable the final member without retaining an empty stack.
        run(tab*2+down*4+b" "+down+b" s\x1b", state(), size=size,
            widgets={"cardStacks": "a/launcher,background"})
        assert saved_stacks() == ""
        # Remove a whole stack, then explicitly re-enable a module.
        run(tab*2+down*4+delete+b" s\x1b", state(), size=size,
            widgets={"cardStacks": "a/launcher,background;b/audio"})
        assert saved_stacks() == "b/audio;stack-1/launcher"
        # Focus scrolls to the last module; its configured fourth accent repeats.
        run(tab*2+down*16+b"s\x1b", state(), size=size,
            widgets={"cardStacks": "mixed/launcher,audio,clipboard,performance"})
        assert saved_stacks() == "mixed/launcher,audio,clipboard,performance"
        assert any(b"performance" in frame and b"4 (primary)" in frame for frame in last_frames)
    # Moving a singleton into its previous stack must remove the old stack
    # without losing or misindexing the destination. Save button remains usable.
    run(tab*2+down*4+left+down*13+b"\r\x1b", state(), size=(24, 80),
        widgets={"cardStacks": "a/launcher;b/audio"})
    assert saved_stacks() == "b/audio,launcher"
    # Tab keeps the draft; Cancel never writes it.
    run(tab*2+down*4+delete+tab*3+b"\x1b", state())
    assert not any(call[0] == "widgets-apply" for call in last_widget_calls)
    # Policy locks stack operations but leaves ordinary boolean settings editable.
    run(tab*2+down*4+b"n+-[]"+right+delete+b" s\x1b", state(),
        widgets={"cardStacks": "host/launcher"}, widget_policy="cardStacks")
    assert saved_stacks() == "host/launcher"
    run(tab*2+b"ns\x1b", state(), widget_policy="notificationToasts,windowSwitcher,cardStacks,barBehaviour,barLocation")
    assert not any(call[0] == "widgets-apply" for call in last_widget_calls)
    run(tab*2+b"ns\x1b", state(), widget_policy="invalid")
    assert not any(call[0] == "widgets-apply" for call in last_widget_calls)
    assert b"invalid cardStacks policy" in last_output
    # Every visibility/location pair is an unsaved draft until Save; cycling
    # wraps both ways and read-only policy rows are skipped by real navigation.
    behaviours = ("keyboard", "keyboard-mouse", "toggle", "always")
    locations = ("above", "top", "bottom")
    for behaviour_index, behaviour in enumerate(behaviours):
        for location_index, location in enumerate(locations):
            run(tab*2+down*2+right*behaviour_index+down+right*location_index+b"s\x1b", state(), size=(24, 80))
            call = next(call for call in last_widget_calls if call[0] == "widgets-apply")
            assert "barBehaviour=" + behaviour in call and "barLocation=" + location in call
    run(tab*2+down*2+left+right+down+left+b"s\x1b", state())
    call = next(call for call in last_widget_calls if call[0] == "widgets-apply")
    assert "barBehaviour=keyboard" in call and "barLocation=bottom" in call
    run(tab*2+down*2+right+down+right+tab*3+b"\x1b", state())
    assert not any(call[0] == "widgets-apply" for call in last_widget_calls)
    run(tab*2+down*2+right+b"s\x1b", state(),
        widgets={"barBehaviour": "always", "barLocation": "bottom"}, widget_policy="barBehaviour")
    call = next(call for call in last_widget_calls if call[0] == "widgets-apply")
    assert "barBehaviour=always" in call and "barLocation=above" in call
    # Delivery can fail after committing a choice: display/next cycle follow saved state.
    assert run(tab+b"\x1b[C\x1b[C\x1b[B\x1b[C\x1b[C\x1b", state(), delivery_fail=True) == [["state"]]
    changes = [call for call in tools() if call[0] == "icewine" and len(call) == 3]
    assert changes == [["icewine", "theme", "dracula"], ["icewine", "theme", "tokyo-night"],
                       ["icewine", "transparency", "high"], ["icewine", "transparency", "off"]]
    assert b"live delivery failed after saving selection" in last_output
    # Utility read-only does not lock permitted appearance controls; theme policy does.
    assert run(tab+b"\x1b[C\x1b", state(readonly=True), policy=True) == [["state"]]
    assert ["icewine", "transparency", "high"] in tools()
    assert not any(call[:2] == ["icewine", "theme"] and len(call) == 3 for call in tools())
    # Linked controls are skipped individually; a regular layout remains live.
    assert run(tab+b"\x1b[C\x1b", state(readonly=True),
               file_state="theme=true transparency=true wallpaper=true monitors=true layout=false") == [["state"]]
    assert [call for call in tools() if len(call) == 3] == [["icewine", "layout", "dwindle"]]
    assert b"symlink/read-only" in last_output
    assert run(tab*2+b" \r\x1b", state(), widget_linked=True) == [["state"]]
    assert not any(call[0] == "widgets-apply" for call in last_widget_calls)
    assert b"symlink" in last_output
    # A committed fallback is read back after failed delivery, even with utility
    # controls read-only; the next cycle and Cancel follow the saved selection.
    assert run(tab + down*4 + b"\x1b[C\x1b[C\x1b", state(readonly=True), delivery_fail=True) == [["state"]]
    changes = [call for call in tools() if call[:2] == ["icewine", "layout"] and len(call) == 3]
    assert changes == [["icewine", "layout", "dwindle"], ["icewine", "layout", "master"]]
    assert any(b"Desktop layout default" in frame and b"< master >" in frame for frame in last_frames)
    assert b"live delivery failed after saving selection" in last_output
    # Malformed layout responses fail before entering the terminal UI.
    assert run(b"", state(), valid=False, layout="invalid") == [["state"]]
    # Native chooser restores the terminal after success, cancel and failure.
    picked = str(root / "picture with spaces.png")
    for pick, exit_code, fail in ((picked+"\n", 0, False), ("", 0, False), (picked+"\n", 1, False), (picked+"\n", 0, True)):
        assert run(tab+b"\x1b[B\x1b[B\r\x1b", state(), pick=pick, pick_exit=exit_code, command_fail=fail) == [["state"]]
        calls = tools()
        assert sum(call[0] == "yazi" for call in calls) == 1
        assert (["icewine", "wallpaper", picked] in calls) == (bool(pick) and exit_code == 0)
        assert not list(root.glob("icewine-picker-*")), "chooser file leaked"
        if fail: assert b"invalid image" in last_output
    (root / "yazi").chmod(0o600)
    try:
        assert run(tab+b"\x1b[B\x1b[B\r\x1b", state()) == [["state"]]
        assert b"Yazi unavailable:" in last_output
    finally: (root / "yazi").chmod(0o755)
    # A historical auth image must not restore the retired presentation controls.
    assert run(tab+b"\x1b", state(), auth=True) == [["state"]]
    assert b"Lockscreen Wallpaper" not in last_output and b"Separate image" not in last_output
    assert (root / "data/icewine/wallpapers/auth.img").read_bytes() == b"fixture"
    # HyprMon owns live/save semantics; zero exit must not claim a successful save.
    for exit_code in (0, 1, 127):
        assert run(tab+b"\x1b[B"*3+b"\r"+tab+b"\x1b", state(), hyprmon_exit=exit_code) == [["state"]]
        assert ["hyprmon"] in tools()
    assert b"HyprMon live/save changes remain after Cancel." in last_output
    (root / "hyprmon").chmod(0o600)
    try:
        assert run(tab+b"\x1b[B"*3+b"\r\x1b", state()) == [["state"]]
        assert b"HyprMon unavailable: could not run hyprmon:" in last_output
    finally: (root / "hyprmon").chmod(0o755)
    (root / "hyprmon").rename(root / "hyprmon-hidden")
    try:
        assert run(tab+b"\x1b[B"*3+b"\r\x1b", state(readonly=True), size=(24, 80), path=str(root)) == [["state"]]
        assert b"hyprmon on PATH" in last_output
        assert b"Lua-compatible" in last_output
        assert b"services.icewine.monitors" in last_output
    finally: (root / "hyprmon-hidden").rename(root / "hyprmon")
print("PASS: real TTY cancel, editable/read-only navigation, named selections, invalid state, Tab pages, appearance handoffs and fresh overwrite default")
