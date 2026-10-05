import Quickshell
import Quickshell.Io

Scope {
    id: root
    property var commands: []

    function refresh() {
        if (!reader.running)
            reader.running = true
    }

    Process {
        id: reader
        command: ["icewine-steam-shortcuts"]
        stdout: StdioCollector {}
        onExited: function(code) {
            try {
                if (code !== 0)
                    throw new Error("Shortcut reader exited with " + code)
                root.commands = JSON.parse(stdout.text)
            } catch (error) {
                console.warn("Steam shortcut discovery:", error)
                root.commands = []
            }
        }
    }
}
