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

binary = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    backend = root / "icewine-manage-backend"
    backend.write_text('#!' + sys.executable + '\n' + '''import json,os,sys
with open(os.environ["TUI_LOG"],"a") as stream: stream.write(json.dumps(sys.argv[1:])+"\\n")
if sys.argv[1:] == ["state"]: print(os.environ["TUI_STATE"])
''')
    backend.chmod(0o755)
    log = root / "calls"
    def run(keys, state, valid=True):
        log.unlink(missing_ok=True)
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
        env = dict(os.environ, TERM="xterm", PATH=str(root)+":"+os.environ["PATH"], TUI_LOG=str(log), TUI_STATE=state)
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
            # Ratatui can render spaces between words with cursor positioning.
            rendered = re.sub(rb"\x1b\[\d+;\d+H", b" ", output)
            if not sent and b"Esc: cancel" in rendered:
                os.write(master, keys)
                sent = True
        if process.poll() is None:
            process.kill()
        code = process.wait()
        os.close(master)
        assert code == (0 if valid else 1), output.decode(errors="replace")
        if not valid:
            assert not sent
            return [json.loads(line) for line in log.read_text().splitlines()]
        assert sent, output.decode(errors="replace")
        assert b"Icewine Installer" in rendered
        assert b"Overwrite existing dotfiles" in rendered
        assert b"[ Apply ]" in rendered and b"[ Cancel ]" in rendered
        assert (b"NixOS: utility selections are read-only." in rendered) == ("readonly=true" in state.split())
        return [json.loads(line) for line in log.read_text().splitlines()]
    ids = ("desktop", "terminal", "filemanager", "gaming", "flatpak", "login", "shellExtras")
    def state(readonly=False, **selected):
        # Deliberately shuffle fields: identity must not depend on wire order.
        return " ".join([f"{name}={str(selected.get(name, False)).lower()}" for name in reversed(ids)]
                        + [f"readonly={str(readonly).lower()}"])
    def applied(calls):
        assert calls[0] == ["state"] and calls[1][0] == "apply" and len(calls) == 2
        fields = dict(field.split("=") for field in calls[1][1:])
        assert len(fields) == len(ids) + 1 and set(fields) == {*ids, "overwrite"}
        return fields
    assert run(b" \x1b", state()) == [["state"]]
    assert run(b"\t"*(len(ids)+2)+b"\r", state()) == [["state"]]
    expected = dict.fromkeys(ids, "false") | {"desktop": "true", "overwrite": "false"}
    assert applied(run(b" "+b"\t"*(len(ids)+1)+b"\r", state())) == expected
    # A second row toggles its own ID, not the backend's second field.
    expected["desktop"], expected["terminal"] = "false", "true"
    assert applied(run(b"\t "+b"\t"*len(ids)+b"\r", state())) == expected
    # Reverse navigation from the first control reaches Cancel.
    assert run(b"\x1b[Z\r", state()) == [["state"]]
    # NixOS focus skips utility rows; Space only checks overwrite.
    expected = dict.fromkeys(ids, "false") | {"desktop": "true", "overwrite": "true"}
    assert applied(run(b" \t\r", state(readonly=True, desktop=True))) == expected
    assert applied(run(b"\t\r", state(readonly=True, desktop=True)))["overwrite"] == "false"
    for invalid in (state() + " terminal=true", state().replace("terminal=false", "unknown=false"),
                    state().replace("terminal=false", ""), state().replace("terminal=false", "terminal=1")):
        assert run(b"", invalid, valid=False) == [["state"]]
print("PASS: real TTY cancel, editable/read-only navigation, named selections, invalid state and fresh overwrite default")
