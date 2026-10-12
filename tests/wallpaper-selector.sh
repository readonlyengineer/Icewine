#!/usr/bin/env bash
set -euo pipefail

cli=${1:?pass the icewine CLI executable}
test_home=$(mktemp -d)
trap 'rm -rf -- "$test_home"' EXIT
mkdir -p "$test_home/runtime" "$test_home/public"
chmod 700 "$test_home/runtime"

printf '%s' 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVQI12P4//8/AAX+Av7czFnnAAAAAElFTkSuQmCC' \
    | base64 --decode > "$test_home/source image.png"

export XDG_CONFIG_HOME="$test_home/config"
export XDG_STATE_HOME="$test_home/state"
export XDG_CACHE_HOME="$test_home/cache"
export ICEWINE_SDDM_WALLPAPER_FILE="$test_home/public/wallpaper.img"
export XDG_DATA_HOME="$test_home/data"
export ICEWINE_WALLPAPER_DATA_HOME="$XDG_DATA_HOME"
export XDG_RUNTIME_DIR="$test_home/runtime"
"$cli" wallpaper "$test_home/source image.png"
selection="$XDG_DATA_HOME/icewine/wallpapers/selection.img"
cmp "$test_home/source image.png" "$selection"

cp -- "$selection" "$test_home/previous-selection"
printf 'not an image\n' > "$test_home/broken.png"
if "$cli" wallpaper "$test_home/broken.png"; then
    echo "unsupported input unexpectedly succeeded" >&2
    exit 1
fi
cmp "$test_home/previous-selection" "$selection"

if "$cli" wallpaper --migrate "$test_home/source image.png" "$test_home/old-data"; then
    echo "obsolete migration command unexpectedly succeeded" >&2
    exit 1
fi
[[ ! -e $test_home/old-data ]]
cmp "$test_home/previous-selection" "$selection"

# Replacing a selection copies bytes; later edits to the source do not change it.
"$cli" wallpaper "$test_home/source image.png"
printf 'source changed\n' > "$test_home/source image.png"
cmp "$test_home/previous-selection" "$selection"

# One authentication override; desktop changes preserve it, reset inherits again.
public="$ICEWINE_SDDM_WALLPAPER_FILE"
"$cli" wallpaper --publish-auth
cmp "$selection" "$public"
[[ $(stat -c %a "$public") == 644 ]]
cp "$test_home/previous-selection" "$test_home/auth image.png"
printf 'auth' >> "$test_home/auth image.png"
"$cli" wallpaper --auth "$test_home/auth image.png"
override="$XDG_DATA_HOME/icewine/wallpapers/auth.img"
cmp "$test_home/auth image.png" "$override"
cmp "$override" "$public"
[[ $(stat -c %a "$override") == 600 ]]
cp "$test_home/previous-selection" "$test_home/desktop image.png"
printf 'desktop' >> "$test_home/desktop image.png"
"$cli" wallpaper "$test_home/desktop image.png"
cmp "$test_home/desktop image.png" "$selection"
cmp "$override" "$public"
"$cli" wallpaper --auth-reset
[[ ! -e $override ]]
cmp "$selection" "$public"

# Failed publication and invalid override retain both previous valid images.
cp "$selection" "$test_home/previous-desktop"
cp "$public" "$test_home/previous-public"
printf 'not a directory' > "$test_home/unusable"
if ICEWINE_SDDM_WALLPAPER_FILE="$test_home/unusable/wallpaper.img" \
    "$cli" wallpaper --auth "$test_home/auth image.png"; then
    echo 'failed publication unexpectedly succeeded' >&2
    exit 1
fi
[[ ! -e $override ]]
cmp "$test_home/previous-desktop" "$selection"
cmp "$test_home/previous-public" "$public"
if "$cli" wallpaper --auth "$test_home/broken.png"; then
    echo 'invalid override unexpectedly succeeded' >&2
    exit 1
fi
[[ ! -e $override ]]
cmp "$test_home/previous-desktop" "$selection"
cmp "$test_home/previous-public" "$public"

# Exercise the real transaction's recovery if private commit fails after publication.
python3 - "${2:-scripts/wallpaper}" "$test_home/previous-selection" "$selection" "$public" <<'PY'
import importlib.machinery
import contextlib
import io
import subprocess
from pathlib import Path
import os
import sys
import types
from unittest.mock import patch

script, source, selection, public = map(Path, sys.argv[1:])
os.environ["ICEWINE_WALLPAPER_VALIDATOR"] = str(script.resolve().parent.parent / "quickshell/modules/WallpaperValidator.qml")
selector = types.ModuleType("wallpaper_selector")
importlib.machinery.SourceFileLoader(selector.__name__, str(script)).exec_module(selector)
old_selection, old_public = selection.read_bytes(), public.read_bytes()
replace = os.replace

def fail_private(source, destination):
    if Path(destination) == selection:
        raise PermissionError("test private commit failure")
    return replace(source, destination)

with patch.object(selector.os, "replace", side_effect=fail_private):
    try:
        selector.select([str(source)])
    except PermissionError:
        pass
    else:
        raise AssertionError("private commit failure ignored")
assert selection.read_bytes() == old_selection
assert public.read_bytes() == old_public
assert not list(selection.parent.glob(".wallpaper-*"))
assert not list(public.parent.glob(".wallpaper-*"))

# Refresh delivery fails after commit: saved bytes remain successful and pending.
run = selector.subprocess.run
for error in (subprocess.TimeoutExpired("qs ipc", 10), FileNotFoundError("qs unavailable")):
    calls = []
    def fail_refresh(command, **kwargs):
        if command[1] != "ipc":
            return run(command, **kwargs)
        calls.append(command)
        raise error
    warning = io.StringIO()
    with patch.object(selector.subprocess, "run", side_effect=fail_refresh), contextlib.redirect_stderr(warning):
        selector.select([str(source)])
    assert selection.read_bytes() == source.read_bytes()
    assert public.read_bytes() == source.read_bytes()
    assert len(calls) == 2 and "saved" in warning.getvalue() and "next launch" in warning.getvalue()
PY

echo 'PASS: desktop/auth inheritance, reset, private/public modes, validation and transactional failure recovery'
