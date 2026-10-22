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
dp_edid=$(od -An -v -tx1 "$root/drm/card1-DP-1/edid" | tr -d ' \n')
hdmi_edid=$(od -An -v -tx1 "$root/drm/card1-HDMI-A-1/edid" | tr -d ' \n')
expected=$(printf 'DP-1\ttrue\ttrue\t%s\nHDMI-A-1\tfalse\tfalse\t%s' "$dp_edid" "$hdmi_edid")
[[ "$actual" == "$expected" ]]

# /proc is a readable pseudo-file with stat size zero, like a sysfs EDID.
mkdir -p "$root/drm/card2-ZERO-1" "$root/drm/card2-DP-1"
printf connected > "$root/drm/card2-ZERO-1/status"
printf connected > "$root/drm/card2-DP-1/status"
ln -s /proc/version "$root/drm/card2-ZERO-1/edid"
[[ -r "$root/drm/card2-ZERO-1/edid" && ! -s "$root/drm/card2-ZERO-1/edid" ]]
actual=$(PATH="$root/bin:$PATH" bash "$1" "$root/drm")
zero_edid=$(od -An -v -tx1 /proc/version | tr -d ' \n')
expected=$(printf '%s\nDP-1\tfalse\tfalse\t\nZERO-1\tfalse\tfalse\t%s' "$expected" "$zero_edid")
[[ "$actual" == "$expected" ]]
# Keep even an unreadable duplicate connector row so the consumer cannot pick one GPU.
printf 'monitor capability probe and zero-size/duplicate connector checks ok\n'
