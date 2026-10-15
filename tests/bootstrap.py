#!/usr/bin/env python3
"""Exercise the real shell bootstrap with isolated developer acquisition/build tools."""
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import tempfile
import time

source = Path(sys.argv[1]).resolve()
revision = "a" * 40
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    tools = root / "tools"
    tools.mkdir()
    log = root / "calls"
    home = root / "home"
    (home / ".config").mkdir(parents=True)
    # These programs only create synthetic download/build outputs inside TMPDIR.
    stub = tools / "stub"
    stub.write_text("#!" + sys.executable + "\n" + '''import json,os,pathlib,sys
name=pathlib.Path(sys.argv[0]).name
args=sys.argv[1:]
with open(os.environ["BOOT_LOG"],"a") as stream: stream.write(json.dumps([name,*args])+"\\n")
mode=os.environ["BOOT_MODE"]
if name=="id": print("1000")
elif name=="uname": print("x86_64")
elif name=="sed": print("nixos" if mode=="nixos" else "arch")
elif name=="pacman": sys.exit(1 if mode=="prerequisite" else 0)
elif name=="git":
 if "fetch" in args and mode=="download": sys.exit(1)
 if "rev-parse" in args: print(("b" if mode=="mismatch" else "a")*40)
 if "fsck" in args and mode=="integrity": sys.exit(1)
 if "archive" in args:
  sys.stdout.buffer.write(b"synthetic local archive")
 if "show" in args: print("# synthetic recipe, never executed")
elif name=="makepkg":
 if mode=="build": sys.exit(1)
 target=pathlib.Path("src/icewine/manager/target/release/icewine-manage")
 target.parent.mkdir(parents=True)
 target.write_text("#!/bin/sh\\nprintf 'BOOT_MANAGER %s\\\\n' \\\"$*\\\"\\n")
 target.chmod(0o755)
''')
    stub.chmod(0o755)
    for name in ("id", "uname", "sed", "pacman", "git", "makepkg", "cargo", "python3"):
        (tools / name).symlink_to(stub)
    def run(mode="ok", answer=b"yes\n", tty=True):
        log.unlink(missing_ok=True)
        work = root / (mode + "-work")
        work.mkdir(exist_ok=True)
        env = dict(os.environ, HOME=str(home), PATH=str(tools)+":"+os.environ["PATH"],
                   BOOT_LOG=str(log), BOOT_MODE=mode, TMPDIR=str(work))
        command = ["sh", "-c", 'cat "$1" | sh -s -- "$2"', "bootstrap", str(source / "install.sh"), revision]
        if not tty:
            result = subprocess.run(command, env=env, stdin=subprocess.DEVNULL, capture_output=True, start_new_session=True)
            return result.returncode, result.stdout+result.stderr, [] if not log.exists() else [json.loads(line) for line in log.read_text().splitlines()]
        master, slave = pty.openpty()
        def controlling_tty():
            os.setsid()
            fcntl.ioctl(0, __import__("termios").TIOCSCTTY, 0)
        process = subprocess.Popen(command, env=env, stdin=slave, stdout=slave, stderr=slave, preexec_fn=controlling_tty)
        os.close(slave)
        output = bytearray()
        sent = False
        deadline = time.monotonic()+8
        while process.poll() is None and time.monotonic()<deadline:
            if select.select([master], [], [], .05)[0]:
                try: output.extend(os.read(master, 65536))
                except OSError: break
            if not sent and b"Type yes" in output:
                os.write(master, answer)
                sent = True
        if process.poll() is None:
            try: process.wait(timeout=1)
            except subprocess.TimeoutExpired: process.kill()
        code = process.wait()
        while select.select([master], [], [], 0)[0]:
            try: output.extend(os.read(master, 65536))
            except OSError: break
        os.close(master)
        calls=[] if not log.exists() else [json.loads(line) for line in log.read_text().splitlines()]
        return code, bytes(output), calls
    for mode in ("download", "mismatch", "integrity", "build", "prerequisite", "nixos"):
        code, output, calls = run(mode)
        assert code != 0 and b"BOOT_MANAGER" not in output, (mode, output)
        if mode in ("prerequisite", "nixos"):
            assert not any(call[0]=="git" for call in calls)
    for answer in (b"no\n", b"\x03"):
        code, output, calls=run(answer=answer)
        assert b"BOOT_MANAGER" not in output and not any(call[0]=="git" for call in calls)
    code, output, calls=run(tty=False)
    assert code != 0 and not any(call[0]=="git" for call in calls)
    code, output, calls=run()
    assert code == 0 and b"BOOT_MANAGER --bootstrap" in output, output
    fetch=next(call for call in calls if call[0]=="git" and "fetch" in call)
    assert fetch[-1]==revision
    builds=[call for call in calls if call[0]=="makepkg"]
    assert builds and all("-s" not in call and "-i" not in call and "--syncdeps" not in call and "--install" not in call for call in builds)
print("PASS: piped TTY bootstrap, revision/integrity, cancellation, NixOS ownership and acquisition/build/prerequisite failures")
