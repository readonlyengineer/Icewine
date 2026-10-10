return {
    editor = "icewine-editor",
    terminal = "xdg-terminal-exec",
    browser = 'gtk-launch "$(xdg-settings get default-web-browser)"',
    file_manager = 'xdg-open "$HOME"',
    lock = "qs ipc call session lock",
}
