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
  slurp) test "${FAIL:-}" != slurp; echo '0,0 100x100' ;;
  grim) printf 'new image' > "$3"; test "${FAIL:-}" != grim ;;
  mv) test "${FAIL:-}" != mv; exec "$REAL_MV" "$@" ;;
  wl-copy) test "${FAIL:-}" != wl-copy; cat > "$TEST_EVENTS.clipboard" ;;
  notify-send) printf '%s\n' "$*" > "$TEST_EVENTS" ;;
esac
MOCK
chmod +x "$work/bin/mock"
for command in xdg-user-dir slurp grim mv wl-copy notify-send; do
  ln -s mock "$work/bin/$command"
done
export PATH="$work/bin:$PATH"
# Fresh home, XDG Pictures path containing spaces.
bash "$script"
test "$(cat "$TEST_PICTURES/screenshot.png")" = 'new image'
test "$(cat "$TEST_EVENTS.clipboard")" = 'new image'
test -s "$TEST_EVENTS"
# Cancellation, partial capture and failed save must preserve the old image.
for failure in slurp grim mv; do
  printf 'previous image' > "$TEST_PICTURES/screenshot.png"
  rm -f "$TEST_EVENTS" "$TEST_EVENTS.clipboard"
  if FAIL="$failure" bash "$script"; then exit 1; fi
  test "$(cat "$TEST_PICTURES/screenshot.png")" = 'previous image'
  test ! -e "$TEST_EVENTS"
  test ! -e "$TEST_EVENTS.clipboard"
  test "$(ls -A "$TEST_PICTURES")" = screenshot.png
done
# Clipboard failure retains the successfully saved image, without false success.
if FAIL=wl-copy bash "$script"; then exit 1; fi
test "$(cat "$TEST_PICTURES/screenshot.png")" = 'new image'
test ! -e "$TEST_EVENTS"
test "$(ls -A "$TEST_PICTURES")" = screenshot.png
