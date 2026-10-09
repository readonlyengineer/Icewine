return {
    editor = "icewine-editor",
    terminal = "icewine-terminal",
    browser = 'gtk-launch "$(xdg-settings get default-web-browser)"',
    file_manager = "icewine-file-manager",
    lock = "qs ipc call session lock",
}
