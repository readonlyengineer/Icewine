set -euo pipefail
script=$1
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
export TEST_PICTURES="$work/Pictures with spaces"
export TEST_EVENTS="$work/events"
export REAL_MV
REAL_MV=$(command -v mv)
mkdir "$work/bin"
printf '#!%s\n' "$(command -v bash)" > "$work/bin/mock"
cat >> "$work/bin/mock" <<'MOCK'
set -euo pipefail
case "${0##*/}" in
  xdg-user-dir) printf '%s\n' "$TEST_PICTURES" ;;
  grim|grimblast)
    printf '%s\n' "${0##*/} $*" >> "$TEST_EVENTS.order"
    printf 'new image' > "${!#}"
    test "${FAIL:-}" != "${0##*/}"
    ;;
  sleep) printf 'sleep %s\n' "$*" >> "$TEST_EVENTS.order" ;;
  mv) test "${FAIL:-}" != mv; exec "$REAL_MV" "$@" ;;
  wl-copy) test "${FAIL:-}" != wl-copy; cat > "$TEST_EVENTS.clipboard" ;;
  notify-send) printf '%s\n' "$*" > "$TEST_EVENTS" ;;
esac
MOCK
chmod +x "$work/bin/mock"
for command in xdg-user-dir grim grimblast mv wl-copy notify-send sleep; do
  ln -s mock "$work/bin/$command"
done
export PATH="$work/bin:$PATH"
# Each capture mode reaches the same atomic save, clipboard and notification path.
for args in 'monitor DP-1' 'region' 'window stable-id'; do
  rm -f "$TEST_EVENTS" "$TEST_EVENTS.clipboard"
  read -r -a invocation <<< "$args"
  bash "$script" "${invocation[@]}"
done
test "$(cat "$TEST_PICTURES/screenshot.png")" = 'new image'
test "$(cat "$TEST_EVENTS.clipboard")" = 'new image'
test -s "$TEST_EVENTS"
# Cancellation, partial capture and failed save must preserve the old image.
for failure in grimblast grim mv; do
  printf 'previous image' > "$TEST_PICTURES/screenshot.png"
  rm -f "$TEST_EVENTS" "$TEST_EVENTS.clipboard"
  mode=region
  if [[ "$failure" == grim ]]; then mode=monitor; fi
  if FAIL="$failure" bash "$script" "$mode" DP-1; then exit 1; fi
  test "$(cat "$TEST_PICTURES/screenshot.png")" = 'previous image'
  test ! -e "$TEST_EVENTS"
  test ! -e "$TEST_EVENTS.clipboard"
  test "$(ls -A "$TEST_PICTURES")" = screenshot.png
done
# Clipboard failure retains the successfully saved image, without false success.
if FAIL=wl-copy bash "$script" region; then exit 1; fi
test "$(cat "$TEST_PICTURES/screenshot.png")" = 'new image'
test ! -e "$TEST_EVENTS"
test "$(ls -A "$TEST_PICTURES")" = screenshot.png

# Clipboard-only capture must not touch Pictures.
export TEST_PICTURES="$work/unused Pictures"
bash "$script" region "" 0 1 0
test ! -e "$TEST_PICTURES"
test "$(cat "$TEST_EVENTS.clipboard")" = 'new image'

# Pictures-only capture must not change the clipboard.
printf 'old clipboard' > "$TEST_EVENTS.clipboard"
bash "$script" region "" 0 0 1
test "$(cat "$TEST_PICTURES/screenshot.png")" = 'new image'
test "$(cat "$TEST_EVENTS.clipboard")" = 'old clipboard'

# Delay precedes capture and preserves the requested mode and target.
for args in 'monitor DP-1' 'region' 'window stable-id'; do
  read -r -a invocation <<< "$args"
  : > "$TEST_EVENTS.order"
  bash "$script" "${invocation[0]}" "${invocation[1]:-}" 3 1 1
  test "$(head -n 1 "$TEST_EVENTS.order")" = 'sleep 3'
  case "${invocation[0]}" in
    monitor) expected='grim -o DP-1 ' ;;
    region) expected='grimblast --freeze save area ' ;;
    window) expected='grim -T stable-id ' ;;
  esac
  [[ "$(sed -n '2p' "$TEST_EVENTS.order")" == "$expected"* ]]
done

# Invalid options and disabled destinations must not capture anything.
for options in '0 0 0' '2 1 1' '0 yes 1'; do
  read -r -a flags <<< "$options"
  : > "$TEST_EVENTS.order"
  if bash "$script" region "" "${flags[@]}"; then exit 1; fi
  test ! -s "$TEST_EVENTS.order"
done
