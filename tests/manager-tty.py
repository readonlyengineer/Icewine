#!/usr/bin/env python3
"""Drive the built Ratatui frontend through a pseudo-TTY, without host changes."""
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

def rendered_frames(output, size):
    # Ratatui emits positioned cell deltas, not complete text on page changes.
    # Replay its cursor/clear commands; retain completed draws for assertions.
    rows, columns = size
    screen = [[" "] * columns for _ in range(rows)]
    x = y = 0
    frames = []
    for token in re.split(r"(\x1b\[[0-?]*[ -/]*[@-~])", output.decode(errors="replace")):
        if token.startswith("\x1b["):
            command, args = token[-1], token[2:-1]
            if command in ("H", "f"):
                position = [int(value or 1) for value in args.split(";")]
                y, x = position[0] - 1, (position[1] if len(position) > 1 else 1) - 1
            elif command == "J" and args == "2":
                screen = [[" "] * columns for _ in range(rows)]
            elif token == "\x1b[?25l":
                frames.append("\n".join("".join(row) for row in screen).encode())
        else:
            for char in token:
                if char == "\r": x = 0
                elif char == "\n": y += 1
                elif char >= " ":
                    if 0 <= y < rows and 0 <= x < columns: screen[y][x] = char
                    x += 1
    return frames

