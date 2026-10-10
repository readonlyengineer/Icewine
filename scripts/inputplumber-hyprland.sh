# Shared userspace bootstrap; restoration is ExecStopPost, including failed starts.
set -eu
inputplumber devices manage-all --enable
device=
for _ in $(seq 1 40); do
  if device=$(icewine-inputplumber-intercept device); then break; fi
  sleep 0.25
done
[ -n "$device" ] || { echo 'No InputPlumber composite device appeared after manage-all' >&2; exit 1; }
inputplumber device "$device" targets set xbox-elite keyboard mouse touchpad
inputplumber device "$device" profile load "${ICEWINE_INPUTPLUMBER_PROFILE_DIR:-/etc/inputplumber/profiles}/icewine-hyprland.yaml"
# Fail closed until Quickshell observes Gamescope taking focus.
icewine-inputplumber-intercept overlay
