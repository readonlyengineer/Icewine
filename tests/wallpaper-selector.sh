#!/usr/bin/env bash
set -euo pipefail
cli=${1:?pass the icewine CLI executable}
test_home=$(mktemp -d)
trap 'rm -rf -- "$test_home"' EXIT
mkdir -p "$test_home/runtime"
chmod 700 "$test_home/runtime"
printf '%s' 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVQI12P4//8/AAX+Av7czFnnAAAAAElFTkSuQmCC' \
    | base64 --decode > "$test_home/source image.png"
export XDG_CONFIG_HOME="$test_home/config" XDG_STATE_HOME="$test_home/state"
export XDG_CACHE_HOME="$test_home/cache" XDG_DATA_HOME="$test_home/data"
export ICEWINE_WALLPAPER_DATA_HOME="$XDG_DATA_HOME" XDG_RUNTIME_DIR="$test_home/runtime"
"$cli" wallpaper "$test_home/source image.png"
selection="$XDG_DATA_HOME/icewine/wallpapers/selection.img"
cmp "$test_home/source image.png" "$selection"
[[ $(stat -c %a "$selection") == 600 ]]
cp "$selection" "$test_home/previous-selection"
printf 'not an image\n' > "$test_home/broken.png"
if "$cli" wallpaper "$test_home/broken.png"; then exit 1; fi
cmp "$test_home/previous-selection" "$selection"
# Retired auth commands must fail without changing existing user files.
printf 'preserve historical override' > "$XDG_DATA_HOME/icewine/wallpapers/auth.img"
for option in --auth --auth-reset --publish-auth --migrate; do
    if "$cli" wallpaper "$option"; then exit 1; fi
done
[[ $(cat "$XDG_DATA_HOME/icewine/wallpapers/auth.img") == 'preserve historical override' ]]
"$cli" wallpaper "$test_home/source image.png"
printf 'source changed\n' > "$test_home/source image.png"
cmp "$test_home/previous-selection" "$selection"
python3 - "${2:-scripts/wallpaper}" "$test_home/previous-selection" "$selection" <<'PY'
import importlib.machinery
import contextlib
import io
import subprocess
from pathlib import Path
import os
import sys
import types
from unittest.mock import patch
script, source, selection = map(Path, sys.argv[1:])
os.environ['ICEWINE_WALLPAPER_VALIDATOR'] = str(script.resolve().parent.parent / 'quickshell/modules/WallpaperValidator.qml')
selector = types.ModuleType('wallpaper_selector')
importlib.machinery.SourceFileLoader(selector.__name__, str(script)).exec_module(selector)
previous = selection.read_bytes()
with patch.object(selector.os, 'replace', side_effect=PermissionError('test commit failure')):
    try: selector.select([str(source)])
    except PermissionError: pass
    else: raise AssertionError('commit failure ignored')
assert selection.read_bytes() == previous
assert not list(selection.parent.glob('.wallpaper-*'))
run = selector.subprocess.run
for error in (subprocess.TimeoutExpired('qs ipc', 10), FileNotFoundError('qs unavailable')):
    calls = []
    def fail_refresh(command, **kwargs):
        if command[1] != 'ipc': return run(command, **kwargs)
        calls.append(command)
        raise error
    warning = io.StringIO()
    with patch.object(selector.subprocess, 'run', side_effect=fail_refresh), contextlib.redirect_stderr(warning):
        selector.select([str(source)])
    assert selection.read_bytes() == source.read_bytes()
    assert len(calls) == 1 and 'saved' in warning.getvalue() and 'next launch' in warning.getvalue()
PY
echo 'PASS: desktop selection, private mode, validation, atomic failure recovery and retired auth commands'