binary = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    backend = root / "icewine-manage-backend"
    backend.write_text('#!' + sys.executable + '\n' + '''import json,os,sys
with open(os.environ["TUI_LOG"],"a") as stream: stream.write(json.dumps(sys.argv[1:])+"\\n")
if sys.argv[1:] == ["state"]: print(os.environ["TUI_STATE"])
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
elif args == ["transparency"]: print("Transparency: " + saved["transparency"] + " (off, low, med, high)")
elif args[0] in ("theme", "transparency"):
 saved[args[0]]=args[1]
 with open(os.environ["TUI_APPEARANCE"],"w") as stream: json.dump(saved,stream)
 if os.environ["TUI_DELIVERY_FAIL"] == "1":
  print("live delivery failed after saving selection", file=sys.stderr); sys.exit(1)
elif os.environ["TUI_COMMAND_FAIL"] == "1":
 print("invalid image; saved preference unchanged", file=sys.stderr); sys.exit(1)
''')
    icewine.chmod(0o755)
    for tool in ("yazi", "hyprmon"):
        executable = root / tool
        executable.write_text('#!' + sys.executable + '\n' + '''import json,os,sys,termios
assert os.isatty(0)
assert termios.tcgetattr(0)[3] & termios.ICANON, "manager did not release raw mode"
with open(os.environ["TUI_TOOLS"],"a") as stream: stream.write(json.dumps([os.path.basename(sys.argv[0]),*sys.argv[1:]])+"\\n")
if os.path.basename(sys.argv[0]) == "yazi":
 with open(sys.argv[2],"w") as stream: stream.write(os.environ["TUI_PICK"])
 sys.exit(int(os.environ["TUI_PICK_EXIT"]))
sys.exit(int(os.environ["TUI_HYPRMON_EXIT"]))
''')
        executable.chmod(0o755)
    log = root / "calls"
    def run(keys, state, valid=True, policy=False, pick="", pick_exit=0, hyprmon_exit=0, auth=False, command_fail=False, delivery_fail=False, size=(24, 100)):
        global last_output, last_frames
        log.unlink(missing_ok=True)
        tool_log.unlink(missing_ok=True)
        appearance_state = root / "appearance-state"
        appearance_state.write_text(json.dumps({"theme": "tokyo-night", "transparency": "med"}))
        data = root / "data/icewine/wallpapers"
        data.mkdir(parents=True, exist_ok=True)
        (data / "auth.img").unlink(missing_ok=True)
        if auth: (data / "auth.img").write_bytes(b"fixture")
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", *size, 0, 0))
        env = dict(os.environ, TERM="xterm", PATH=str(root)+":"+os.environ["PATH"], TUI_LOG=str(log), TUI_STATE=state,
                   TUI_TOOLS=str(tool_log), TUI_POLICY=str(int(policy)),
                   TUI_PICK=pick, TUI_PICK_EXIT=str(pick_exit), TUI_HYPRMON_EXIT=str(hyprmon_exit),
                   TUI_COMMAND_FAIL=str(int(command_fail)), TUI_DELIVERY_FAIL=str(int(delivery_fail)),
                   TUI_APPEARANCE=str(appearance_state), XDG_DATA_HOME=str(root / "data"),
                   ICEWINE_WALLPAPER_DATA_HOME=str(root / "data"), TMPDIR=str(root))
        process = subprocess.Popen([str(binary)], stdin=slave, stdout=slave, stderr=slave, env=env)
        os.close(slave)
        output = bytearray()
        deadline = time.monotonic() + 10
        sent = False
        while process.poll() is None and time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    output.extend(os.read(master, 65536))
                except OSError:
                    break
            frames = rendered_frames(output, size)
            rendered = b"\n".join(frames)
            if not sent and frames:
                assert b"Icewine Installer (1/2) | Tab: Appearance (2/2)" in rendered
                os.write(master, keys)
                sent = True
        if process.poll() is None:
            process.kill()
        code = process.wait()
        while select.select([master], [], [], 0)[0]:
            try: output.extend(os.read(master, 65536))
            except OSError: break
        last_frames = rendered_frames(output, size)
        rendered = b"\n".join(last_frames)
        if sent:
            assert termios.tcgetattr(master)[3] & termios.ICANON, "terminal raw mode was not restored"
        os.close(master)
        last_output = rendered
        assert code == (0 if valid else 1), output.decode(errors="replace")
        if not valid:
            assert not sent
            return [json.loads(line) for line in log.read_text().splitlines()]
        assert sent, output.decode(errors="replace")
        assert (b"Esc: cancel" if size[1] == 100 else b"Esc: canc") in rendered
        assert b"Icewine Installer" in rendered
        assert b"Overwrite existing dotfiles" in rendered
        assert b"[ Apply ]" in rendered and b"[ Cancel ]" in rendered
        assert (b"NixOS: utility selections are read-only." in rendered) == ("readonly=true" in state.split())
        return [json.loads(line) for line in log.read_text().splitlines()]
    ids = ("desktop", "terminal", "filemanager", "steam", "gamescope", "handheld", "login", "shellExtras")
    visible = 6 # Steam none hides its two children.
    def state(readonly=False, **selected):
        # Deliberately shuffle fields: identity must not depend on wire order.
        return " ".join([f"{name}={str(selected.get(name, "none" if name == "steam" else False)).lower()}" for name in reversed(ids)]
                        + [f"readonly={str(readonly).lower()}"])
    def applied(calls):
        assert calls[0] == ["state"] and calls[1][0] == "apply" and len(calls) == 2
        fields = dict(field.split("=") for field in calls[1][1:])
        assert len(fields) == len(ids) + 1 and set(fields) == {*ids, "overwrite"}
        return fields
    assert run(b" \x1b", state()) == [["state"]]
    assert run(b"\x1b[B"*(visible+2)+b"\r", state()) == [["state"]]
    expected = dict.fromkeys(ids, "false") | {"steam": "none", "desktop": "true", "overwrite": "false"}
    assert applied(run(b" "+b"\x1b[B"*(visible+1)+b"\r", state())) == expected
    # A second row toggles its own ID, not the backend's second field.
    expected["desktop"], expected["terminal"] = "false", "true"
    assert applied(run(b"\x1b[B "+b"\x1b[B"*visible+b"\r", state())) == expected
    # Right selects native, defaults Gamescope on and leaves Handheld off.
    chosen = applied(run(b"\x1b[B"*3+b"\x1b[C"+b"\x1b[B"*5+b"\r", state()))
    assert chosen["steam"] == "native" and chosen["gamescope"] == "true" and chosen["handheld"] == "false"
    # Flatpak skips unsupported Handheld; Gamescope may be turned off.
    chosen = applied(run(b"\x1b[B"*3+b"\x1b[C\x1b[C\x1b[B "+b"\x1b[B"*4+b"\r", state()))
    assert chosen["steam"] == "flatpak" and chosen["gamescope"] == "false" and chosen["handheld"] == "false"
    # Native+desktop allows Handheld; turning desktop off clears it.
    chosen = applied(run(b" \x1b[B\x1b[B\x1b[B\x1b[C\x1b[B\x1b[B "+b"\x1b[B"*4+b"\r", state()))
    assert chosen["handheld"] == "true"
    chosen = applied(run(b" "+b"\x1b[B"*8+b"\r", state(desktop=True, steam="native", gamescope=True, handheld=True)))
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
    # Page changes preserve utility focus and pending selections; appearance is live.
    chosen = applied(run(b" \x1b[B" + tab + b"\x1b[C\x1b[B\x1b[C" + tab + b" " + tab + b"\x1b[C" + tab + down*visible+b"\r", state()))
    assert chosen["desktop"] == "true" and chosen["terminal"] == "true"
    assert ["icewine", "theme", "dracula"] in tools()
    assert ["icewine", "transparency", "high"] in tools()
    assert ["icewine", "transparency", "off"] in tools(), "appearance focus was not preserved"
    assert b"Tab: page" in last_output
    assert b"Up/down: move" in last_output
    assert b"Appearance updates immediately." in last_output
    # The navigation affordance and controls fit a conventional 80-column TTY
    # as well as the wider default; exercise a round trip at both sizes.
    for size in ((24, 80), (24, 100)):
        assert run(tab + tab + b"\x1b", state(), size=size) == [["state"]]
        assert b"Appearance updates immediately." in last_output
        assert any(b"Icewine Appearance (2/2) | Tab: Installer (1/2)" in frame for frame in last_frames)
        assert b"Icewine Installer (1/2) | Tab: Appearance (2/2)" in last_frames[-1]
    # Overwrite survives page switches and Apply works from either page.
    for finish in (tab + down + b"\r", down*5 + b"\r"):
        assert applied(run(down*visible + b" " + tab + finish, state()))["overwrite"] == "true"
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
    assert run(tab+b"\x1b[B"*3+b"\r\x1b", state(), pick=picked+"\n") == [["state"]]
    assert ["icewine", "wallpaper", "--auth", picked] in tools()
    assert run(tab+b"\x1b[B"*3+b"\r\x1b", state(), auth=True) == [["state"]]
    assert ["icewine", "wallpaper", "--auth-reset"] in tools()
    assert not any(call[0] == "yazi" for call in tools())
    # HyprMon owns live/save semantics; zero exit must not claim a successful save.
    for exit_code in (0, 1, 127):
        assert run(tab+b"\x1b[B"*4+b"\r"+tab+b"\x1b", state(), hyprmon_exit=exit_code) == [["state"]]
        assert ["hyprmon"] in tools()
    assert b"HyprMon live/save changes remain after Cancel." in last_output
    (root / "hyprmon").chmod(0o600)
    try:
        assert run(tab+b"\x1b[B"*4+b"\r\x1b", state()) == [["state"]]
        assert b"HyprMon unavailable:" in last_output
    finally: (root / "hyprmon").chmod(0o755)
print("PASS: real TTY cancel, editable/read-only navigation, named selections, invalid state, Tab pages, appearance handoffs and fresh overwrite default")
