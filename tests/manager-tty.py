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
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time

def rendered_frames(output, size, check_contrast=False, resize_events=(), check_background=False):
    # Ratatui emits positioned cell deltas, not complete text on page changes.
    # Replay its cursor/clear commands; retain completed draws for assertions.
    rows, columns = size
    screen = [[" "] * columns for _ in range(rows)]
    styles = [[(None, None)] * columns for _ in range(rows)]
    x = y = 0
    foreground = background = None
    frames = []
    # Resize offsets belong to the harness, keeping captured ANSI unmodified.
    def tokens():
        start = 0
        for offset, new_size in resize_events:
            yield from re.split(r"(\x1b\[[0-?]*[ -/]*[@-~])", output[start:offset].decode(errors="replace"))
            yield new_size
            start = offset
        yield from re.split(r"(\x1b\[[0-?]*[ -/]*[@-~])", output[start:].decode(errors="replace"))
    for token in tokens():
        if isinstance(token, tuple):
            rows, columns = token
            screen = [[" "] * columns for _ in range(rows)]
            styles = [[(None, None)] * columns for _ in range(rows)]
            x = y = 0
            continue
        if token.startswith("\x1b["):
            command, args = token[-1], token[2:-1]
            if command in ("H", "f"):
                position = [int(value or 1) for value in args.split(";")]
                y, x = position[0] - 1, (position[1] if len(position) > 1 else 1) - 1
            elif (command == "J" and args == "2") or token == "\x1b[?1049h":
                screen = [[" "] * columns for _ in range(rows)]
                styles = [[(foreground, background)] * columns for _ in range(rows)]
            elif command == "m":
                codes = [int(value or 0) for value in args.split(";")]
                while codes:
                    code = codes.pop(0)
                    if code == 0: foreground = background = None
                    elif code == 39: foreground = None
                    elif code == 49: background = None
                    elif 30 <= code <= 37: foreground = code - 30
                    elif 40 <= code <= 47: background = code - 40
                    elif 90 <= code <= 97: foreground = code - 90 + 8
                    elif 100 <= code <= 107: background = code - 100 + 8
                    elif code in (38, 48) and len(codes) >= 2 and codes[0] == 5:
                        codes.pop(0)
                        colour = codes.pop(0)
                        if code == 38: foreground = colour
                        else: background = colour
                    elif code in (38, 48) and len(codes) >= 4 and codes[0] == 2:
                        codes.pop(0)
                        colour = tuple(codes[:3]); del codes[:3]
                        if code == 38: foreground = colour
                        else: background = colour
            elif token == "\x1b[?25l":
                if check_background:
                    # The fixture's theme background is only a highlight foreground.
                    # Check retained cells too: deltas must erase old selections.
                    highlights = {((30, 30, 46), (137, 180, 250)), ((40, 42, 54), (189, 147, 249)), (0, 6)}
                    for row, cells in enumerate(styles):
                        for column, (fg, bg) in enumerate(cells):
                            assert bg is None or (fg, bg) in highlights, (
                                f"Non-default ordinary background at ({row+1}, {column+1}): fg={fg}, bg={bg}")
                    assert all(bg is None for fg, bg in styles[0] + styles[-1]), "Opaque canvas border"
                frames.append("\n".join("".join(row) for row in screen).encode())
        else:
            for char in token:
                if char == "\r": x = 0
                elif char == "\n": y += 1
                elif char >= " ":
                    if check_contrast and char != " " and background is not None:
                        assert foreground != background, f"Invisible {char!r} at ({y+1}, {x+1}): fg=bg={background}"
                    if 0 <= y < rows and 0 <= x < columns:
                        screen[y][x] = char
                        styles[y][x] = (foreground, background)
                    x += 1
    return frames

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("binary", type=Path)
parser.add_argument("--export-frames", type=Path, help="write complete text frames and raw terminal cells for developer inspection")
parser.add_argument("--preview-only", action="store_true", help="run the existing native Theme preview/cancel/commit regression group")
parser.add_argument("--frames-only", action="store_true", help="capture representative visual states without repeating the semantic suite")
parser.add_argument("--background-only", action="store_true", help="check terminal-default cells across pages, previews, errors and resize")
parser.add_argument("--hotkeys-only", action="store_true", help="check continuous Hotkeys scrolling, editing, wrapping, mouse, focus and resize")
parser.add_argument("--spacing-only", action="store_true", help="check page geometry, wrapping and action placement with synthetic data")
options = parser.parse_args()
if options.frames_only and not options.export_frames: parser.error("--frames-only requires --export-frames")
if options.frames_only and options.background_only: parser.error("--background-only requires background assertions; omit --frames-only")
binary = options.binary.resolve()
if options.export_frames: options.export_frames.mkdir(parents=True, exist_ok=True)
capture_number = 0
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    backend = root / "icewine-manage-backend"
    backend.write_text('#!' + sys.executable + '\n' + '''import json,os,sys
with open(os.environ["TUI_LOG"],"a") as stream: stream.write(json.dumps(sys.argv[1:])+"\\n")
if sys.argv[1:] == ["state"]: print(os.environ["TUI_STATE"])
elif sys.argv[1:] == ["appearance-state"]:
 with open(os.environ["TUI_APPEARANCE"]) as stream: saved=json.load(stream)
 response=" ".join(["themes=dracula,tokyo-night", "selected="+saved["theme"], "policy="+str(os.environ["TUI_POLICY"]=="1").lower(), "level="+saved["transparency"], "desktopLayout="+saved["layout"], os.environ["TUI_FILE_STATE"]])
 print(os.environ["TUI_APPEARANCE_WIRE"] or (response+" unknown=false" if os.environ["TUI_REFRESH_BAD"]=="1" and saved["theme"]!="tokyo-night" else response))
elif sys.argv[1:2] == ["theme-preview"]:
 print("primary=bd93f9 foreground=f8f8f2 background=282a36 muted=6272a4 secondary=50fa7b tertiary=ff79c6" if sys.argv[2] == "dracula" else "primary=89b4fa foreground=cdd6f4 background=1e1e2e muted=a6adc8 secondary=a6e3a1 tertiary=cba6f7")
elif sys.argv[1:] == ["hotkeys-state"]:
 with open(os.environ["TUI_HOTKEYS"]) as stream: saved=json.load(stream)
 print("readonly="+os.environ["TUI_HOTKEY_READONLY"], "live=true", "revision="+"a"*64, *[name+"="+chord for name,chord in saved.items()])
elif sys.argv[1:2] == ["hotkeys-apply"]:
 if os.environ["TUI_HOTKEY_ERROR"]:
  print(os.environ["TUI_HOTKEY_ERROR"],file=sys.stderr); sys.exit(1)
 defaults={"launcher":"SUPER+SPACE","terminal":"SUPER+RETURN","filemanager":"SUPER+E","screenshot":"SUPER+PRINT","lock":"SUPER+L"}
 with open(os.environ["TUI_HOTKEYS"]) as stream: saved=json.load(stream)
 name,chord=sys.argv[3:]
 saved[name]=defaults[name] if chord=="default" else chord.upper().replace("ENTER","RETURN").replace(" ","")
 with open(os.environ["TUI_HOTKEYS"],"w") as stream: json.dump(saved,stream)
 print("Hotkey saved")
elif sys.argv[1:] == ["widget-icons"]:
 print("launcher= background=󰀻 layout=󰕰 media= audio= bluetooth= clipboard=󰅌 network=󰯡 tailscale=󰒍 ssh=󰣀 notifications=󰂜 battery=󰐥 performance=󰓅")
elif sys.argv[1:] == ["widgets-state"]:
 if os.environ["TUI_WIDGET_POLICY"] == "invalid":
  print("invalid cardStacks policy; Widgets are read-only",file=sys.stderr); sys.exit(1)
 with open(os.environ["TUI_WIDGETS"]) as stream: saved=json.load(stream)
 owners=json.loads(os.environ["TUI_WIDGET_OWNERS"])
 print("supported="+os.environ["TUI_WIDGET_SUPPORTED"], "revision="+"a"*64, *[
  name+"="+(str(saved[name]) if name in ("cardStacks","barBehaviour","barLocation","barStyle","barWidth","oskAccess") else str(saved[name]).lower())+":"+owners.get(name, "symlink" if os.environ["TUI_WIDGET_LINKED"] == "1" else "policy" if name in os.environ["TUI_WIDGET_POLICY"].split(",") else "user")
  for name in ("notificationToasts","windowSwitcher","cardStacks","barBehaviour","barLocation","barStyle","barWidth","oskAccess")])
elif sys.argv[1] == "widgets-apply":
 if os.environ["TUI_WIDGET_FAIL"] == "1":
  print("Widget preferences changed; reopen the manager before saving",file=sys.stderr); sys.exit(1)
 saved=dict(field.split("=") for field in sys.argv[3:])
 with open(os.environ["TUI_WIDGETS"]) as stream: previous=json.load(stream)
 with open(os.environ["TUI_WIDGETS"],"w") as stream: json.dump(previous | {name:int(value) if name == "barWidth" else value if name in ("cardStacks","barBehaviour","barLocation","barStyle","oskAccess") else value=="true" for name,value in saved.items()},stream)
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
if len(args) == 1 and args[0] in ("theme", "transparency", "layout"):
 print("human status must not be read by the manager",file=sys.stderr); sys.exit(1)
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
    def run(keys, state, valid=True, policy=False, pick="", pick_exit=0, hyprmon_exit=0, auth=False, command_fail=False, delivery_fail=False, size=(24, 100), path=None, widgets=None, widget_policy="", widget_supported=True, widget_fail=False, capture="run", layout="scrolling", confirm=True, apply_exit=0, bootstrap=False, archives=None, revision="a"*40, file_state="theme=false transparency=false wallpaper=false monitors=false layout=false", widget_linked=False, appearance_wire="", refresh_bad=False, resize_steps=(), widget_owners=None, hotkeys=None, hotkey_readonly=False, hotkey_error=""):
        global last_output, last_frames, last_widget_calls, all_last_calls, capture_number
        log.unlink(missing_ok=True)
        tool_log.write_text("")  # A run may legitimately invoke no external tools.
        appearance_state = root / "appearance-state"
        appearance_state.write_text(json.dumps({"theme": "tokyo-night", "transparency": "med", "layout": layout}))
        data = root / "data/icewine/wallpapers"
        data.mkdir(parents=True, exist_ok=True)
        (data / "auth.img").unlink(missing_ok=True)
        if auth: (data / "auth.img").write_bytes(b"fixture")
        widgets_state = root / "widgets-state"
        widgets_state.write_text(json.dumps({"notificationToasts": True, "windowSwitcher": True,
            "cardStacks": "launcher/launcher,background,layout;media/media;audio/audio,bluetooth;network/network,tailscale,ssh;notifications/notifications,clipboard;battery/battery,performance", "barBehaviour": "keyboard", "barLocation": "above", "barStyle": "anchored", "barWidth": 80, "oskAccess": "none"} | (widgets or {})))
        hotkey_state = root / "hotkeys-state"
        hotkey_state.write_text(json.dumps({"launcher":"SUPER+SPACE", "terminal":"SUPER+RETURN", "filemanager":"SUPER+E", "screenshot":"SUPER+PRINT", "lock":"SUPER+L"} | (hotkeys or {})))
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", *size, 0, 0))
        env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(root / "config"), TERM="xterm", PATH=path if path is not None else str(root)+":"+os.environ["PATH"], TUI_LOG=str(log), TUI_STATE=state,
                   TUI_HOTKEYS=str(hotkey_state), TUI_HOTKEY_READONLY=str(hotkey_readonly).lower(), TUI_HOTKEY_ERROR=hotkey_error,
                   TUI_APPLY_EXIT=str(apply_exit), TUI_WIDGETS=str(widgets_state), TUI_WIDGET_SUPPORTED=str(widget_supported).lower(),
                   TUI_FILE_STATE=file_state, TUI_APPEARANCE_WIRE=appearance_wire, TUI_REFRESH_BAD=str(int(refresh_bad)), TUI_WIDGET_LINKED=str(int(widget_linked)),
                   TUI_WIDGET_OWNERS=json.dumps(widget_owners or {}), TUI_WIDGET_POLICY=widget_policy, TUI_WIDGET_FAIL=str(int(widget_fail)), TUI_TOOLS=str(tool_log), TUI_POLICY=str(int(policy)),
                   TUI_PICK=pick, TUI_PICK_EXIT=str(pick_exit), TUI_HYPRMON_EXIT=str(hyprmon_exit),
                   TUI_COMMAND_FAIL=str(int(command_fail)), TUI_DELIVERY_FAIL=str(int(delivery_fail)),
                   TUI_APPEARANCE=str(appearance_state), XDG_DATA_HOME=str(root / "data"), XDG_STATE_HOME=str(root / "state"),
                   ICEWINE_WALLPAPER_DATA_HOME=str(root / "data"), TMPDIR=str(root))
        arguments = [str(binary)]
        if bootstrap:
            package_dir = Path(tempfile.mkdtemp(dir=root))
            (package_dir / "source-revision").write_text("a"*40+"\n")
            for name, kind in ({"icewine-0.1-1-x86_64.pkg.tar.zst": "file"} if archives is None else archives).items():
                archive = package_dir / name
                if kind == "symlink": archive.symlink_to(package_dir / "source-revision")
                elif kind == "directory": archive.mkdir()
                elif kind == "fifo": os.mkfifo(archive)
                else: archive.write_bytes(b"synthetic package")
            arguments += ["--bootstrap", str(package_dir), revision]
        process = subprocess.Popen(arguments, stdin=slave, stdout=slave, stderr=slave, env=env)
        os.close(slave)
        output = bytearray()
        deadline = time.monotonic() + 10
        sent = False
        pending_input = []
        input_boundary = 0
        input_batches = 0
        def send_keys(data):
            nonlocal input_boundary, input_batches
            # ESC ESC in one terminal packet is Alt-Escape, not two presses.
            # Keep CSI/mouse sequences intact; release each adjacent bare Escape
            # after the preceding input's redraw has been consumed.
            pending_input.extend(re.split(rb"(?<=\x1b)(?=\x1b)", data))
            input_boundary = len(output)
            os.write(master, pending_input.pop(0))
            input_batches += 1
        pending_resizes = list(resize_steps)
        resize_events = []
        resize_keys = None
        reviewed = False
        stop_reason = "child-exit"
        while process.poll() is None and time.monotonic() < deadline:
            readable = select.select([master], [], [], 0.1)[0]
            if readable:
                try:
                    output.extend(os.read(master, 65536))
                except OSError as error:
                    stop_reason = f"read-error:{error.errno}"
                    break
            frames = rendered_frames(output, size, resize_events=resize_events)
            rendered = b"\n".join(frames)
            if sent and not reviewed and b"Utilities / Review" in rendered:
                os.write(master, b"i" if confirm else b"\x1b")
                reviewed = True
            if not sent and frames:
                assert (b"Icewine needs an 80 x 24 terminal." if size[1] < 80 or size[0] < 24 else
                        b"Icewine onboarding: base package" if bootstrap else
                        b"Utilities") in rendered
                send_keys(keys)
                sent = True
            elif resize_keys is not None:
                # Wait for a completed redraw at the new dimensions before keys.
                offset, new_size = resize_events[-1]
                if rendered_frames(output[offset:], new_size):
                    send_keys(resize_keys)
                    resize_keys = None
            elif sent and pending_input and not readable and rendered_frames(output[input_boundary:], resize_events[-1][1] if resize_events else size):
                input_boundary = len(output)
                os.write(master, pending_input.pop(0))
                input_batches += 1
            elif sent and pending_resizes and not pending_input and not readable:
                new_size, resize_keys = pending_resizes.pop(0)
                resize_events.append((len(output), new_size))
                fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", *new_size, 0, 0))
                os.kill(process.pid, signal.SIGWINCH)
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
            "sent": sent, "input_batches": input_batches, "pending_input_chunks": len(pending_input),
            "reviewed": reviewed, "resize_events": resize_events,
            "mock_calls": log.read_text().splitlines() if log.exists() else [],
            "tool_calls": tool_log.read_text().splitlines() if tool_log.exists() else []}
        if options.export_frames:
            capture_number += 1
            directory = options.export_frames / f"{capture_number:03d}-{capture}-{size[1]}x{size[0]}"
            directory.mkdir()
            (directory / "terminal.ansi").write_bytes(output)
            (directory / "capture.json").write_text(json.dumps(diagnostic, indent=2)+"\n")
        # Preserve the child outcome before either contrast or ICANON assertions.
        last_frames = rendered_frames(output, size, check_contrast=not options.frames_only, resize_events=resize_events, check_background=not options.frames_only)
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
        assert not pending_resizes and resize_keys is None, "resize sequence incomplete: " + json.dumps(diagnostic)
        assert code == (0 if valid and apply_exit == 0 else 1), output.decode(errors="replace")
        if bootstrap:
            if not valid:
                assert not sent and (b"preparation incomplete" in output or b"Invalid prepared source revision" in output)
                assert tool_log.read_text() == ""
                return []
            if size[1] < 80 or size[0] < 24:
                assert sent and b"Resize to continue; Esc: cancel." in rendered
            else:
                assert sent
            if apply_exit: assert b"Base installation failed; packages may have changed" in output
            return [] if not tool_log.exists() else [json.loads(line) for line in tool_log.read_text().splitlines()]
        if not valid:
            assert not sent
            return [call for line in log.read_text().splitlines() if (call := json.loads(line))[0] != "appearance-state"]
        assert sent, output.decode(errors="replace")
        if size[1] < 80 or size[0] < 24:
            assert b"Resize to continue; Esc: cancel." in rendered
        else:
            assert b"Utilities" in rendered
            assert b"Overwrite existing dotfiles" in rendered
            assert b"Selected utilities are installed" in rendered
        all_calls = [json.loads(line) for line in log.read_text().splitlines()]
        all_last_calls = all_calls
        last_widget_calls = [call for call in all_calls if call[0].startswith("widgets-")]
        return [call for call in all_calls if not call[0].startswith(("widgets-", "hotkeys-")) and call[0] not in ("appearance-state","theme-preview","widget-icons")]
    ids = ("desktop", "terminal", "filemanager", "steam", "gamescope", "handheld", "login", "shellExtras", "texteditor", "screenshot")
    visible = 5 # Arch hides Login; Steam none hides its two children.
    def state(readonly=False, **selected):
        # Deliberately shuffle fields: identity must not depend on wire order.
        return " ".join([f"{name}={str(selected.get(name, "none" if name in {"steam","screenshot"} else False)).lower()}" for name in reversed(ids)]
                        + [f"readonly={str(readonly).lower()}"])
    def applied(calls):
        assert calls[0] == ["state"] and calls[1][0] == "apply" and len(calls) == 2
        fields = dict(field.split("=") for field in calls[1][1:])
        assert len(fields) == len(ids) + 1 and set(fields) == {*ids, "overwrite"}
        return fields
    up, down, left, right, enter, esc, tab = b"\x1b[A", b"\x1b[B", b"\x1b[D", b"\x1b[C", b"\r", b"\x1b", b"\t"
    def page(index): return down*index + tab
    def saves(): return [call for call in last_widget_calls if call[0] == "widgets-apply"]
    def save_field(name):
        return next(field.split("=", 1)[1] for field in saves()[-1][2:] if field.startswith(name + "="))
    def tools(): return [json.loads(line) for line in tool_log.read_text().splitlines()]
    def click(x, y): return f"\x1b[<0;{x};{y}M\x1b[<0;{x};{y}m".encode()
    def test_theme_preview():
        # Theme preview is local; Back never calls the public mutation command.
        run(page(1)+enter+up+esc+esc, state())
        assert not any(call[:2] == ["icewine","theme"] for call in tools())
        # Reach Use theme via Back, without traversing and previewing tokyo-night.
        run(page(1)+enter+up+up*2+enter+esc, state())
        assert ["icewine","theme","dracula"] in tools()
        # Keyboard exit from a local preview restores the effective theme palette.
        run(page(1)+enter+up+tab+down+esc, state())
        previews = [call for call in all_last_calls if call[0] == "theme-preview"]
        assert previews[-1] == ["theme-preview", "tokyo-night"]
        assert not any(call[:2] == ["icewine", "theme"] for call in tools())
    def test_spacing():
        visual = state(desktop=True, terminal=True, filemanager=True, texteditor=True,
                       shellExtras=True, steam="flatpak", gamescope=True, screenshot="advanced")
        def frame_for(title):
            return next(frame.decode().splitlines() for frame in reversed(last_frames)
                        if title in frame.decode().splitlines()[1])
        taskbar = page(1)+down*4+enter
        for size in ((24,80), (30,100), (24,160), (48,80)):
            for name, keys, title in (
                    ("utilities", esc, "Utilities"),
                    ("appearance", page(1)+esc, "Appearance"),
                    ("theme", page(1)+enter+esc*2, "Appearance / Theme"),
                    ("taskbar", taskbar+esc*2, "Appearance / Taskbar"),
                    ("widgets", page(2)+esc, "Widgets")):
                run(keys, visual, size=size, capture=name)
                frame = frame_for(title)
                assert all(line[20:22] == "  " for line in frame), (name, size, frame)
                assert all(line[-1] == ("╮" if y == 0 else "╯" if y == size[0]-1 else "┤" if y == 2 else "│")
                           for y, line in enumerate(frame)), (name, size, frame)
                if name in ("theme", "taskbar"):
                    action = "[ Use theme ]" if name == "theme" else "[ Save ]"
                    assert action in frame[size[0]-4], (name, size, frame)
                if name == "utilities":
                    selected_rows = [i for i, line in enumerate(frame) if any(label in line for label in ("Desktop session", "Steam", "Overwrite existing"))]
                    assert len(selected_rows) >= 3
                if name == "widgets" and size == (24,80):
                    assert all(label in "\n".join(frame) for label in ("Launcher", "Media", "Audio", "Network", "Notifications", "Battery", "Unassigned"))
            run(page(3)+esc, visual, size=size, capture="hotkeys-start")
            frame = frame_for("Hotkeys")
            assert "Common" in frame[4] and "Show/Toggle Taskbar" in frame[6], (size, frame)
            assert "←/→ Category" not in "\n".join(frame)
            for line in frame[6:size[0]-3]:
                if "Super+" in line:
                    assert line.index("Super+") == 49, (size, line)
        run(page(2)+up+esc, visual, size=(24,80), capture="widgets-tools")
        frame = frame_for("Widgets")
        assert "Window switcher" in "\n".join(frame) and "[ New stack ]" in "\n".join(frame)
        assert all(line[-1] == "│" for line in frame[3:-1]), frame
        long_theme = "a-very-long-installed-theme-name-with-a-variant"
        wire = f"themes={long_theme},tokyo-night selected={long_theme} policy=false level=med desktopLayout=scrolling theme=false transparency=false wallpaper=false monitors=false layout=false"
        run(page(1)+enter+esc*2, visual, size=(24,80), appearance_wire=wire, capture="theme-long")
        frame = frame_for("Appearance / Theme")
        assert "Current" in "\n".join(frame)
        assert next(line.index("Current") for line in frame if "Current" in line) == 44
        assert "Variant" in "\n".join(frame), frame
        run(esc, state(readonly=True), size=(24,80), capture="utilities-readonly")
        frame = frame_for("Utilities - Read Only")
        assert "Hyprland + Quickshell" in "\n".join(frame) and "Neovim + LazyVIM" in "\n".join(frame)
        run(taskbar+esc*2, visual, size=(24,80), widgets={"barBehaviour":"keyboard-mouse"},
            widget_policy="barBehaviour", capture="taskbar-readonly")
        frame = frame_for("Appearance / Taskbar")
        assert "Read Only" in "\n".join(frame) and "Keyboard + Mouse" in "\n".join(frame)
        run(page(2)+b"s"+esc, visual, size=(24,80), widget_fail=True, capture="widgets-error")
        frame = frame_for("Widgets")
        assert "Widget preferences changed" in "\n".join(frame[-4:-1])
        assert "[ Save ]" in "\n".join(frame[:-4])
        run(tab+down*10+enter, visual, size=(24,80), confirm=False, capture="review")
        frame = frame_for("Utilities / Review")
        assert "[ Apply ]   [ Back ]" in frame[20] and frame[0].startswith("╭")
        assert not any(call[0] == "apply" for call in all_last_calls)
        run(tab+down*9+enter, state(), size=(24,80), widget_policy="invalid", confirm=False, capture="utilities-startup-error")
        assert any(b"[ Review and Apply ]" in frame for frame in last_frames)
        assert not any(call[0] == "apply" for call in all_last_calls)
        run(esc, "", bootstrap=True, size=(24,80), capture="bootstrap")
        print("PASS: spacing, wrapping, read-only values, status/action separation and native captures")
    def hotkey_bodies():
        bodies = []
        for raw in last_frames:
            frame = raw.decode().splitlines()
            if len(frame) < 24 or "Hotkeys" not in frame[1][22:]: continue
            assert "Enter: Edit  r: Reset" in frame[-2], frame
            assert "←/→ Category" not in "\n".join(frame), frame
            assert all(line[20:22] == "  " and line[-1] == "│" for line in frame[3:-1]), frame
            body = [line[24:-2].rstrip() for line in frame[4:-3]]
            if not bodies or body != bodies[-1]: bodies.append(body)
        assert bodies, "No Hotkeys draw captured"
        return bodies

    def test_hotkeys():
        headings = ["Common", "Applications", "Windows", "Workspaces", "Desktop / session"]
        visual = state(screenshot="advanced")
        wheel_down = b"\x1b[<65;40;10M"
        wheel_up = b"\x1b[<64;40;10M"
        for size in ((24,80), (30,100), (40,140), (48,80)):
            # Recover the actual native list from overlapping one-row scrolls.
            # This detects both clipping and overscroll, including wrapped rows.
            run(page(3)+wheel_down*180+esc, visual, size=size, capture="hotkeys-traversal")
            bodies = hotkey_bodies()
            content = list(bodies[0])
            assert content[0] == "Common" and content[1] == ""
            assert content[2].startswith("Show/Toggle Taskbar")
            for previous, current in zip(bodies, bodies[1:]):
                assert previous[1:] == current[:-1], (size, previous, current)
                content.append(current[-1])
            assert [line for line in content if line in headings] == headings, (size, content)
            assert content[-1].endswith("scrolls."), (size, content[-5:])
            assert sum(line.startswith("Taskbar:") for line in content) == 1
            assert sum(line.startswith("Shipped Icewine bindings.") for line in content) == 1
            text = "\n".join(content)
            assert all(label in text for label in ("Flameshot editor", "Browser (if configured)",
                "Join/split column", "(scrolling only)", "Relative workspace", "Widget cards",
                "Focused display", "brightness", "Cards: Bluetooth")), (size, text)
            start, end = bodies[0], bodies[-1]
            # A single Up must move immediately even after excess Down inputs.
            run(page(3)+wheel_down*180+wheel_up+esc, visual, size=size, capture="hotkeys-end-up")
            assert hotkey_bodies()[-1] == bodies[-2]
            run(page(3)+down*180+up*180+esc, visual, size=size, capture="hotkeys-return-start")
            assert hotkey_bodies()[-1] == start
            run(page(3)+wheel_down*180+esc, visual, size=size, capture="hotkeys-wheel-end")
            assert hotkey_bodies()[-1] == end
            run(page(3)+wheel_down*180+wheel_up*180+esc, visual, size=size, capture="hotkeys-wheel-start")
            assert hotkey_bodies()[-1] == start
            # Left/right/activation do not change sections. Pane/page changes retain offset.
            run(page(3)+wheel_down*20+left+right+tab+up+down+tab+esc,
                visual, size=size, capture="hotkeys-focus")
            assert hotkey_bodies()[-1] == bodies[20]
            assert not saves() and not tools()
        # Clicking the list focuses it; its headings are not separate controls.
        run(down*3+click(30,5)+down+esc, visual, size=(24,80), capture="hotkeys-click")
        assert hotkey_bodies()[-1][0] == "Common" and "Show/Toggle Taskbar" in hotkey_bodies()[-1][2]
        # Reflow at the bottom must clamp to the new rendered height immediately.
        run(page(3)+down*180, visual, size=(24,80), capture="hotkeys-resize",
            resize_steps=[((40,140),down*180), ((20,79),down+tab), ((30,100),down*180+esc)])
        resized = hotkey_bodies()
        assert next(body for body in resized if len(body) == 40-7)[-1].endswith("scrolls."), resized
        resized_end = resized[-1]
        run(page(3)+down*180+esc, visual, size=(30,100), capture="hotkeys-resize-expected")
        assert hotkey_bodies()[-1] == resized_end
        print("PASS: continuous Hotkeys headings, native row overlap, bounds, wrapping, wheel, focus and resize")

    def test_hotkey_editor():
        def edits(): return [call for call in all_last_calls if call[0] == "hotkeys-apply"]
        # Cursor moves through the continuous rendered list; first editable row is Launcher.
        launcher = page(3)+down*3
        clear = b"\x15"  # Ctrl+U; text input avoids terminal Super-key interception.
        for size in ((24,80), (40,140)):
            run(launcher+enter+clear+b"Super+Alt+F8"+enter+esc, state(), size=size, capture="hotkeys-save")
            assert edits()[-1][2:] == ["launcher", "Super+Alt+F8"]
            assert b"Launcher" in last_frames[-1] and b"Super+Alt+F8" in last_frames[-1]
            # The same action in Applications must show and edit the new effective chord.
            run(page(3)+down*180+esc, state(), size=size, hotkeys={"launcher":"SUPER+ALT+F8"}, capture="hotkeys-effective-repeat")
            assert any(b"Applications" in frame and b"Launcher" in frame and b"Super+Alt+F8" in frame for frame in last_frames)
            assert all("Super+Alt+F8" in line for frame in last_frames for line in frame.decode().splitlines()
                       if line[24:].startswith("Launcher"))
            run(launcher+enter+clear+b"Super+Q"+esc+esc, state(), size=size, capture="hotkeys-cancel")
            assert not edits()
            for error in ("Invalid hotkey chord", "Hotkey conflicts with an existing binding", "Hotkey reload failed; previous bindings restored"):
                run(launcher+enter+clear+b"Super+Q"+enter+esc+esc, state(), size=size,
                    hotkey_error=error, capture="hotkeys-error")
                assert error.encode().split()[0] in last_output
                assert len(edits()) == 1
            run(launcher+b"r"+esc, state(), size=size, hotkeys={"launcher":"SUPER+ALT+F8"}, capture="hotkeys-reset")
            assert edits()[-1][2:] == ["launcher", "default"]
            assert b"Super+Space" in last_frames[-1]
            run(launcher+enter+b"r"+esc, state(), size=size, hotkey_readonly=True, capture="hotkeys-readonly")
            assert not edits() and b"Hotkeys - Read Only" in last_output
        # Screenshot near the Common viewport edge stays visible during edit/error/reflow.
        run(page(3)+down*12+enter, state(screenshot="advanced"), size=(24,80), capture="hotkeys-editor-resize",
            resize_steps=[((40,140), clear+b"Super+Shift+Ctrl+Alt+F12"+enter+esc)])
        assert edits()[-1][2:] == ["screenshot", "Super+Shift+Ctrl+Alt+F12"]
        assert b"Flameshot editor" in last_frames[-1] and b"Super+Shift+Ctrl+Alt+F12" in last_frames[-1]
        # Edit the repeated Lock below wrapped Windows/Workspaces text, then reflow.
        run(page(3)+b"\x1b[<65;40;10M"*180+esc, state(), size=(24,80), capture="hotkeys-lock-position")
        bodies = hotkey_bodies()
        content = list(bodies[0]) + [body[-1] for body in bodies[1:]]
        lock_row = max(index for index, line in enumerate(content) if line.startswith("Lock "))
        run(page(3)+down*lock_row+enter, state(), size=(24,80), capture="hotkeys-lock-reflow",
            resize_steps=[((40,140), clear+b"Super+Alt+F9"+enter+esc)])
        assert edits()[-1][2:] == ["lock", "Super+Alt+F9"]
        assert b"Lock" in last_frames[-1] and b"Super+Alt+F9" in last_frames[-1]
        print("PASS: Hotkeys editor save/cancel/reset, effective appearances, errors, ownership and selected-row resize")

    if options.hotkeys_only:
        test_hotkeys()
        test_hotkey_editor()
        sys.exit(0)
    if options.background_only:
        test_spacing()
        test_theme_preview()
        run(tab+b" ", state(), size=(24,80), capture="background-resize",
            resize_steps=[((20,79),right+tab),((30,100),esc)])
        print("PASS: terminal-default ordinary cells and retained highlight contrast across pages, previews, errors and resize")
        sys.exit(0)
    if options.spacing_only:
        test_spacing()
        sys.exit(0)
    if options.preview_only:
        test_theme_preview()
        print("PASS: native Theme preview cancel/commit and keyboard preview exit")
        sys.exit(0)
    no_tty = subprocess.run([str(binary)], stdin=subprocess.DEVNULL, capture_output=True)
    assert no_tty.returncode == 1 and b"A terminal is required" in no_tty.stderr
    assert run(b"", "", valid=False, bootstrap=True, archives={}) == []
    base = "icewine-12.34.5-6.2-x86_64.pkg.tar.zst"
    ignored = {name: "file" for name in (
        "icewine-session-12.34.5-6.2-x86_64.pkg.tar.zst",
        "icewine-handheld-12.34.5-6.2-x86_64.pkg.tar.zst",
        base+".sig", "icewine-12.34.5-6.2-aarch64.pkg.tar.zst",
        "icewine-next-1-x86_64.pkg.tar.zst", "icewine-1..2-1-x86_64.pkg.tar.zst",
        "icewine-1--x86_64.pkg.tar.zst", "icewine-1-1-x86_64.pkg.tar.")}
    assert run(b"", "", valid=False, bootstrap=True, archives=ignored) == []
    calls = run(b"i", "", bootstrap=True, archives={base: "file", **ignored})
    assert calls[0][:3] == ["sudo", "pacman", "-U"] and Path(calls[0][3]).name == base
    assert len(calls) == 2 and calls[1] == ["icewine-manage"]
    assert run(b"", "", valid=False, bootstrap=True,
               archives={base: "file", "icewine-0.1-1-x86_64.pkg.tar.xz": "file"}) == []
    for kind in ("symlink", "directory", "fifo"):
        assert run(b"", "", valid=False, bootstrap=True, archives={base: kind}) == []
    for revision in ("a"*39, "A"*40, "g"*40, "b"*40):
        assert run(b"", "", valid=False, bootstrap=True, revision=revision) == []
    assert run(b"\x1b", "", bootstrap=True) == []
    assert run(b"\x03", "", bootstrap=True) == []
    assert run(b"i\x1b", "", bootstrap=True, size=(24, 79)) == []
    calls = run(b"i", "", bootstrap=True)
    assert calls[0][:3] == ["sudo", "pacman", "-U"] and len(calls)==2
    assert calls[1] == ["icewine-manage"]
    calls = run(b"i", "", bootstrap=True, apply_exit=1)
    assert len(calls)==1 and calls[0][0] == "sudo"
    for size in ((24,80), (24,160), (48,80), (48,160)):
        run(esc, state(), size=size)
        assert b"Utilities" in last_output and b"Appearance" in last_output and b"Hotkeys" in last_output
        frame = last_frames[-1].decode().splitlines()
        assert all(line[20:22] == "  " for line in frame), "Page panes lost their two-cell gap"
        assert frame[2].startswith("├" + "─"*18 + "┤  ├"), "Title separator lost its crossbar junctions"

        assert b"[ Review and Apply ]" in last_output and b"[ Setup Monitors... ]" in last_output
        run(page(1)+esc, state(), size=size)
        assert b"Default layout" in last_output and b"Notifications" in last_output
        run(page(2)+right+down+esc, state(), size=size)
        assert b"Unassigned" in last_output and b"Import (coming soon)" in last_output
        if size == (24,80):
            assert all(name.encode() in last_frames[-1] for name in ("Launcher", "Media", "Audio", "Network", "Notifications", "Battery")), "Default Widgets grid must show all six stacks"

        run(page(3)+right+down*5+esc, state(), size=size)
        assert b"Common" in last_output and b"Applications" in last_output
        assert not saves()
    test_spacing()
    test_hotkeys()
    test_hotkey_editor()
    # Pane focus and keyboard utility Apply identify fields independently of wire order.
    run(tab+b" "+down*9+enter, state())
    choices = applied([call for call in all_last_calls if call[0] in ("state", "apply")])
    assert choices["desktop"] == "true" and choices["overwrite"] == "false"
    run(tab+b" "+down*9+enter, state(), confirm=False)
    assert not any(call[0] == "apply" for call in all_last_calls)
    # Steam-none prerequisite rows remain visible and cannot enable Handheld.
    run(tab+down*6+right+down+enter+esc, state())
    assert b"Requires Steam native" in last_output
    test_theme_preview()
    # Taskbar save scope is explicit. Legacy always survives unrelated Save/Cancel.
    taskbar = page(1)+down*4+enter
    run(taskbar+right+down*5+enter+esc, state())
    assert save_field("barBehaviour") == "keyboard-mouse"
    assert {field.split("=",1)[0] for field in saves()[-1][2:]} == {"barBehaviour","barLocation","barStyle","barWidth","oskAccess"}
    run(taskbar+right+esc+esc, state())
    assert not saves()
    run(taskbar+down*5+enter+esc, state(), widgets={"barBehaviour":"always"})
    assert save_field("barBehaviour") == "always" and b"Always show (legacy)" in last_output
    run(taskbar+right+down*5+enter+esc, state(), widgets={"barBehaviour":"always"})
    assert save_field("barBehaviour") == "keyboard"
    run(taskbar+left+down*5+enter+esc, state(), widgets={"barBehaviour":"always"})
    assert save_field("barBehaviour") == "toggle"
    run(taskbar+right+down*4+enter+esc, state(), widgets={"barBehaviour":"always"}, widget_policy="barBehaviour")
    assert save_field("barBehaviour") == "always"
    for width, changes in ((50,left*40),(100,right*40)):
        run(taskbar+down*3+changes+down*2+enter+esc, state())
        assert save_field("barWidth") == str(width)
    # Notifications saves only the toast bit; Widgets draft persists across pages.
    run(page(1)+down*5+enter+esc, state())
    assert saves()[-1][2:] == ["notificationToasts=false"]
    # Remove, place in the visible grid, cancel placement and preserve destination IDs.
    widgets = page(2)
    run(widgets+enter+b"  "+right+enter+b"s"+esc*2, state())
    assert "media/media,launcher" in save_field("cardStacks")
    run(widgets+enter+b"  "+esc+b"s"+esc*2, state())
    assert "launcher/" not in save_field("cardStacks") or "launcher/background,layout" in save_field("cardStacks")
    run(widgets+enter+down+b"-s"+esc*2, state())
    assert save_field("cardStacks").startswith("launcher/background,launcher,layout")
    run(widgets+enter+b"ns"+esc*2, state())
    assert "stack-1/launcher" in save_field("cardStacks")
    run(widgets+enter+b"\x1b[3~s"+esc*2, state())
    assert "launcher/" not in save_field("cardStacks")
    run(widgets+enter+b"s"+esc*2, state(), widgets={"cardStacks":""})
    assert save_field("cardStacks") == ""
    run(widgets+enter+b"ns"+esc*2, state(), widgets={"cardStacks":""})
    assert save_field("cardStacks") == "stack-1/launcher"
    many = ";".join(f"s{i}/{name}" for i,name in enumerate(("launcher","background","layout","media","audio","bluetooth","clipboard","network","tailscale","ssh","notifications","battery","performance")))
    for size in ((24,80),(24,160),(48,80)):
        run(widgets+down*9+up+right+b"s"+esc*2, state(), widgets={"cardStacks":many}, size=size)
        assert save_field("cardStacks") == many
        run(widgets+enter+down*12+b"s"+esc*2, state(), widgets={"cardStacks":"all/"+",".join(name.split('/')[1] for name in many.split(';'))}, size=size)
        assert b"Performance" in last_output
    # Read-only and invalid ownership cannot save; sole editable fields remain reachable.
    for options_ in ({"widget_linked":True}, {"widget_supported":False}, {"widget_policy":"notificationToasts,windowSwitcher,cardStacks,barBehaviour,barLocation,barStyle,barWidth,oskAccess"}):
        run(widgets+enter+b" n+-[]s"+esc*3, state(), **options_)
        assert not saves()
    run(widgets+b"ns"+esc*2, state(), widget_fail=True)
    assert b"changed" in last_output
    for name in ("notificationToasts","windowSwitcher","cardStacks","barBehaviour","barLocation","barStyle","barWidth","oskAccess"):
        run(esc, state(), widget_owners={name:"invalid"})
        assert b"Invalid" in last_output or b"invalid" in last_output
    fields = ("notificationToasts","windowSwitcher","cardStacks","barBehaviour","barLocation","barStyle","barWidth","oskAccess")
    for name in fields:
        owners = {field:"user" if field == name else "policy" for field in fields}
        if name == "notificationToasts": keys = page(1)+down*5+enter+esc
        elif name == "windowSwitcher": keys = widgets+up+b" s"+esc*2
        elif name == "cardStacks": keys = widgets+b"ns"+esc*2
        else: keys = taskbar+right+down+enter+esc
        run(keys, state(), widget_owners=owners)
        assert saves(), name
        if name == "notificationToasts": assert save_field(name) == "false"
        elif name == "windowSwitcher": assert save_field(name) == "false"
        elif name == "cardStacks": assert "stack-1/launcher" in save_field(name)
        else: assert save_field(name) != str({"barBehaviour":"keyboard","barLocation":"above","barStyle":"anchored","barWidth":80,"oskAccess":"none"}[name])
    # Taskbar Save must not commit pending card membership, and later Widgets Save keeps it.
    run(widgets+b"n"+tab+up+tab+down*4+enter+right+down*5+enter+tab+down+tab+b"s"+esc*2, state())
    assert len(saves()) == 2
    assert not any(field.startswith("cardStacks=") for field in saves()[0])
    assert "stack-1/launcher" in save_field("cardStacks")
    # Real mouse targets: select page, enter/remove a member, save; import is inert.
    run(click(5,9)+click(26,5)+b"s"+esc*2, state(), size=(24,80))
    assert saves()
    run(page(3)+down*180+esc, state())
    assert b"Desktop / session" in last_output
    run(page(3)+esc, state(), widgets={"barBehaviour":"toggle"})
    assert b"toggle on press" in last_output and b"toggle on release" not in last_output
    taskbar_line = next(line for line in last_frames[-1].decode().splitlines() if "Show/Toggle Taskbar" in line)
    assert taskbar_line.index("Show/Toggle Taskbar") < taskbar_line.index("Super+"), "Hotkeys must put the action before its chord"

    # File read-only indicators skip the action, independently of host utility policy.
    run(page(1)+right+esc, state(readonly=True), policy=True)
    assert not any(call[:2] == ["icewine","theme"] for call in tools())
    run(page(1)+esc, state(), file_state="theme=true transparency=true wallpaper=true monitors=true layout=false")
    assert b"Read Only" in last_output
    picked = str(root / "picture with spaces.png")
    for pick, code in ((picked+"\n",0),("",0),(picked+"\n",1)):
        run(page(1)+down*2+enter+esc, state(), pick=pick, pick_exit=code)
        assert any(call[0] == "yazi" for call in tools())
        assert (["icewine","wallpaper",picked] in tools()) == (bool(pick) and code == 0)
        assert not list(root.glob("icewine-picker-*"))
    for code in (0,1,127):
        run(tab+down*8+enter+esc, state(), hyprmon_exit=code)
        assert ["hyprmon"] in tools()
        assert b"live/save changes remain" in last_output
    (root / "hyprmon").rename(root / "hyprmon-hidden")
    try:
        run(esc, state(), size=(24,80), path=str(root))
        assert b"Hyprmon Unavailable" in last_output
    finally: (root / "hyprmon-hidden").rename(root / "hyprmon")
    # Fail malformed machine state before terminal ownership and commands.
    for wire in (state()+" terminal=true", state().replace("screenshot=none","screenshot=invalid"), state().replace("terminal=false","terminal=1")):
        run(b"", wire, valid=False)
        assert not tools()
    good = "themes=dracula,tokyo-night selected=tokyo-night policy=false level=med desktopLayout=scrolling theme=false transparency=false wallpaper=false monitors=false layout=false"
    for wire in (good+" unknown=false", good.replace("policy=false","policy=maybe"), good.replace("selected=tokyo-night","selected=missing"), good.replace("desktopLayout=scrolling","desktopLayout=invalid")):
        run(b"",state(),valid=False,appearance_wire=wire)
        assert not tools()
    # Undersized input has no side effects; recovery retains draft and focus.
    run(tab+right+esc, state(), size=(23,79))
    assert not saves() and not tools()
    run(tab+b" ", state(), size=(24,80), resize_steps=[((20,79),right+tab),((24,100),esc)])
print("PASS: pane/grid/entry/placement, separate drafts, legacy policy, mouse, overflow, handoffs and bootstrap TTY contracts")
