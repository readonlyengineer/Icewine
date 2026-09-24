#!/usr/bin/env bash
set -euo pipefail

session_script=$1
reaper=$2
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/bin" "$work/home/.config/quickshell/startup"
touch "$work/home/.config/quickshell/startup/shell.qml"
bash_path=$(command -v bash)

printf '#!%s\n' "$bash_path" > "$work/bin/qs"
cat >> "$work/bin/qs" <<'EOF'
printf '%s\n' "$@" > "$TEST_STATE/splash-arguments"
printf '%s\n' "${ICEWINE_SPLASH_MODE:-}" > "$TEST_STATE/splash-mode"
if [[ ${TEST_SPLASH_WAIT:-} ]]; then
    trap ': > "$TEST_STATE/splash-stopped"; exit 0' TERM HUP INT
    : > "$TEST_STATE/splash-started"
    while true; do sleep 1; done
fi
: > "$TEST_STATE/splash-exited"
exit 7
EOF
printf '#!%s\n' "$bash_path" > "$work/bin/icewine-steam"
cat >> "$work/bin/icewine-steam" <<'EOF'
printf '%s\n' "$@" > "$TEST_STATE/steam-arguments"
if [[ ${TEST_STEAM_DAEMON:-} ]]; then
    (
        trap ': > "$TEST_STATE/daemon-stopped"; exit 0' TERM HUP INT
        : > "$TEST_STATE/daemon-started"
        while true; do sleep 1; done
    ) &
    exit 0
fi
if [[ ${TEST_STEAM_WAIT:-} ]]; then
    trap ': > "$TEST_STATE/steam-stopped"; exit 0' TERM HUP INT
    : > "$TEST_STATE/steam-started"
    while true; do sleep 1; done
fi
exit "${TEST_STEAM_STATUS:-9}"
EOF
chmod +x "$work/bin/qs" "$work/bin/icewine-steam"

if env HOME="$work/home" PATH="$work/bin:$PATH" TEST_STATE="$work" \
    bash "$session_script" 'a b' literal; then
    echo "Steam failure unexpectedly succeeded" >&2
    exit 1
else
    status=$?
fi

test "$status" -eq 9
cmp -s <(printf '%s\n' -p "$work/home/.config/quickshell/startup/shell.qml") "$work/splash-arguments"
test "$(cat "$work/splash-mode")" = steam
cmp -s <(printf 'a b\nliteral\n') "$work/steam-arguments"

wait_for() {
    for _ in {1..40}; do
        test -e "$1" && return
        sleep 0.05
    done
    echo "Timed out waiting for $1" >&2
    return 1
}

wait_for "$work/splash-exited"

rm -f "$work"/splash-{started,stopped}
env HOME="$work/home" PATH="$work/bin:$PATH" TEST_STATE="$work" \
    TEST_SPLASH_WAIT=1 TEST_STEAM_STATUS=9 \
    "$reaper" -- bash "$session_script"
wait_for "$work/splash-stopped"

rm -f "$work"/{splash,daemon}-{started,stopped}
env HOME="$work/home" PATH="$work/bin:$PATH" TEST_STATE="$work" \
    TEST_SPLASH_WAIT=1 TEST_STEAM_DAEMON=1 \
    "$reaper" -- bash "$session_script"
wait_for "$work/splash-stopped"
wait_for "$work/daemon-stopped"

rm -f "$work"/{splash,steam}-{started,stopped}
env HOME="$work/home" PATH="$work/bin:$PATH" TEST_STATE="$work" \
    TEST_SPLASH_WAIT=1 TEST_STEAM_WAIT=1 \
    "$reaper" -- bash "$session_script" &
reaper_pid=$!
wait_for "$work/splash-started"
wait_for "$work/steam-started"
kill -TERM "$reaper_pid"
wait "$reaper_pid"
wait_for "$work/splash-stopped"
wait_for "$work/steam-stopped"

echo "Steam session: arguments/status, reaper failure, daemon and cancellation checks pass"
