#!/usr/bin/env python3
"""Exercise the real clipboard adapter with disposable state and mocked commands."""
import ctypes
import hashlib
import importlib.machinery
import json
import os
from pathlib import Path
import selectors
import signal
import struct
import subprocess
import sys
import tempfile
import time
from urllib.parse import unquote, urlparse
from unittest.mock import patch
import zlib

sys.dont_write_bytecode = True
source = Path(__file__).resolve().parent.parent
clipboard = importlib.machinery.SourceFileLoader("clipboard", str(source / "scripts/clipboard")).load_module()

def png(width=2, height=1):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\x00\xff\x00")) + chunk(b"IEND", b""))


def thumbnail_path(row):
    url = urlparse(row["thumbnail"])
    assert url.scheme == "file" and not url.netloc
    return Path(unquote(url.path))

# Only external command contracts are substituted; state/identity/load logic is real.
TOOLS = r'''
import base64, json, os, pathlib, signal, sys, time
root = pathlib.Path(os.environ["CLIPBOARD_FIXTURE"])
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with (root / "calls").open("a") as log:
    log.write(json.dumps([name, args]) + "\n")
if (root / "fail").exists() and (root / "fail").read_text() in [name, args[-1] if args else ""]:
    sys.exit(1)
def selection():
    return json.loads((root / "selection").read_text())
if name == "wl-paste":
    if "--watch" in args:
        last = None
        while True:
            version = (root / "selection").stat().st_mtime_ns
            if version != last:
                last = version
                state = selection()
                subprocess = __import__("subprocess")
                callback = subprocess.Popen(args[args.index("--watch") + 1:], stdin=subprocess.PIPE,
                    env=os.environ | {"CLIPBOARD_STATE": state.get("state", "data")}, bufsize=0)
                if state.get("stall"):
                    # Match native waitpid with a producer holding its writer open.
                    try: callback.stdin.write(b"partial")
                    except BrokenPipeError: pass
                    callback.wait()
                    callback.stdin.close()
                else:
                    callback.communicate(input=base64.b64decode(state["data"]))
            time.sleep(.01)
    elif "--list-types" in args:
        print("\n".join(selection()["types"]))
    else:
        state = selection()
        if args[-1] not in state["types"]: sys.exit(1)
        if (root / "native-transfer").exists():
            # Pinned wl-paste forks cat and waits; the provider is external.
            subprocess = __import__("subprocess")
            transfer = subprocess.Popen(["cat", str(root / "transfer-fifo")],
                stdout=subprocess.DEVNULL if (root / "detach-transfer").exists() else None)
            (root / "transfer-pid").write_text(str(transfer.pid))
            if (root / "detach-transfer").exists():
                while not (root / "producer-ready").exists(): time.sleep(.01)
                print("complete")  # Waiter exits while its reader remains blocked.
            else:
                transfer.wait()
            sys.exit(0)
        sys.stdout.buffer.write(base64.b64decode(state["data"]))
        if state.get("stall"):
            sys.stdout.buffer.flush()
            while True: time.sleep(1)
elif name == "wl-copy":
    data = sys.stdin.buffer.read()
    if not (root / "competing-copy").exists():
        temp = root / ("copy-" + str(os.getpid()))
        temp.write_text(json.dumps({"types": [args[-1]], "data": base64.b64encode(data).decode()}))
        temp.replace(root / "selection")
    (root / "owner").write_text(str(os.getpid()))
    while True: time.sleep(1)
elif name == "cliphist":
    assert not any(k.startswith("CLIPHIST_") for k in os.environ)
    assert "CLIPBOARD_STATE" not in os.environ and "CLIPBOARD_TYPE" not in os.environ
    db = pathlib.Path(args[args.index("-db-path") + 1] + ".fixture")
    state = json.loads(db.read_text()) if db.exists() else {"sequence": 0, "items": []}
    action = args[-1]
    if action == "store":
        data = base64.b64encode(sys.stdin.buffer.read()).decode()
        state["sequence"] += 1
        state["items"] = [[str(state["sequence"]), data]] + [i for i in state["items"] if i[1] != data]
        state["items"] = state["items"][:int(args[args.index("-max-items") + 1])]
    elif action == "list":
        for ident, data in state["items"]:
            preview = " ".join(base64.b64decode(data).decode(errors="replace").split())[:160]
            print(ident + "\t" + preview)
    elif action in ("decode", "delete"):
        ident = sys.stdin.buffer.read().decode()
        found = next((i for i in state["items"] if i[0] == ident), None)
        if not found: sys.exit(1)
        if action == "decode": sys.stdout.buffer.write(base64.b64decode(found[1]))
        else: state["items"].remove(found)
    elif action == "wipe": state["items"] = []
    db.write_text(json.dumps(state))
elif name == "hyprctl":
    if args[-1] == "locked":
        print((root / "locked").read_text())
        if (root / "locked-next").exists():
            (root / "locked").write_text((root / "locked-next").read_text())
            (root / "locked-next").unlink()
    elif args[-1] == "activewindow": print((root / "active").read_text())
elif name == "wtype":
    if (root / "typing-wait").exists():
        (root / "typing-pid").write_text(str(os.getpid()))
        while True: time.sleep(1)
    (root / "typed").write_text(json.dumps(args))
'''

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "bin").mkdir()
    tool = root / "tool"
    tool.write_text("#!" + sys.executable + "\n" + TOOLS)
    tool.chmod(0o755)
    for name in ("cliphist", "wl-paste", "wl-copy", "hyprctl", "wtype"):
        (root / "bin" / name).symlink_to(tool)
    runtime = root / "runtime"
    runtime.mkdir(mode=0o700)
    history_dir = runtime / "unit"
    history_dir.mkdir(mode=0o700)
    env = {"PATH": str(root / "bin") + ":" + os.environ["PATH"], "CLIPBOARD_FIXTURE": str(root),
           "XDG_RUNTIME_DIR": str(runtime), "CLIPHIST_DB_PATH": "/must-not-use", "HOME": str(root)}
    import base64
    def select(data, mime="text/plain;charset=utf-8", state="data", extra=(), stall=False):
        temporary = root / "next"
        temporary.write_text(json.dumps(dict(data=base64.b64encode(data).decode(), types=[mime, *extra], state=state, stall=stall)))
        temporary.replace(root / "selection")
    def fails(action):
        try: action()
        except ValueError: return
        raise AssertionError("Failed operation was accepted")
    with patch.dict(os.environ, env):
        expiry_dir = runtime / "expiry"
        expiry_dir.mkdir()
        aged = clipboard.History(expiry_dir)
        with patch.object(clipboard.time, "monotonic", return_value=100) as clock:
            select(b"aged text")
            aged.observe()
            text_id = aged.rows[0]["id"]
            clock.return_value = 110
            select(png(), "image/png")
            aged.observe()
            image_id = aged.rows[0]["id"]
            image_path = thumbnail_path(aged.rows[0])
            clock.return_value = 400
            assert not aged.expire() and len(aged.rows) == 2, "Off expired history"
            for invalid in (-1, 1, 300.0, True, "300", None):
                fails(lambda: aged.change(dict(action="expiry", seconds=invalid)))
            aged.change(dict(action="expiry", seconds=300))
            assert text_id not in aged.metadata and image_path.exists(), "Age boundary/individual expiry"
            fails(lambda: aged.change(dict(action="load", id=text_id)))
            # Delayed notifications of the same offer never renew age.
            clock.return_value = 409.99
            aged.observe()
            assert aged.metadata[image_id][2] == 110 and not aged.expire()
            clock.return_value = 410
            (root / "fail").write_text("delete")
            fails(aged.expire)
            assert image_id in aged.metadata and image_path.exists(), "Failed delete lost bookkeeping"
            (root / "fail").unlink()
            assert aged.expire() and not aged.metadata and not image_path.exists()
            aged.observe()
            assert not aged.rows, "Delayed current offer recreated expired image"
            fails(lambda: aged.change(dict(action="load", id=image_id)))
            assert clipboard.current_selection() == ("image/png", png()), "Expiry changed system clipboard"
            clock.return_value = 500
            select(b"new copy")
            aged.observe()
            aged.change(dict(action="expiry", seconds=3600))
            clock.return_value = 800
            assert not aged.expire()
        with patch.object(clipboard.time, "monotonic", return_value=800):
            aged.change(dict(action="expiry", seconds=300))
            assert not aged.rows, "Shortening did not immediately expire old entries"
            select(b"disabled again")
            aged.observe()
            aged.change(dict(action="expiry", seconds=0))
        with patch.object(clipboard.time, "monotonic", return_value=90000):
            assert not aged.expire()
        aged.change(dict(action="clear"))
        with patch.object(clipboard.time, "monotonic", return_value=100000) as clock:
            select(png(), "image/png")
            aged.observe()
            image_path = thumbnail_path(aged.rows[0])
            aged.change(dict(action="expiry", seconds=300))
            clock.return_value = 100300
            (root / "fail").write_text("delete")
            try:
                fails(aged.expire)
                aged.change(dict(action="clear"))
                assert not aged.rows and not aged.metadata and not image_path.exists(), "Clear could not recover from failed expiry deletion"
                assert not json.loads((expiry_dir / "db.fixture").read_text())["items"], "Clear retained backend entries"
                assert clipboard.current_selection() == ("image/png", png()), "Clear changed current clipboard"
            finally:
                (root / "fail").unlink()
        history = clipboard.History(history_dir)
        try:
            original = b"  <b>plain</b>; $(never-run)\nsecond line\n"
            select(original)
            history.observe()
            first = history.rows[0]["id"]
            assert history.rows[0]["thumbnail"] == "", "Text acquired an image source"
            assert history.snapshot()["active"] == first
            select(b"second")
            history.observe()
            second = history.rows[0]["id"]
            assert first != second and len(history.rows) == 2
            select(original)
            history.observe()
            assert len(history.rows) == 2 and history.rows[0]["id"] not in (first, second), "Dedupe did not refresh identity"
            fails(lambda: history.change(dict(action="load", id=first)))
            target = history.rows[0]["id"]
            select(b"other")
            history.observe()
            stored_at = history.metadata[target][2]
            assert history.change(dict(action="load", id=target))
            assert history.metadata[target][2] == stored_at
            assert base64.b64decode(json.loads((root / "selection").read_text())["data"]) == original
            assert history.snapshot()["active"] == target, "Load marker did not follow confirmed selection"
            # Confirmation reads must not acknowledge an unstored stable external copy.
            select(b"competing external copy")
            (root / "competing-copy").touch()
            try:
                fails(lambda: history.change(dict(action="load", id=target)))
                history.observe()  # The real queued watcher notification.
                assert history.rows[0]["preview"] == "competing external copy"
                assert history.snapshot()["active"] == history.rows[0]["id"]
            finally:
                (root / "competing-copy").unlink()
            assert history.change(dict(action="load", id=target))
            history.change(dict(action="remove", id=target))
            assert history.snapshot()["active"] == "" and history.current is not None
            history.observe()  # Delayed own-copy event cannot undo removal.
            assert all(row["id"] != target for row in history.rows)
            (root / "fail").write_text("wipe")
            before = list(history.rows)
            fails(lambda: history.change(dict(action="clear")))
            assert history.rows == before, "Failed clear lost visible history"
            (root / "fail").unlink()
            history.change(dict(action="clear"))
            history.observe()
            assert not history.rows, "Queued event silently restored cleared history"
            select(b"secret", extra=("x-kde-passwordManagerHint",))
            history.observe()
            assert not history.rows and history.current is None
            select(b"unsupported", "text/html")
            history.observe()
            assert history.current is None and not history.rows
            select(b" \n")
            history.observe()
            assert history.current is None
            select(b"x" * (clipboard.LIMIT + 1))
            fails(history.observe)
            assert history.current is None and not history.rows
            for invalid in (b"\x89PNG\r\n\x1a\nfixture bytes", png(0, 1), png(16385, 1),
                            png(4001, 4000), png() + b"x" * clipboard.LIMIT):
                assert history.thumbnail("invalid", invalid) == ""
            assert not list(history_dir.glob("*.png")), "Rejected image left a preview file"
            select(b"\x89PNG\r\n\x1a\nmalformed", "image/png")
            history.observe()
            assert history.rows[0]["image"] and not history.rows[0]["thumbnail"]
            image = png()
            select(image, "image/png")
            history.observe()
            assert history.rows[0]["image"]
            image_id = history.rows[0]["id"]
            image_path = thumbnail_path(history.rows[0])
            assert image_path.parent == history_dir and image_path.read_bytes() == image
            assert image_path.stat().st_mode & 0o777 == 0o600, "Preview file is not private"
            for action in ("delete", "wipe"):
                (root / "fail").write_text(action)
                fails(lambda: history.change(dict(action="remove" if action == "delete" else "clear", id=image_id)))
                assert image_path.read_bytes() == image, "Failed deletion discarded a live preview"
                (root / "fail").unlink()
            history.observe()
            assert thumbnail_path(history.rows[0]) == image_path, "Unchanged offer recreated its preview"
            select(b"different")
            assert history.change(dict(action="load", id=image_id))
            assert json.loads((root / "selection").read_text())["types"] == ["image/png"]
            # Actual native lock/focus/content checks must all precede finite input.
            identity = clipboard.fingerprint("image/png", image)
            (root / "locked").write_text('{"locked":false}')
            (root / "active").write_text('{"stableId":"1ab"}')
            clipboard.paste("1ab", *identity)
            assert json.loads((root / "typed").read_text()) == ["-M", "ctrl", "-P", "v", "-p", "v", "-m", "ctrl"]
            (root / "typed").unlink()
            (root / "locked-next").write_text('{"locked":true}')
            fails(lambda: clipboard.paste("1ab", *identity))
            assert not (root / "typed").exists(), "Lock change during native preflight reached input"
            for locked, active in [('{"locked":true}', '{"stableId":"1ab"}'),
                                   ('{}', '{"stableId":"1ab"}'),
                                   ('{"locked":false}', '{"stableId":"different"}')]:
                (root / "locked").write_text(locked)
                (root / "active").write_text(active)
                fails(lambda: clipboard.paste("1ab", *identity))
                assert not (root / "typed").exists()
            select(b"replaced")
            fails(lambda: clipboard.paste("1ab", *identity))
            assert not (root / "typed").exists()
            select(image, "image/png")
            (root / "locked").write_text('{"locked":false}')
            (root / "active").write_text('{"stableId":"1ab"}')
            (root / "typing-wait").touch()
            sender = subprocess.Popen([sys.executable, str(source / "scripts/clipboard"), "paste", "1ab", *identity],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            try:
                for _ in range(100):
                    if (root / "typing-pid").exists(): break
                    time.sleep(.01)
                assert (root / "typing-pid").exists()
                typing_pid = int((root / "typing-pid").read_text())
                sender.terminate()
                sender.wait(timeout=3)
                try: os.kill(typing_pid, 0)
                except ProcessLookupError: pass
                else: raise AssertionError("Cancelled paste orphaned its input client")
            finally:
                clipboard.stop(sender)
                (root / "typing-wait").unlink()
            history.observe(state="nil")
            assert history.snapshot()["active"] == ""
            history.change(dict(action="clear"))
            assert not image_path.exists() and not history.thumbnails
            select(image, "image/png")
            history.observe()
            image_path = thumbnail_path(history.rows[0])
            history.change(dict(action="remove", id=history.rows[0]["id"]))
            assert not image_path.exists() and not history.thumbnails
            select(image + b"eviction fixture", "image/png")
            history.observe()
            image_path = thumbnail_path(history.rows[0])
            for i in range(51):
                select(str(i).encode())
                history.observe()
            assert len(history.rows) == 50 and history.rows[0]["preview"] == "50"
            assert not image_path.exists() and not history.thumbnails, "Eviction retained image bytes"
        finally:
            clipboard.stop(history.owner)
        # Reap only fixture orphans locally; never scan or signal provider/app PIDs.
        assert ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) == 0  # PR_SET_CHILD_SUBREAPER
        def reader_gone(pid):
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                try:
                    if os.waitpid(pid, os.WNOHANG)[0] == pid: return
                except ChildProcessError:
                    try: os.kill(pid, 0)
                    except ProcessLookupError: return
                time.sleep(.01)
            raise AssertionError("Owned transfer reader survived command cleanup")
        # Actual read_selection, including cancellation through the real paste adapter.
        for mode in ("timeout", "cancel", "ordinary"):
            select(b"disposable transfer")
            (root / "native-transfer").touch()
            os.mkfifo(root / "transfer-fifo", 0o600)
            if mode == "ordinary": (root / "detach-transfer").touch()
            producer = subprocess.Popen([sys.executable, "-c", """
import pathlib, sys, time
root = pathlib.Path(sys.argv[1])
with (root / "transfer-fifo").open("wb", buffering=0) as output:
    output.write(b"partial fixture")
    (root / "producer-ready").touch()
    while True: time.sleep(1)
""", str(root)], start_new_session=True)
            reader_pid = None
            reader_cleaned = False
            sender = None
            try:
                argv = ["wl-paste", "--no-newline", "--type", clipboard.TYPES[0]]
                if mode == "cancel":
                    identity = clipboard.fingerprint(clipboard.TYPES[0], b"disposable transfer")
                    sender = subprocess.Popen([sys.executable, str(source / "scripts/clipboard"),
                        "paste", "1ab", *identity], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        start_new_session=True)
                    for _ in range(200):
                        if (root / "producer-ready").exists(): break
                        time.sleep(.01)
                    assert (root / "producer-ready").exists(), "Transfer never started"
                    sender.terminate()
                    sender.wait(timeout=3)
                    assert sender.stderr.read() == b""
                elif mode == "timeout":
                    fails(lambda: clipboard.read_selection(argv))
                else:
                    assert clipboard.read_selection(argv) == b"complete\n"
                reader_pid = int((root / "transfer-pid").read_text())
                reader_gone(reader_pid)
                reader_cleaned = True
                assert producer.poll() is None, "Reader cleanup signalled the external producer"
            finally:
                clipboard.stop(sender)
                # Known fixture PID only, including cleanup if an assertion failed.
                if not reader_cleaned and reader_pid is None and (root / "transfer-pid").exists():
                    reader_pid = int((root / "transfer-pid").read_text())
                if not reader_cleaned and reader_pid is not None:
                    try: os.kill(reader_pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    try: os.waitpid(reader_pid, 0)
                    except ChildProcessError: pass
                clipboard.stop(producer)
                for name in ("native-transfer", "detach-transfer", "transfer-fifo", "transfer-pid", "producer-ready"):
                    (root / name).unlink(missing_ok=True)
        # Real callback must notify/exit even while its provider keeps the pipe open.
        for state in ("data", "sensitive", "nil"):
            reader, writer = os.pipe()
            os.write(writer, b"partial fixture")
            callback = subprocess.Popen([sys.executable, str(source / "scripts/clipboard"), "changed"],
                stdin=reader, stdout=subprocess.PIPE, env=os.environ | {"CLIPBOARD_STATE": state},
                start_new_session=True)
            os.close(reader)
            try:
                with selectors.DefaultSelector() as ready:
                    ready.register(callback.stdout, selectors.EVENT_READ)
                    assert ready.select(1), "Callback waited for provider EOF before invalidating"
                    assert callback.stdout.readline().decode().strip() == state
                callback.wait(timeout=1)
            finally:
                os.close(writer)
                clipboard.stop(callback)
        # Exercise real watcher/request plumbing and runtime cleanup on shell stop/lock.
        select(b"session fixture")
        clock_file = root / "clock-offset"
        clock_file.write_text("0")
        serve_code = """
import pathlib, runpy, signal, sys, time
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
clock_file = pathlib.Path(sys.argv[2])
clock = time.monotonic
time.monotonic = lambda: clock() + float(clock_file.read_text())
adapter = runpy.run_path(sys.argv[1], run_name="clipboard_fixture")
adapter["serve"]()
"""
        process = subprocess.Popen([sys.executable, "-c", serve_code, str(source / "scripts/clipboard"), str(clock_file)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=os.environ, bufsize=0)
        def message(predicate):
            with selectors.DefaultSelector() as ready:
                ready.register(process.stdout, selectors.EVENT_READ)
                for _ in range(10):
                    assert ready.select(3), "Backend response timed out"
                    line = process.stdout.readline()
                    assert line, process.stderr.read().decode()
                    value = json.loads(line)
                    if predicate(value): return value
                raise AssertionError("Backend response missing")
        try:
            state = message(lambda state: len(state["entries"]) == 1)
            assert state["active"] == state["entries"][0]["id"]
            select(b"stalled provider", stall=True)
            state = message(lambda state: bool(state["error"]))
            assert not state["active"] and len(state["entries"]) == 1, "Stalled transfer left a stale highlight"
            select(b"later stable copy")
            state = message(lambda state: state["active"] and len(state["entries"]) == 2)
            assert not state["error"] and state["entries"][0]["preview"] == "later stable copy"
            for status in ("sensitive", "nil"):
                select(b"private fixture", state=status, stall=True)
                state = message(lambda state: not state["active"])
                assert not state["error"] and len(state["entries"]) == 2
            select(b"after nil")
            state = message(lambda state: state["active"] and len(state["entries"]) == 3)
            process.stdin.write(b'{"action":"clear","request":1}\n')
            state = message(lambda state: state["request"] == 1)
            assert not state["entries"] and not state["active"] and not state["error"]
            select(png(), "image/png")
            state = message(lambda state: state["entries"] and state["entries"][0]["image"])
            session_image = thumbnail_path(state["entries"][0])
            assert session_image.read_bytes() == png()
            image_id = state["entries"][0]["id"]
            process.stdin.write(b'{"action":"expiry","seconds":300,"request":2}\n')
            message(lambda state: state["request"] == 2)
            clock_file.write_text("301")
            state = message(lambda state: not state["entries"])
            assert not state["active"] and not session_image.exists(), "Idle expiry missed cleanup/refresh"
            assert clipboard.current_selection() == ("image/png", png())
            process.stdin.write((json.dumps(dict(action="load", id=image_id, request=3)) + "\n").encode())
            state = message(lambda state: state["request"] == 3)
            assert not state["loaded"] and state["error"], "Stale paste/load was confirmed"
        finally:
            process.terminate()
            process.wait(timeout=4)
        assert not list(runtime.glob("icewine-clipboard-*")), "Runtime history survived orderly stop"
        assert not session_image.exists(), "Image bytes survived backend stop/lock"
        assert process.stderr.read() == b"", "Normal operation leaked into logs"
    print("PASS clipboard: expiry age boundaries, Off/changed limits, idle cleanup, stale load rejection, duplicate suppression, failed-delete retry; real adapter ordering/dedupe, identities, external/active state, literal bytes, PNG, bounds, deletion failures, sensitive hints, guarded finite input, owned waiter/reader cleanup on timeout/cancel/completion and runtime cleanup")
