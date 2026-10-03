import QtQuick
import Quickshell
import Quickshell.Io
import qs.theme as Theme

QtObject {
    id: root

    property string requested: ""
    property string activeRequest: ""
    property string result: Theme.Palette.refresh
        ? "applied: " + Theme.Palette.snapshot.themeId
        : "pending: user-owned Palette.qml does not support live reload"
    readonly property string policy: Quickshell.env("ICEWINE_THEME_POLICY")
    readonly property var installed: Quickshell.env("ICEWINE_THEME_IDS").split(":")

    property FileView selectionFile: FileView {
        path: (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state")
              + "/icewine/theme"
        blockWrites: true
        onSaved: {
            if (root.policy) {
                root.result = "saved: " + root.requested + "; Nix policy keeps " + root.policy
            } else if (!renderer.running) {
                root.start()
            }
        }
        onSaveFailed: {
            root.requested = root.activeRequest
            root.result = "failed: selection could not be saved"
        }
    }

    property Process renderer: Process {
        id: renderer
        command: ["icewine-theme", "apply"]
        environment: ({ ICEWINE_THEME_FROM_SHELL: "1" })
        onExited: (code, status) => {
            if (!Theme.Palette.refresh || !Theme.Palette.refresh()) {
                root.result = "failed: theme saved, but shell palette could not be applied"
            } else if (!root.policy && Theme.Palette.snapshot.themeId !== root.activeRequest
                       && root.requested === root.activeRequest) {
                root.result = "failed: theme saved, but shell palette kept its previous colours"
            } else if (code !== 0) {
                root.result = "partial: shell palette applied; some consumer notifications failed"
            } else {
                root.result = "applied: " + Theme.Palette.snapshot.themeId
            }
            if (!root.policy && root.requested !== root.activeRequest)
                Qt.callLater(root.start)
        }
    }

    function start(): void {
        activeRequest = requested
        result = "pending: applying " + requested
        renderer.running = true
    }

    property IpcHandler ipc: IpcHandler {
        target: "theme"

        function select(theme: string): string {
            if (!/^[a-z0-9][a-z0-9-]*$/.test(theme) || root.installed.indexOf(theme) < 0)
                return "failed: theme is not installed: " + theme
            root.requested = theme
            if (root.selectionFile.text().trim() === theme) {
                if (root.policy)
                    root.result = "saved: " + theme + "; Nix policy keeps " + root.policy
                else if (!renderer.running)
                    root.start()
                return root.result
            }
            root.result = "pending: saving " + theme
            root.selectionFile.setText(theme + "\n")
            return root.result
        }

        function refresh(): string {
            if (!Theme.Palette.refresh || !Theme.Palette.refresh())
                return "failed: published palette could not be loaded"
            root.result = "applied: " + Theme.Palette.snapshot.themeId
            return root.result
        }

        function status(): string { return root.result }
    }
}
