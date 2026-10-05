#!/usr/bin/env bash
set -euo pipefail

root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT

mkdir -p "$root/drm/card1-DP-1" "$root/drm/card1-HDMI-A-1" "$root/bin"
printf connected > "$root/drm/card1-DP-1/status"
printf connected > "$root/drm/card1-HDMI-A-1/status"
printf '%s\n' \
    'SMPTE ST2084' \
    'Vendor-Specific Data Block (AMD)' \
    'Minimum Refresh Rate: 48 Hz' > "$root/drm/card1-DP-1/edid"
printf 'Traditional gamma - SDR luminance range\n' > "$root/drm/card1-HDMI-A-1/edid"

printf '#!%s\ncat "$1"\n' "$BASH" > "$root/bin/edid-decode"
chmod +x "$root/bin/edid-decode"

actual=$(PATH="$root/bin:$PATH" bash "$1" "$root/drm")
expected=$'DP-1\ttrue\ttrue\nHDMI-A-1\tfalse\tfalse'
[[ "$actual" == "$expected" ]]

printf 'monitor capability probe ok\n'
