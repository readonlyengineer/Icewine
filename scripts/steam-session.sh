# shellcheck shell=bash
ICEWINE_SPLASH_MODE=steam qs -p "$HOME/.config/quickshell/startup/shell.qml" &
exec icewine-steam "$@"
