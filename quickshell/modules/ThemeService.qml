import QtQuick
import Quickshell
import Quickshell.Io
import qs.icewine.theme as Theme

QtObject {
    id: root

    property string requested: ""
    property string activeRequest: ""
    property bool selectionSaved: false
    property string result: Theme.Palette.refresh
        ? "applied: " + Theme.Palette.snapshot.themeId
        : "pending: user-owned Palette.qml does not support live reload"
    readonly property string policy: Quickshell.env("ICEWINE_THEME_POLICY")
    readonly property var installed: Quickshell.env("ICEWINE_THEME_IDS").split(":")

    property Process renderer: Process {
        id: renderer
        command: ["icewine-theme", "theme", root.activeRequest]
        environment: ({ ICEWINE_THEME_FROM_SHELL: "1" })
        stdout: SplitParser {
            onRead: data => {
                if (data === "Saved selection: " + root.activeRequest)
                    root.selectionSaved = true
            }
        }
        onExited: (code, status) => {
            if (!root.selectionSaved) {
                root.result = "failed: selection could not be saved"
            } else if (root.policy) {
                root.result = "saved: " + root.activeRequest + "; Nix policy keeps " + root.policy
            } else if (!Theme.Palette.refresh || !Theme.Palette.refresh()) {
                root.result = "failed: theme saved, but shell palette could not be applied"
            } else if (!root.policy && Theme.Palette.snapshot.themeId !== root.activeRequest
                       && root.requested === root.activeRequest) {
                root.result = "failed: theme saved, but shell palette kept its previous colours"
            } else if (code !== 0) {
                root.result = "partial: shell palette applied; some consumer notifications failed"
            } else {
                root.result = "applied: " + Theme.Palette.snapshot.themeId
            }
            if (root.requested !== root.activeRequest)
                Qt.callLater(root.start)
        }
    }

    function start(): void {
        activeRequest = requested
        selectionSaved = false
        result = "pending: applying " + requested
        renderer.running = true
    }

    property IpcHandler ipc: IpcHandler {
        target: "theme"

        function select(theme: string): string {
            if (!/^[a-z0-9][a-z0-9-]*$/.test(theme) || root.installed.indexOf(theme) < 0)
                return "failed: theme is not installed: " + theme
            root.requested = theme
            root.result = "pending: applying " + theme
            if (!renderer.running)
                root.start()
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
