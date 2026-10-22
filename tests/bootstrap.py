#!/usr/bin/env python3
"""Exercise the real shell bootstrap with isolated developer acquisition/build tools."""
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import shutil
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
elif name=="pacman": sys.exit(1 if mode in ("no-provider", "native-rust", "unowned") else 0)
elif name=="sudo":
 assert args[:5]==["pacman","-Syu","--needed","base-devel","git"],args
 if mode in ("no-provider", "native-rust"): pathlib.Path(os.environ["TMPDIR"], "provider-installed").touch()
 sys.exit(1 if mode=="prerequisite" else 0)
elif name in ("cargo", "rustc"):
 if mode in ("no-provider", "native-rust"): sys.exit(0 if pathlib.Path(os.environ["TMPDIR"], "provider-installed").exists() else 1)
 if mode in ("proxy", "toolchain-fail"):
  private=pathlib.Path(os.environ.get("RUSTUP_HOME", "/missing"))
  sys.exit(0 if os.environ.get("RUSTUP_TOOLCHAIN")=="stable" and (private/"installed").exists() else 1)
elif name=="rustup":
 assert args==["toolchain","install","stable","--profile","minimal","--no-self-update"],args
 assert os.environ["RUSTUP_HOME"].startswith(os.environ["TMPDIR"])
 assert os.environ["RUSTUP_TOOLCHAIN"]=="stable"
 if mode=="toolchain-fail": sys.exit(1)
 private=pathlib.Path(os.environ["RUSTUP_HOME"])
 private.mkdir()
 (private/"installed").touch()
elif name=="git":
 if "ls-remote" in args:
  if mode=="resolve": sys.exit(1)
  print(("invalid" if mode=="invalid-remote" else "a"*40)+"\\tHEAD")
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
    for name in ("id", "uname", "sed", "pacman", "git", "makepkg", "cargo", "rustc", "rustup", "sudo", "python3"):
        (tools / name).symlink_to(stub)
    def run(mode="ok", answer=b"yes\n", tty=True, latest=False, shell="sh"):
        log.unlink(missing_ok=True)
        work = root / (mode + "-work")
        work.mkdir(exist_ok=True)
        env = dict(os.environ, HOME=str(home), PATH=str(tools)+":"+os.environ["PATH"],
                   BOOT_LOG=str(log), BOOT_MODE=mode, TMPDIR=str(work))
        command = ([shell, "-c", 'cat "$argv[1]" | sh', str(source / "install.sh")]
                   if shell == "fish" else
                   [shell, "-c", 'cat "$1" | sh' if latest else 'cat "$1" | sh -s -- "$2"',
                    "bootstrap", str(source / "install.sh"), *([] if latest else [revision])])
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
    for mode in ("download", "mismatch", "integrity", "build", "prerequisite", "nixos", "toolchain-fail"):
        code, output, calls = run(mode)
        assert code != 0 and b"BOOT_MANAGER" not in output, (mode, output)
        if mode in ("prerequisite", "nixos"):
            assert not any(call[0]=="git" for call in calls)
    for answer in (b"no\n", b"\x03"):
        code, output, calls=run(answer=answer)
        assert b"BOOT_MANAGER" not in output and not any(call[0]=="git" for call in calls)
    code, output, calls=run(tty=False)
    assert code != 0 and not any(call[0]=="git" for call in calls)
    code, output, calls = run("unowned")
    assert code != 0 and b"Working Rust toolchain is outside pacman" in output
    assert not any(call[0] == "sudo" for call in calls)
    for mode in ("resolve", "invalid-remote"):
        code, output, calls = run(mode, latest=True)
        assert code != 0 and b"BOOT_MANAGER" not in output, output
    for mode in ("proxy", "no-provider", "native-rust"):
        rustup_link = tools / "rustup"
        if mode == "native-rust": rustup_link.unlink()
        try:
            code, output, calls = run(mode)
        finally:
            if mode == "native-rust": rustup_link.symlink_to(stub)
        assert code == 0 and b"BOOT_MANAGER" in output, output
        installs = [call for call in calls if call[0] == "rustup"]
        assert bool(installs) == (mode == "proxy")
        if mode in ("no-provider", "native-rust"):
            assert ("rust" if mode == "native-rust" else "rustup") in next(call for call in calls if call[0] == "sudo")
    for shell in ("sh", "fish"):
        if not shutil.which(shell):
            print(f"SKIP: {shell} not installed; command compatibility needs integration check")
            continue
        code, output, calls = run(latest=True, shell=shell)
        assert code == 0 and b"BOOT_MANAGER" in output, output
        assert next(call for call in calls if call[0]=="git" and "fetch" in call)[-1] == revision
    code, output, calls=run()
    assert code == 0 and b"BOOT_MANAGER --bootstrap" in output, output
    assert not any(call[0] == "rustup" for call in calls), "working toolchain was replaced"
    fetch=next(call for call in calls if call[0]=="git" and "fetch" in call)
    assert fetch[-1]==revision
    builds=[call for call in calls if call[0]=="makepkg"]
    assert builds and all("-s" not in call and "-i" not in call and "--syncdeps" not in call and "--install" not in call for call in builds)
print("PASS: piped TTY bootstrap, revision/integrity, cancellation, NixOS ownership and acquisition/build/prerequisite failures")
