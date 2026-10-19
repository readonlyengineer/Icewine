#!/usr/bin/env python3
"""Exercise the real SSH helper using only disposable agents and synthetic keys."""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest import mock

source = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("ssh_card", str(source / "scripts/ssh"))
spec = importlib.util.spec_from_loader(loader.name, loader)
ssh = importlib.util.module_from_spec(spec)
loader.exec_module(ssh)


def rejected(call, label):
    try:
        call()
    except (ssh.Unavailable, OSError):
        return
    raise AssertionError(label)


with tempfile.TemporaryDirectory(prefix="icewine-ssh-launcher-") as tools, tempfile.TemporaryDirectory(prefix="icewine-ssh-test-", dir="/dev/shm") as td:
    root = Path(td)
    home = root / "home"
    home.mkdir()
    keys = home / ".ssh"
    keys.mkdir()
    runtime = root / "runtime"
    runtime.mkdir(mode=0o700)
    askpass = Path(tools) / "askpass"
    askpass.write_text(f'#!{sys.executable}\nimport runpy\nrunpy.run_path({str(source / "scripts/ssh")!r}, run_name="__main__")\n')
    askpass.chmod(0o755)
    assert Path(sys.executable).is_absolute()
    env = dict(os.environ, HOME=str(home), XDG_RUNTIME_DIR=str(runtime),
               SSH_AUTH_SOCK=str(runtime / "ssh-agent"), ICEWINE_SSH_ASKPASS=str(askpass))
    env.pop("ICEWINE_SSH_PHRASE_FD", None)
    with mock.patch.dict(os.environ, env, clear=True):
        if "--input-only" in sys.argv:
            # Exercise the actual import branch without an agent/socket. The add
            # boundary still asks real OpenSSH to parse/decrypt the passed memfd.
            backend = ssh.Backend(home, runtime, 0)
            private = keys / "synthetic"
            phrase = "synthetic input phrase"
            popen = ssh.subprocess.Popen
            observed = []

            def observe_input(args, **kwargs):
                assert phrase not in repr((args, kwargs.get("env", {})))
                assert "PRIVATE KEY" not in repr((args, kwargs.get("env", {})))
                return popen(args, **kwargs)

            def parse(fd, phrase, origin, path, expected=""):
                assert stat.S_IMODE(os.fstat(fd).st_mode) == 0o600
                assert os.readlink(f"/proc/self/fd/{fd}").startswith("/memfd:")
                observed.append(path)
                public = ssh.public_fields(ssh.native(["ssh-keygen", "-y", "-f", f"/proc/self/fd/{fd}"],
                                                     phrase=phrase, descriptors=(fd,)))
                return "Parsed synthetic input", public

            with mock.patch.object(backend, "ownership", contextlib.nullcontext), mock.patch.object(backend, "status", return_value={}), mock.patch.object(backend, "add", parse), mock.patch.object(ssh.subprocess, "Popen", observe_input):
                for password in ("", phrase):
                    ssh.native(["ssh-keygen", "-q", "-t", "ed25519", "-f", str(private)], phrase=password, repeats=2)
                    text = private.read_text()
                    for request in (dict(private=text), dict(path=str(private))):
                        result = backend.mutate(dict(action="import", passphrase=password, **request))
                        assert result["public"].startswith("ssh-ed25519 ")
                        assert "PRIVATE KEY" not in json.dumps(result) and phrase not in json.dumps(result)
                    if password:
                        rejected(lambda: backend.mutate(dict(action="import", private=text, passphrase="wrong")), "Wrong pasted passphrase accepted")
                    private.unlink()
                    Path(str(private) + ".pub").unlink()
                for request in (dict(private=""), dict(private="x" * (ssh.LIMIT + 1)),
                                dict(private="not a private key"), dict(private=text, path="/ambiguous")):
                    rejected(lambda: backend.mutate(dict(action="import", **request)), "Invalid pasted input accepted")
            assert "" in observed and str(private) in observed
            assert not list(keys.iterdir()), "Pasted input wrote key files"
            print("PASS input-only: real file/paste import, encrypted/plain native parsing, memfd/argv/env/output confidentiality, invalid input")
            sys.exit(0)

        # The host assertions select foreground mode. A real native forked
        # listener must still fail the exact peer/MainPID check, not be accepted
        # merely because its socket is local and owned by this user.
        forked = subprocess.run(["ssh-agent", "-s", "-a", str(runtime / "ssh-agent")], capture_output=True, text=True, check=True)
        daemon = int(re.search(r"SSH_AGENT_PID=(\d+)", forked.stdout)[1])
        try:
            rejected(lambda: ssh.Backend(home, runtime, daemon).agent(), "Forked parent peer accepted as daemon MainPID")
        finally:
            os.kill(daemon, signal.SIGTERM)
            for _ in range(100):
                if not (runtime / "ssh-agent").exists():
                    break
                time.sleep(0.01)
        agent = subprocess.Popen(["ssh-agent", "-D", "-a", str(runtime / "ssh-agent")],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                if (runtime / "ssh-agent").exists():
                    break
                time.sleep(0.01)
            backend = ssh.Backend(home, runtime, agent.pid)
            initial = backend.dispatch({"action": "status"})
            assert initial["available"], initial["error"]
            print("PASS actual native foreground peer/MainPID contract; forked native parent remains rejected")
            phrase = "synthetic private phrase"
            imported = keys / "id_ed25519"
            ssh.native(["ssh-keygen", "-q", "-t", "ed25519", "-f", str(imported)], phrase=phrase, repeats=2)
            original = imported.read_bytes()
            public = ssh.public_fields(Path(str(imported) + ".pub").read_text())

            # Selected-row identity survives stale sidecars and replacement after discovery.
            expected = ssh.fingerprint(public)
            selected = next(e for e in backend.status()["entries"] if e["public"] == public)
            replacement = keys / "replacement"
            ssh.native(["ssh-keygen", "-q", "-t", "ed25519", "-f", str(replacement)], phrase=phrase, repeats=2)
            imported.write_bytes(replacement.read_bytes())
            stale = next(e for e in backend.status()["entries"] if e["public"] == public)
            assert stale["importPath"] == str(imported)
            additions = []
            real_native = ssh.native

            def observe_add(args, **kwargs):
                if args[:4] == ["ssh-add", "-q", "-k", "-"]:
                    additions.append(True)
                return real_native(args, **kwargs)

            with mock.patch.object(ssh, "native", observe_add):
                for row in (selected, stale):
                    rejected(lambda: backend.dispatch(dict(action="import", path=row["importPath"],
                             passphrase=phrase, expectedFingerprint=row["fingerprint"])), "Selected identity replacement accepted")
                for invalid in (False, [], "SHA256:bad", "x" * 10000):
                    rejected(lambda: backend.dispatch(dict(action="import", path=str(imported),
                             passphrase=phrase, expectedFingerprint=invalid)), "Invalid selected identity accepted")
                assert not additions and not backend.loaded(), "Mismatch reached ssh-add"
                imported.write_bytes(original)
                matching = backend.dispatch(dict(action="import", path=selected["importPath"],
                                            passphrase=phrase, expectedFingerprint=expected))
                assert matching["public"] == public and additions == [True]
            backend.dispatch(dict(action="remove", public=public))
            assert not backend.loaded()
            print("PASS selected-row stale/replaced identity rejected before ssh-add; matching identity and bounded input")

            # Real SIGTERM at the final response boundary, after add() returned.
            handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
            for sig in handlers:
                signal.signal(sig, ssh.cancelled)
            try:
                before = set(backend.loaded())
                original_add = backend.add
                original_status = backend.status
                armed = []

                def completed_add(*args, **kwargs):
                    result = original_add(*args, **kwargs)
                    armed.append(True)
                    return result

                def cancel_response():
                    if armed:
                        armed.clear()
                        os.kill(os.getpid(), signal.SIGTERM)
                    return original_status()

                for request in (dict(action="import", path=str(imported), passphrase=phrase),
                                dict(action="import", private=original.decode(), passphrase=phrase),
                                dict(action="generate", storage="temporary", unprotected=True)):
                    with mock.patch.object(backend, "add", completed_add), mock.patch.object(backend, "status", cancel_response):
                        rejected(lambda: backend.dispatch(request), "Post-add response cancellation reported success")
                    assert set(backend.loaded()) == before
                    assert not any(r.get("temporary") for r in backend.records.values())
                assert imported.read_bytes() == original
                # Cancellation cannot remove a duplicate/pre-existing identity.
                with imported.open("rb") as stream:
                    ssh.native(["ssh-add", "-q", "-k", "-"], stdin=stream, phrase=phrase)
                with mock.patch.object(backend, "add", completed_add), mock.patch.object(backend, "status", cancel_response):
                    rejected(lambda: backend.dispatch(dict(action="import", path=str(imported), passphrase=phrase)), "Duplicate cancellation reported success")
                assert set(backend.loaded()) == before | {public}
                with ssh.memory((public + "\n").encode()) as fd:
                    ssh.native(["ssh-add", "-q", "-d", "-"], stdin=fd)

                # Both O_EXCL calls must register before a real pending signal runs.
                real_open = os.open
                for member in (1, 2):
                    fresh = ssh.Backend(home, runtime, agent.pid)
                    target = home / f"registration-{member}"
                    creations = []

                    def interrupt_creation(*args, **kwargs):
                        fd = real_open(*args, **kwargs)
                        if args[1] & os.O_EXCL:
                            creations.append(fd)
                            if len(creations) == member:
                                os.kill(os.getpid(), signal.SIGTERM)
                        return fd

                    with mock.patch.object(ssh.os, "open", interrupt_creation):
                        rejected(lambda: fresh.publish(imported, str(target)), "Pre-registration cancellation ignored")
                    assert len(creations) == member
                    assert not target.exists() and not Path(str(target) + ".pub").exists()

                # A complete permanent pair is a committed save, even if the
                # later response inventory or publication return is cancelled.
                original_publish = backend.publish
                for boundary in ("status", "publish-return"):
                    target = home / ("completed-" + boundary)
                    fired = []

                    def cancel_once():
                        if not fired:
                            fired.append(True)
                            os.kill(os.getpid(), signal.SIGTERM)
                        return original_status()

                    def cancel_after_publish(*args):
                        result = original_publish(*args)
                        os.kill(os.getpid(), signal.SIGTERM)
                        return result

                    with mock.patch.object(backend, "status", cancel_once if boundary == "status" else original_status), mock.patch.object(backend, "publish", cancel_after_publish if boundary == "publish-return" else original_publish):
                        completed = backend.dispatch(dict(action="generate", storage="permanent", path=str(target), unprotected=True))
                    assert completed["saved"] == str(target) and completed["public"]
                    assert completed["error"] == "" and "saved" in completed["message"]
                    assert target.is_file() and Path(str(target) + ".pub").is_file()
                    assert completed["public"] not in backend.loaded()
                print("PASS post-add response cancellation rollback/duplicate exclusion; both O_EXCL registration signals; completed permanent-save result")
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)

            # Observe the actual subprocess boundary, without logging any private input.
            popen = ssh.subprocess.Popen
            seen_memfd = []

            def observe(args, **kwargs):
                transport = repr((args, kwargs.get("env", {})))
                assert phrase not in transport and original.decode() not in transport
                if args[:2] == ["ssh-keygen", "-y"]:
                    assert args[-1].startswith("/proc/self/fd/")
                    fd = int(args[-1].rsplit("/", 1)[1])
                    assert fd in kwargs["pass_fds"]
                    assert stat.S_IMODE(os.fstat(fd).st_mode) == 0o600
                    assert os.readlink(f"/proc/self/fd/{fd}").startswith("/memfd:")
                    seen_memfd.append(True)
                return popen(args, **kwargs)

            with mock.patch.object(ssh.subprocess, "Popen", observe):
                result = backend.dispatch({"action": "import", "path": str(imported), "passphrase": phrase})
            assert seen_memfd and result["public"] == public
            assert any(e["loaded"] and e["temporary"] and e["paths"] for e in result["entries"])
            assert imported.read_bytes() == original
            provenance = (runtime / "icewine-ssh/public.json").read_text()
            assert phrase not in provenance and "PRIVATE KEY" not in provenance
            assert public in provenance
            statefile = runtime / "icewine-ssh/public.json"
            sentinel = root / "keep"
            sentinel.write_text("unchanged")
            statefile.unlink()
            statefile.symlink_to(sentinel)
            assert not backend.dispatch({"action": "status"})["available"]
            rejected(lambda: backend.dispatch({"action": "remove", "public": public}), "Metadata symlink accepted")
            assert sentinel.read_text() == "unchanged"
            statefile.unlink()
            statefile.write_text(provenance)
            statefile.chmod(0o600)
            print("PASS native encrypted memfd import, actual argv/env boundary, public-only provenance, inventory")

            # Pasted input follows the real encrypted memfd/agent transaction too.
            backend.dispatch(dict(action="remove", public=public))
            files_before = {p.relative_to(home) for p in home.rglob("*")}
            with mock.patch.object(ssh.subprocess, "Popen", observe):
                pasted = backend.dispatch(dict(action="import", private=original.decode(), passphrase=phrase))
            assert pasted["public"] == public and public in backend.loaded()
            assert original.decode() not in json.dumps(pasted) and phrase not in json.dumps(pasted)
            metadata = (runtime / "icewine-ssh/public.json").read_text()
            assert "PRIVATE KEY" not in metadata and phrase not in metadata
            assert {p.relative_to(home) for p in home.rglob("*")} == files_before
            assert backend.records[public]["path"] == ""
            before_invalid = set(backend.loaded())
            for request in (dict(private=original.decode(), passphrase="wrong"),
                            dict(private="not a private key"), dict(private=""),
                            dict(private="x" * (ssh.LIMIT + 1)),
                            dict(private=original.decode(), path=str(imported))):
                rejected(lambda: backend.dispatch(dict(action="import", **request)), "Invalid pasted input accepted")
                assert set(backend.loaded()) == before_invalid
            backend.dispatch(dict(action="remove", public=public))
            # The encrypted fixture is reloaded for the existing ownership checks.
            backend.dispatch(dict(action="import", private=original.decode(), passphrase=phrase))
            print("PASS pasted encrypted import, no disk writes or secret output, invalid/ambiguous/oversize rejection")

            # A new helper instance represents reopening/reloading the shell.
            reloaded = ssh.Backend(home, runtime, agent.pid)
            result = reloaded.dispatch({"action": "status"})
            assert any(e["temporary"] and e["loaded"] for e in result["entries"])
            before = reloaded.loaded()
            with mock.patch.object(ssh, "native", wraps=ssh.native) as native:
                result = reloaded.dispatch({"action": "import", "path": str(imported), "passphrase": phrase})
                assert not any(c.args[0][0] == "ssh-add" for c in native.call_args_list)
            assert "Already loaded" in result["message"] and reloaded.loaded() == before
            rejected(lambda: reloaded.dispatch({"action": "import", "path": str(imported), "passphrase": "wrong"}), "Wrong phrase accepted")
            malformed = keys / "bad"
            malformed.write_text("not a private key")
            malformed.chmod(0o600)
            rejected(lambda: reloaded.dispatch({"action": "import", "path": str(malformed)}), "Malformed input accepted")
            assert reloaded.loaded() == before
            print("PASS reload ownership, duplicate unchanged, wrong phrase/malformed key rejected")

            generated = reloaded.dispatch({"action": "generate", "storage": "temporary", "passphrase": "", "confirmation": "", "unprotected": True})
            other = generated["public"]
            assert other != public and other in reloaded.loaded()
            reloaded.dispatch({"action": "remove", "public": public})
            assert reloaded.loaded() == [other] and imported.read_bytes() == original
            rejected(lambda: reloaded.dispatch({"action": "remove", "public": public}), "Unowned identity accepted")
            # An identity added externally is visible but must never acquire card ownership.
            with imported.open("rb") as stream:
                ssh.native(["ssh-add", "-q", "-k", "-"], stdin=stream, phrase=phrase)
            result = reloaded.dispatch({"action": "import", "path": str(imported), "passphrase": phrase})
            assert not any(e["temporary"] for e in result["entries"] if e["public"] == public)
            rejected(lambda: reloaded.dispatch({"action": "remove", "public": public}), "External identity removed")
            pubfile = Path(str(imported) + ".pub")
            public_bytes = pubfile.read_bytes()
            pubfile.unlink()
            without_sidecar = reloaded.dispatch({"action": "status"})
            assert any(e["loaded"] and str(imported) in e["paths"] for e in without_sidecar["entries"])
            pubfile.write_bytes(public_bytes)
            print("PASS temporary generation, exact unload preserves other key/files, pre-existing ownership refused")

            dest = home / "permanent"
            request = dict(action="generate", storage="permanent", path=str(dest),
                           passphrase=phrase, confirmation=phrase)
            saved = reloaded.dispatch(request)
            assert saved["saved"] == str(dest)
            assert stat.S_IMODE(dest.stat().st_mode) == 0o600
            assert saved["public"] not in reloaded.loaded()
            assert any(e["paths"] == [str(dest)] and not e["loaded"] and not e["temporary"]
                       for e in saved["entries"] if e["public"] == saved["public"])
            assert next(e for e in saved["entries"] if e["public"] == saved["public"])["importPath"] == str(dest)
            # Sidecar-only discovery stays visible, but cannot offer selected-file Load.
            dest.rename(home / "held-private")
            assert next(e for e in reloaded.dispatch({"action": "status"})["entries"]
                        if e["public"] == saved["public"])["importPath"] == ""
            (home / "held-private").rename(dest)
            dest.chmod(0o644)
            assert next(e for e in reloaded.dispatch({"action": "status"})["entries"]
                        if e["public"] == saved["public"])["importPath"] == ""
            dest.chmod(0o600)
            dest.rename(home / "held-private")
            dest.symlink_to(home / "held-private")
            assert next(e for e in reloaded.dispatch({"action": "status"})["entries"]
                        if e["public"] == saved["public"])["importPath"] == ""
            dest.unlink()
            (home / "held-private").rename(dest)
            saved_bytes = dest.read_bytes()
            before_cancel = set(reloaded.loaded())
            real_native = ssh.native

            def cancel_after_commit(args, **kwargs):
                answer = real_native(args, **kwargs)
                if args[:3] == ["ssh-add", "-q", "-k"]:
                    raise ssh.Unavailable("Cancelled")
                return answer

            with mock.patch.object(ssh, "native", cancel_after_commit):
                rejected(lambda: reloaded.dispatch(dict(action="import", path=str(dest), passphrase=phrase)), "Committed cancellation ignored")
            assert set(reloaded.loaded()) == before_cancel
            assert dest.read_bytes() == saved_bytes
            print("PASS native metadata without .pub and cancellation after agent mutation rolls back exactly")
            rejected(lambda: reloaded.dispatch(request), "Overwrote permanent identity")
            assert saved_bytes == dest.read_bytes()
            conflict = home / "public-conflict"
            Path(str(conflict) + ".pub").write_text("keep")
            rejected(lambda: reloaded.dispatch(dict(request, path=str(conflict))), "Overwrote public conflict")
            assert not conflict.exists() and Path(str(conflict) + ".pub").read_text() == "keep"
            link = home / "symlink"
            link.symlink_to(home / "absent")
            rejected(lambda: reloaded.dispatch(dict(request, path=str(link))), "Followed conflicting symlink")
            assert link.is_symlink() and not (home / "absent").exists()
            parent_link = home / "parent-link"
            parent_link.symlink_to(keys)
            rejected(lambda: reloaded.dispatch(dict(request, path=str(parent_link / "new"))), "Followed symlink parent")
            rejected(lambda: reloaded.dispatch(dict(request, confirmation="mismatch")), "Mismatch accepted")
            rejected(lambda: reloaded.dispatch(dict(request, passphrase="", confirmation="")), "Implicit no-phrase choice accepted")
            print("PASS encrypted permanent generation, no overwrite/symlink/partial pair, explicit passphrase choice")

            # Exercise actual publication rollback under a late failure.
            cancelled_path = home / "cancelled"
            real_fsync = os.fsync
            calls = []

            def fail_second(fd):
                calls.append(fd)
                if len(calls) == 2:
                    raise ssh.Unavailable("Cancelled")
                return real_fsync(fd)

            with mock.patch.object(ssh.os, "fsync", fail_second):
                rejected(lambda: reloaded.publish(imported, str(cancelled_path)), "Late failure accepted")
            assert not cancelled_path.exists() and not Path(str(cancelled_path) + ".pub").exists()
            before_dirs = set(Path("/dev/shm").glob("icewine-ssh-*"))
            with mock.patch.object(ssh, "native", side_effect=ssh.Unavailable("Cancelled")):
                rejected(lambda: reloaded.generate(dict(request, storage="temporary")), "Cancellation ignored")
            assert set(Path("/dev/shm").glob("icewine-ssh-*")) == before_dirs
            with mock.patch.object(ssh.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"ext4\n")):
                rejected(lambda: reloaded.generate(dict(request, storage="temporary")), "Disk-backed temp staging allowed")
            print("PASS late failure rollback, cancelled generation cleanup, non-tmpfs rejection")

            # Config discovery never executes Match exec and bounds Include cycles.
            marker = root / "must-not-exist"
            (keys / "config").write_text(f'Include "extra*"\nMatch exec "touch {marker}"\n IdentityFile "%d/.ssh/a=b"\n IdentityFile "%d/.ssh/%h"\n')
            (keys / "extra").write_text('Include config\nIdentityFile ~/.ssh/quoted\\ path\n')
            paths = ssh.identity_files(home)
            assert keys / "a=b" in paths and keys / "quoted path" in paths and not marker.exists()
            assert not any("%h" in str(p) for p in paths)
            with mock.patch.dict(os.environ, SSH_AUTH_SOCK=str(runtime / "forwarded")):
                rejected(lambda: reloaded.dispatch({"action": "remove", "public": other}), "External socket accepted")
            wrong_service = ssh.Backend(home, runtime, os.getpid())
            rejected(lambda: wrong_service.dispatch({"action": "remove", "public": other}), "Unrecognised service accepted")
            # The actual JSON entry point must use only its one native unit contract.
            real_run = subprocess.run

            def unit_query(args, **kwargs):
                if args[:4] == ["systemctl", "--user", "show", "ssh-agent.service"]:
                    value = str(agent.pid) if "MainPID" in args else "{ path=" + shutil.which("ssh-agent") + " ; }"
                    return subprocess.CompletedProcess(args, 0, value.encode())
                return real_run(args, **kwargs)

            handler = signal.getsignal(signal.SIGTERM)
            try:
                output = io.StringIO()
                with mock.patch.object(ssh.subprocess, "run", unit_query), mock.patch.object(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(b'{"action":"status"}'))), mock.patch.object(sys, "stdout", output):
                    ssh.main()
                assert json.loads(output.getvalue())["available"]
                output = io.StringIO()
                payload = json.dumps(dict(action="import", passphrase="secret\ninvalid")).encode()
                with mock.patch.object(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(payload))), mock.patch.object(sys, "stdout", output):
                    ssh.main()
                assert "secret" not in output.getvalue() and not json.loads(output.getvalue())["available"]
                # Also cover cancellation after dispatch finished, before the CLI
                # commits the response. The real entry point must undo the add.
                dispatch = ssh.Backend.dispatch
                before_reply = set(reloaded.loaded())

                def cancel_before_reply(instance, request):
                    answer = dispatch(instance, request)
                    os.kill(os.getpid(), signal.SIGTERM)
                    return answer

                output = io.StringIO()
                payload = json.dumps(dict(action="import", path=str(dest), passphrase=phrase)).encode()
                with mock.patch.object(ssh.Backend, "dispatch", cancel_before_reply), mock.patch.object(ssh.subprocess, "run", unit_query), mock.patch.object(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(payload))), mock.patch.object(sys, "stdout", output):
                    ssh.main()
                cancelled_reply = json.loads(output.getvalue())
                assert cancelled_reply["error"] == "Cancelled" and not cancelled_reply.get("message")
                assert set(reloaded.loaded()) == before_reply
                # The old final guard was OUTSIDE main's try. Send an actual
                # signal at that line event, after dispatch has returned, rather
                # than inside a dispatch wrapper. Cover both transaction kinds.
                lines = (source / "scripts/ssh").read_text().splitlines()
                transition = next(i + 2 for i, line in enumerate(lines)
                                  if "# Keep cancellation rollback live" in line)
                committed = keys / "main-committed"
                for request in (dict(action="import", path=str(dest), passphrase=phrase),
                                dict(action="generate", storage="permanent", path=str(committed),
                                     passphrase=phrase, confirmation=phrase)):
                    fired = []

                    def at_transition(frame, event, arg):
                        if frame.f_code is ssh.main.__code__ and event == "line" and frame.f_lineno == transition and not fired:
                            fired.append(True)
                            os.kill(os.getpid(), signal.SIGTERM)
                        return at_transition

                    output = io.StringIO()
                    payload = json.dumps(request).encode()
                    tracing = sys.gettrace()
                    try:
                        with mock.patch.object(ssh.subprocess, "run", unit_query), mock.patch.object(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(payload))), mock.patch.object(sys, "stdout", output):
                            sys.settrace(at_transition)
                            ssh.main()
                    finally:
                        sys.settrace(tracing)
                    assert fired, "Final response transition was not exercised"
                    reply = json.loads(output.getvalue())
                    if request["action"] == "import":
                        assert reply["error"] == "Cancelled" and not reply.get("message")
                    else:
                        assert reply["saved"] == str(committed) and reply["public"]
                        assert "saved" in reply["message"] and not reply["error"]
                        assert committed.is_file() and Path(str(committed) + ".pub").is_file()
                    assert set(reloaded.loaded()) == before_reply
                # An actual cancellation must kill the native child, not just clear UI state.
                children = []

                def child(args, **kwargs):
                    process = popen(args, **kwargs)
                    children.append(process)
                    return process

                timer = threading.Timer(0.1, lambda: os.kill(os.getpid(), signal.SIGTERM))
                signal.signal(signal.SIGTERM, ssh.cancelled)
                timer.start()
                try:
                    with mock.patch.object(ssh.subprocess, "Popen", child):
                        rejected(lambda: ssh.native([sys.executable, "-c", "import time; time.sleep(30)"]), "Cancellation ignored")
                finally:
                    timer.cancel()
                assert children and all(p.poll() is not None for p in children)
            finally:
                signal.signal(signal.SIGTERM, handler)
            print("PASS actual JSON/native-unit entry point, categorical secret-safe errors, child cancellation")
            subprocess.run(["ssh-add", "-x"], input=b"lock\nlock\n", env=dict(env, SSH_ASKPASS_REQUIRE="never"), capture_output=True, start_new_session=True, check=True)
            assert not reloaded.dispatch({"action": "status"})["available"]
            print("PASS bounded static config, forwarded/wrong-peer/locked-agent refusal")
            agent.terminate()
            agent.wait(timeout=3)
            disappeared = reloaded.dispatch({"action": "status"})
            assert not disappeared["available"]
            agent = subprocess.Popen(["ssh-agent", "-D", "-a", str(runtime / "ssh-agent")],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(100):
                if (runtime / "ssh-agent").exists():
                    break
                time.sleep(0.01)
            fresh = ssh.Backend(home, runtime, agent.pid)
            refreshed = fresh.dispatch({"action": "status"})
            assert refreshed["available"] and fresh.loaded() == []
            assert not any(e["temporary"] for e in refreshed["entries"])
            assert dest.read_bytes() == saved_bytes
            print("PASS agent disappearance/replacement clears volatile ownership, preserves permanent files")
        finally:
            agent.terminate()
            agent.wait(timeout=3)

print("SSH developer checks passed; all identities, agents and files were synthetic")
