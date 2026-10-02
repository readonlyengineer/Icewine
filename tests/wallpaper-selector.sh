#!/usr/bin/env bash
set -euo pipefail

cli=${1:?pass the icewine CLI executable}
test_home=$(mktemp -d)
trap 'rm -rf -- "$test_home"' EXIT
mkdir -p "$test_home/runtime"

printf '%s' 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVQI12P4//8/AAX+Av7czFnnAAAAAElFTkSuQmCC' \
    | base64 --decode > "$test_home/source image.png"

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

XDG_DATA_HOME="$test_home/migrated" "$cli" wallpaper --migrate \
    "$test_home/source image.png" "$test_home/migrated"
cmp "$test_home/source image.png" \
    "$test_home/migrated/icewine/wallpapers/selection.img"

printf 'keep me\n' > "$test_home/existing-selection"
mkdir -p "$test_home/existing/icewine/wallpapers"
cp "$test_home/existing-selection" "$test_home/existing/icewine/wallpapers/selection.img"
XDG_DATA_HOME="$test_home/existing" "$cli" wallpaper --migrate \
    "$test_home/source image.png" "$test_home/existing"
cmp "$test_home/existing-selection" "$test_home/existing/icewine/wallpapers/selection.img"
