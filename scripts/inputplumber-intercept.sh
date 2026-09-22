# Used only inside the Hyprland session. Never select an unrelated controller.
# shellcheck shell=bash
export LC_ALL=C
case "${1:-}" in
  device|events|desktop|game|overlay) action="$1" ;;
  *) echo 'usage: icewine-inputplumber-intercept {device|events|desktop|game|overlay}' >&2; exit 2 ;;
esac

service=org.shadowblip.InputPlumber
interface=org.shadowblip.Input.CompositeDevice
paths=$(busctl --system --timeout=2 --list tree "$service")
device=
while IFS= read -r path; do
  [[ "$path" =~ ^/org/shadowblip/InputPlumber/CompositeDevice[0-9]+$ ]] || continue
  name=$(busctl --system --timeout=2 get-property "$service" "$path" "$interface" Name) || continue
  [ "$name" = 's "Steam Deck"' ] || continue
  if [ -n "$device" ]; then
    echo 'More than one Steam Deck composite device; refusing ambiguous routing' >&2
    exit 1
  fi
  device="$path"
done <<< "$paths"

if [ -z "$device" ]; then
  echo 'No Steam Deck composite device found' >&2
  exit 1
fi

if [ "$action" = events ]; then
  profile=$(busctl --system --timeout=2 get-property "$service" "$device" "$interface" ProfileName)
  case "$profile" in
    's "Icewine Hyprland"'|'s "Icewine Desktop"') ;;
    *) echo 'Deck profile changed; restart icewine-inputplumber-hyprland.service' >&2; exit 1 ;;
  esac
fi

set_mode() {
  local mode="$1" actual
  actual=$(busctl --system --timeout=2 get-property "$service" "$device" "$interface" InterceptMode)
  if [ "$actual" != "u $mode" ]; then
    busctl --system --timeout=2 set-property "$service" "$device" "$interface" InterceptMode u "$mode"
    actual=$(busctl --system --timeout=2 get-property "$service" "$device" "$interface" InterceptMode)
  fi
  [ "$actual" = "u $mode" ] || { echo "Intercept mode did not settle: $actual" >&2; exit 1; }
}

load_profile() {
  local name="$1" path="$2" current id
  current=$(busctl --system --timeout=2 get-property "$service" "$device" "$interface" ProfileName)
  [ "$current" = "s \"$name\"" ] && return
  id="${device##*CompositeDevice}"
  inputplumber device "$id" profile load "$path"
  current=$(busctl --system --timeout=2 get-property "$service" "$device" "$interface" ProfileName)
  [ "$current" = "s \"$name\"" ] || { echo "Profile did not settle: $current" >&2; exit 1; }
}

case "$action" in
  device) printf '%s\n' "${device##*CompositeDevice}" ;;
  events)
    targets=$(busctl --system --timeout=2 --json=short get-property "$service" "$device" "$interface" DbusDevices)
    target=$(jq -er '[.data | .. | strings | select(test("^/org/shadowblip/InputPlumber/devices/target/dbus[0-9]+$"))] | if length == 1 then .[0] else error("Expected one Deck D-Bus target") end' <<< "$targets")
    printf 'NIXDECK_TARGET %s\n' "$target"
    # Ordinary signal subscription; unlike busctl monitor this needs no root.
    # Listen to lifecycle signals too, so Quickshell can reconnect on removal.
    exec stdbuf -oL gdbus monitor --system --dest "$service"
    ;;
  desktop)
    set_mode 3
    load_profile 'Icewine Desktop' /etc/inputplumber/profiles/icewine-desktop.yaml
    ;;
  overlay)
    set_mode 3
    load_profile 'Icewine Hyprland' /etc/inputplumber/profiles/icewine-hyprland.yaml
    ;;
  game)
    # Profile changes happen while raw gamepad output is still intercepted.
    set_mode 3
    load_profile 'Icewine Hyprland' /etc/inputplumber/profiles/icewine-hyprland.yaml
    set_mode 0
    ;;
esac
