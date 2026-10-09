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
    def run(keys, state):
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
        assert code == 0 and sent, output.decode(errors="replace")
        assert b"Icewine Installer" in rendered
        assert b"Overwrite existing dotfiles" in rendered
        assert b"[ Apply ]" in rendered and b"[ Cancel ]" in rendered
        assert (b"NixOS: utility selections are read-only." in rendered) == (state.split()[0] == "1")
        return [json.loads(line) for line in log.read_text().splitlines()]
    assert run(b" \x1b", "0 0 0 0 0 0 0 0 0") == [["state"]]
    assert run(b"\t"*10+b"\r", "0 0 0 0 0 0 0 0 0") == [["state"]]
    assert run(b" "+b"\t"*9+b"\r", "0 0 0 0 0 0 0 0 0") == [
        ["state"], ["apply", "1", "0", "0", "0", "0", "0", "0", "0", "0"]]
    # NixOS focus skips utility rows; Space only checks overwrite.
    assert run(b" \t\r", "1 1 0 0 0 0 0 0 0") == [
        ["state"], ["apply", "1", "0", "0", "0", "0", "0", "0", "0", "1"]]
    assert run(b"\t\r", "1 1 0 0 0 0 0 0 0")[-1][-1] == "0"
print("PASS: real TTY cancel, editable/read-only navigation, Apply and fresh overwrite default")
