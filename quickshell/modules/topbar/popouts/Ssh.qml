pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as Controls
import Quickshell
import Quickshell.Io
import qs.icewine.theme as Theme

Flickable {
    id: root
    property bool active: false
    property bool busy: false
    property bool available: false
    property var entries: []
    property var pending: null
    property string form: ""
    property string error: ""
    property string message: ""
    property string publicKey: ""
    implicitHeight: 480
    contentHeight: content.implicitHeight + 24
    boundsBehavior: Flickable.StopAtBounds
    clip: true

    function clearSecrets() {
        privateKey.clear()
        pasted.checked = false
        keyPath.text = ""
        passphrase.text = ""
        confirmation.text = ""
        unprotected.checked = false
        permanent.checked = false
    }
    function cancel() {
        clearSecrets()
        form = ""
        contentY = 0
        pending = null
        if (backend.running) backend.signal(15)
    }
    function request(action, publicValue = "") {
        if (busy || !active) return
        pending = {action: action}
        if (action === "remove") pending.public = publicValue
        if (action === "import" || action === "generate") {
            if (action === "import" && pasted.checked) pending.private = privateKey.text
            else pending.path = keyPath.text
            pending.passphrase = passphrase.text
            if (action === "generate") {
                pending.storage = permanent.checked ? "permanent" : "temporary"
                pending.confirmation = confirmation.text
                pending.unprotected = unprotected.checked
            }
            clearSecrets()
            form = ""
        }
        error = ""
        message = ""
        busy = true
        backend.stdinEnabled = true
        deadline.restart()
        backend.running = true
    }
    function openForm(kind) {
        clearSecrets()
        form = kind
        publicKey = ""
        contentY = 0
        Qt.callLater(() => {
            if (root.active && root.form === kind)
                (kind === "import" ? keyPath : passphrase).forceActiveFocus()
        })
    }
    function reveal(item) {
        const top = item.mapToItem(content, 0, 0).y + content.y
        contentY = Math.max(0, Math.min(Math.max(0, contentHeight - height),
            Math.min(top, Math.max(contentY, top + item.height - height))))
    }
    onActiveChanged: {
        if (!active) cancel()
        else if (!busy) request("status")
    }
    Component.onDestruction: cancel()
    Keys.onEscapePressed: event => {
        if (form || busy) { cancel(); event.accepted = true }
        else event.accepted = false
    }

    Timer {
        id: deadline
        interval: 40000
        onTriggered: {
            root.cancel()
            root.error = "SSH request timed out. Refresh to check the agent."
            if (!backend.running) root.busy = false
        }
    }
    Process {
        id: backend
        command: ["icewine-ssh"]
        stdinEnabled: true
        stdout: StdioCollector { id: output }
        stderr: StdioCollector {} // Never forward native/private diagnostics into shell logs.
        onStarted: {
            if (root.pending) write(JSON.stringify(root.pending))
            root.pending = null
            stdinEnabled = false
        }
        onExited: (code, status) => {
            deadline.stop()
            root.pending = null
            root.busy = false
            try {
                if (code !== 0 || status !== 0) throw new Error("failed")
                const state = JSON.parse(output.text)
                root.entries = state.entries
                root.available = state.available
                root.error = state.error || ""
                root.message = state.message || ""
                if (state.public) root.publicKey = state.public
                if (state.saved) root.message += "\n" + state.saved
            } catch (_) {
                root.error = "SSH request cancelled or unavailable. Refresh to check the agent."
            }
        }
    }
    Process {
        id: copy
        command: ["wl-copy", "--type", "text/plain"]
        stdinEnabled: true
        onStarted: { write(root.publicKey); stdinEnabled = false }
        onExited: (code, status) => root.message = code === 0 && status === 0
            ? "Public key copied" : "Could not copy the public key"
    }
    Timer { interval: 5000; repeat: true; running: root.active && !root.form && !root.busy; onTriggered: root.request("status") }

    Column {
        id: content
        x: 12; y: 12; width: parent.width - 24
        spacing: 8
        Text {
            width: parent.width
            visible: root.form === ""
            text: "X unloads a temporary identity from the agent. Files, remote authorisation and existing connections are kept."
            textFormat: Text.PlainText
            color: Theme.Palette.muted
            font: importButton.font
            wrapMode: Text.Wrap
        }
        Text {
            width: parent.width
            text: root.error || (root.busy ? "Working…" : root.message || (!root.available ? "Local agent unavailable" : ""))
            textFormat: Text.PlainText
            color: root.error ? Theme.Palette.error : Theme.Palette.muted
            font: importButton.font
            wrapMode: Text.WrapAnywhere
            Accessible.role: Accessible.StaticText
            Accessible.name: text
        }
        Row {
            visible: root.form === ""
            width: parent.width; spacing: 6
            ActionButton { id: importButton; width: (parent.width - 12) / 3; text: "Import"; Accessible.name: "Import SSH key"; enabled: root.active && root.available && !root.busy; onClicked: root.openForm("import") }
            ActionButton { width: (parent.width - 12) / 3; text: "Generate"; Accessible.name: "Generate SSH key"; enabled: root.active && root.available && !root.busy; onClicked: root.openForm("generate") }
            ActionButton { width: (parent.width - 12) / 3; text: "Refresh"; Accessible.name: "Refresh SSH keys"; enabled: root.active && !root.busy; onClicked: root.request("status") }
        }
        Column {
            visible: root.form !== ""
            width: parent.width; spacing: 6
            Text {
                visible: root.form === "import"
                width: parent.width
                text: "Import temporarily · agent only. Existing key files are kept; pasted keys are not saved."
                textFormat: Text.PlainText
                color: Theme.Palette.muted
                font: importButton.font
                wrapMode: Text.Wrap
            }
            Controls.CheckBox {
                id: pasted
                visible: root.form === "import"
                text: "Paste private key text"
                Accessible.name: "Import SSH key from pasted text"
                font: importButton.font
                onCheckedChanged: { privateKey.clear(); keyPath.clear() }
                onActiveFocusChanged: if (activeFocus) root.reveal(this)
            }
            Controls.ScrollView {
                id: privateInput
                width: parent.width
                height: 120
                visible: root.form === "import" && pasted.checked
                contentWidth: availableWidth
                clip: true
                Controls.ScrollBar.horizontal.policy: Controls.ScrollBar.AlwaysOff
                Controls.TextArea {
                    id: privateKey
                    placeholderText: "Paste multiline private key"
                    Accessible.name: "Pasted SSH private key"
                    textFormat: TextEdit.PlainText
                    wrapMode: TextEdit.WrapAnywhere
                    selectByMouse: true
                    inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
                    Keys.onTabPressed: event => { passphrase.forceActiveFocus(); event.accepted = true }
                    font: importButton.font
                    onActiveFocusChanged: if (activeFocus) root.reveal(privateInput)
                }
            }
            Controls.CheckBox {
                id: permanent
                font: importButton.font
                onActiveFocusChanged: if (activeFocus) root.reveal(this)
                visible: root.form === "generate"
                text: checked ? "Permanent · save a key file" : "Temporary · agent only"
                Accessible.name: "Save SSH key permanently"
            }
            Controls.TextField {
                id: keyPath
                width: parent.width
                visible: (root.form === "import" && !pasted.checked) || permanent.checked
                placeholderText: root.form === "import" ? "Existing private key: absolute path" : "Save to: absolute new key path"
                Accessible.name: "SSH key path"
                onAccepted: passphrase.forceActiveFocus()
                selectByMouse: true
                font: importButton.font
                onActiveFocusChanged: if (activeFocus) root.reveal(this)
            }
            Controls.TextField {
                id: passphrase
                width: parent.width
                placeholderText: "Passphrase"
                Accessible.name: "SSH key passphrase"
                onAccepted: {
                    if (root.form === "import") root.request("import")
                    else confirmation.forceActiveFocus()
                }
                echoMode: TextInput.Password
                selectByMouse: true
                font: importButton.font
                onActiveFocusChanged: if (activeFocus) root.reveal(this)
            }
            Controls.TextField {
                id: confirmation
                width: parent.width
                visible: root.form === "generate"
                placeholderText: "Confirm passphrase"
                Accessible.name: "Confirm SSH passphrase"
                onAccepted: root.request("generate")
                echoMode: TextInput.Password
                selectByMouse: true
                font: importButton.font
                onActiveFocusChanged: if (activeFocus) root.reveal(this)
            }
            Controls.CheckBox {
                id: unprotected
                font: importButton.font
                onActiveFocusChanged: if (activeFocus) root.reveal(this)
                visible: root.form === "generate"
                text: "I choose no passphrase"
                Accessible.name: "Generate SSH key without passphrase"
            }
            Text {
                visible: root.form === "generate"
                width: parent.width
                text: permanent.checked ? "Saved files survive reboot. Load them later using Import. X never deletes them."
                    : "The generated private key is discarded after loading. X or reboot removes it from the agent."
                textFormat: Text.PlainText
                color: Theme.Palette.muted
                font: importButton.font
                wrapMode: Text.Wrap
            }
            Row {
                spacing: 6
                ActionButton { onActiveFocusChanged: if (activeFocus) root.reveal(this); text: "Confirm"; Accessible.name: "Confirm SSH key action"; enabled: root.active && !root.busy; onClicked: root.request(root.form) }
                ActionButton { onActiveFocusChanged: if (activeFocus) root.reveal(this); text: "Cancel"; Accessible.name: "Cancel SSH key action"; onClicked: root.cancel() }
            }
        }
        ActionButton {
            visible: root.busy
            text: "Cancel"; Accessible.name: "Cancel pending SSH action"
            onClicked: root.cancel()
        }
        Text {
            visible: root.form === "" && root.publicKey !== ""
            width: parent.width
            text: root.publicKey
            textFormat: Text.PlainText
            color: Theme.Palette.foreground
            font: importButton.font
            wrapMode: Text.WrapAnywhere
        }
        ActionButton {
            visible: root.form === "" && root.publicKey !== ""
            text: "Copy public key"; enabled: !copy.running
            onClicked: { copy.stdinEnabled = true; copy.running = true }
        }
        Text {
            visible: !root.form && !root.busy && root.entries.length === 0
            text: "No discoverable client identities"
            color: Theme.Palette.muted
            font: importButton.font
        }
        Repeater {
            model: root.form ? [] : root.entries
            delegate: Rectangle {
                id: identity
                required property var modelData
                width: parent.width
                height: details.implicitHeight + 20
                radius: 9
                color: Theme.Palette.surface
                Column {
                    id: details
                    x: 10; y: 10; width: parent.width - 20; spacing: 6
                    Text {
                        width: parent.width
                        text: identity.modelData.type + " · " + identity.modelData.fingerprint + "\n"
                            + (identity.modelData.loaded ? "Loaded" : "On disk; agent " + (root.available ? "not loaded" : "unknown"))
                            + (identity.modelData.origin ? " · " + identity.modelData.origin : "")
                            + (identity.modelData.paths.length ? "\n" + identity.modelData.paths.join("\n") : "")
                        textFormat: Text.PlainText
                        color: Theme.Palette.foreground
                        font: importButton.font
                        wrapMode: Text.WrapAnywhere
                    }
                    Row {
                        spacing: 6
                        ActionButton {
                            text: "Public key"; visible: !!identity.modelData.public
                            Accessible.name: "Show public SSH key " + identity.modelData.fingerprint
                            onActiveFocusChanged: if (activeFocus) root.reveal(identity)
                            onClicked: { root.publicKey = identity.modelData.public; root.contentY = 0 }
                        }
                        ActionButton {
                            text: "×"; visible: identity.modelData.loaded && identity.modelData.temporary
                            Accessible.name: "Unload SSH key " + identity.modelData.fingerprint
                            enabled: root.available && !root.busy
                            onActiveFocusChanged: if (activeFocus) root.reveal(identity)
                            onClicked: root.request("remove", identity.modelData.public)
                        }
                    }
                }
            }
        }
    }
}
