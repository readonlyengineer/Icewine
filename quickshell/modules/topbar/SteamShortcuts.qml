import QtQuick
import Quickshell
import Quickshell.Io
import "SteamShortcuts.js" as Steam

Scope {
    id: root

    property var commands: []
    property bool busy: false
    property var pending: []
    property var collected: []

    function refresh() {
        if (busy)
            return
        busy = true
        collected = []
        discover.running = true
    }

    function fail(message) {
        console.warn("Steam shortcut discovery:", message)
        commands = []
        pending = []
        collected = []
        busy = false
    }

    function next() {
        if (!pending.length) {
            commands = collected
            busy = false
            return
        }
        const path = pending[0]
        pending = pending.slice(1)
        if (shortcutFile.path === path)
            shortcutFile.reload()
        else
            shortcutFile.path = path
    }

    Process {
        id: discover
        // Native Steam profiles only; duplicate aliases are harmless.
        command: ["sh", "-c", `
            for root in "\${XDG_DATA_HOME:-$HOME/.local/share}/Steam" "$HOME/.steam/steam"; do
                for file in "$root"/userdata/*/config/shortcuts.vdf; do
                    [ -f "$file" ] && printf '%s\\n' "$file"
                done
            done
            exit 0
        `]
        stdout: StdioCollector {}
        onExited: function(code) {
            if (code !== 0) {
                root.fail("Could not enumerate Steam profiles")
                return
            }
            root.pending = stdout.text.split("\n").filter(path => path !== "")
            root.next()
        }
    }

    FileView {
        id: shortcutFile
        printErrors: false
        onLoaded: {
            try {
                root.collected = root.collected.concat(Steam.commands(data()))
                Qt.callLater(root.next)
            } catch (error) {
                root.fail(String(error))
            }
        }
        onLoadFailed: error => root.fail("Could not read " + path + ": " + error)
    }
}
