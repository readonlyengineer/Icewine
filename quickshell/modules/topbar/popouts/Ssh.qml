pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Window
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
    property string expectedFingerprint: ""
    implicitHeight: 471
    contentHeight: content.implicitHeight + 16
    boundsBehavior: Flickable.StopAtBounds
    clip: true

    function clearSecrets() {
        expectedFingerprint = ""
        privateKey.clear()
        fromFile.checked = false
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
        publicKey = ""
        pending = null
        if (backend.running) backend.signal(15)
    }
    function request(action, publicValue = "") {
        if (busy || !active || (action !== "status" && !available)) return
        pending = {action: action}
        if (action === "remove") pending.public = publicValue
        if (action === "import" || action === "generate") {
            if (action === "import" && !fromFile.checked) pending.private = privateKey.text
            else pending.path = keyPath.text
            if (action === "import" && fromFile.checked && expectedFingerprint)
                pending.expectedFingerprint = expectedFingerprint
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
    function openForm(kind, path = "", fingerprint = "") {
        if (!active || busy || !available) return
        clearSecrets()
        form = kind
        fromFile.checked = kind === "import" && path !== ""
        keyPath.text = path
        expectedFingerprint = fingerprint
        publicKey = ""
        contentY = 0
        Qt.callLater(() => {
            if (root.active && root.form === kind)
                (kind === "import" && !path ? privateKey : passphrase).forceActiveFocus()
        })
    }
    function reveal(item) {
        const top = item.mapToItem(content, 0, 0).y + content.y
        contentY = Math.max(0, Math.min(Math.max(0, contentHeight - height),
            Math.min(top, Math.max(contentY, top + item.height - height))))
    }
    function revealFocused() {
        const focused = root.Window.window?.activeFocusItem
        for (let item = focused; item; item = item.parent) {
            if (item === root) { root.reveal(focused); break }
        }
    }
    onContentHeightChanged: Qt.callLater(root.revealFocused)
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
        property string value: ""
        command: ["wl-copy", "--type", "text/plain"]
        stdinEnabled: true
        onStarted: { write(value); value = ""; stdinEnabled = false }
        onExited: (code, status) => root.message = code === 0 && status === 0
            ? "Public key copied" : "Could not copy the public key"
    }
    Timer { interval: 5000; repeat: true; running: root.active && !root.form && !root.busy; onTriggered: root.request("status") }

    component SshButton: ActionButton {
        id: button
        property bool primary: false
        property bool small: false
        implicitWidth: label.implicitWidth + (small ? 18 : 24)
        implicitHeight: small ? 30 : 34
        font.pixelSize: small ? 10 : 12
        background: Rectangle {
            radius: 9
            color: button.down ? Theme.Palette.primaryDark : button.hovered ? Theme.Palette.selection
                : button.primary ? Theme.Palette.primary : Theme.Palette.surface
            border.width: button.activeFocus ? 2 : 0
            border.color: Theme.Palette.primary
        }
        contentItem: Text {
            id: label
            text: button.text
            font: button.font
            color: !button.enabled ? Theme.Palette.muted : button.primary ? Theme.Palette.highlightedText : Theme.Palette.foreground
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        onActiveFocusChanged: if (activeFocus) { root.reveal(this); Qt.callLater(root.revealFocused) }
    }
    component KeyField: Controls.TextField {
        id: field
        implicitHeight: 40
        font: importButton.font
        color: Theme.Palette.foreground
        placeholderTextColor: Theme.Palette.foregroundDark
        padding: 10
        selectByMouse: true
        background: Rectangle {
            radius: 7
            color: Theme.Palette.backgroundDark
            border.width: field.activeFocus ? 2 : 1
            border.color: field.activeFocus ? Theme.Palette.primary : Theme.Palette.border
        }
        onActiveFocusChanged: if (activeFocus) { root.reveal(this); Qt.callLater(root.revealFocused) }
    }
    component KeyCheck: Controls.CheckBox {
        id: check
        font: importButton.font
        spacing: 8
        padding: 0
        indicator: Rectangle {
            x: 0; y: (check.height - height) / 2
            width: 16; height: 16; radius: 3
            color: check.checked ? Theme.Palette.primary : Theme.Palette.backgroundDark
            border.color: check.activeFocus ? Theme.Palette.primary : Theme.Palette.border
            border.width: check.activeFocus ? 2 : 1
            Text { anchors.centerIn: parent; text: check.checked ? "✓" : ""; color: Theme.Palette.highlightedText; font: check.font }
        }
        contentItem: Text {
            leftPadding: check.indicator.width + check.spacing
            text: check.text; font: check.font
            color: check.enabled ? Theme.Palette.foreground : Theme.Palette.muted
            verticalAlignment: Text.AlignVCenter
        }
        onActiveFocusChanged: if (activeFocus) { root.reveal(this); Qt.callLater(root.revealFocused) }
    }
    component FieldLabel: Text {
        font: importButton.font
        color: Theme.Palette.foreground
        topPadding: 14
        bottomPadding: 6
    }

    Column {
        id: content
        x: 16; width: parent.width - 32
        spacing: 0
        Text {
            visible: text !== ""
            width: parent.width
            bottomPadding: 12
            text: root.error || (root.busy ? "Working…" : root.message || (!root.available ? "Local agent unavailable" : ""))
            textFormat: Text.PlainText
            color: root.error ? Theme.Palette.error : Theme.Palette.foregroundDark
            font: importButton.font
            wrapMode: Text.WrapAnywhere
            Accessible.role: Accessible.StaticText
            Accessible.name: text
        }
        Column {
            visible: root.form === ""
            width: parent.width
            Row {
                width: parent.width; spacing: 8
                SshButton { id: importButton; width: (parent.width - 16) / 3; text: "Import key"; primary: true; Accessible.name: "Import SSH key"; enabled: root.active && root.available && !root.busy; onClicked: root.openForm("import") }
                SshButton { width: (parent.width - 16) / 3; text: "Generate"; Accessible.name: "Generate SSH key"; enabled: root.active && root.available && !root.busy; onClicked: root.openForm("generate") }
                SshButton { width: (parent.width - 16) / 3; text: "↻"; Accessible.name: "Refresh SSH keys"; enabled: root.active && !root.busy; onClicked: root.request("status") }
            }
            Item { width: 1; height: 20 }
            Text {
                visible: root.entries.length > 0
                text: "IDENTITIES · " + root.entries.length
                font { family: importButton.font.family; pixelSize: 10; letterSpacing: 1 }
                color: Theme.Palette.foregroundDark
                bottomPadding: 8
            }
            Text {
                visible: !root.busy && root.entries.length === 0
                width: parent.width; wrapMode: Text.Wrap
                text: "No identities discovered.\nImport an existing key or generate a new one."
                color: Theme.Palette.foregroundDark; font: importButton.font
            }
            Repeater {
                model: root.form ? [] : root.entries
                delegate: Column {
                    id: identity
                    required property var modelData
                    width: parent.width
                    Rectangle {
                        width: parent.width; height: details.implicitHeight + 24
                        radius: 9; color: Qt.tint(Theme.Palette.background, Qt.rgba(Theme.Palette.dark ? 1 : 0, Theme.Palette.dark ? 1 : 0, Theme.Palette.dark ? 1 : 0, 0.045))
                        Column {
                            id: details
                            x: 12; y: 12; width: parent.width - 24
                            Row {
                                width: parent.width; spacing: 8
                                Text {
                                    width: parent.width - status.width - 8
                                    text: identity.modelData.paths.length ? identity.modelData.paths[0].split("/").pop() : identity.modelData.temporary ? "Temporary identity" : "Agent identity"
                                    elide: Text.ElideMiddle; textFormat: Text.PlainText
                                    color: Theme.Palette.foreground
                                    font { family: importButton.font.family; pixelSize: 12; bold: true }
                                }
                                Text {
                                    id: status
                                    text: identity.modelData.loaded ? "Loaded" : "On disk"
                                    color: identity.modelData.loaded ? Theme.Palette.success : Theme.Palette.foregroundDark
                                    font { family: importButton.font.family; pixelSize: 10 }
                                }
                            }
                            Text {
                                width: parent.width
                                text: (identity.modelData.paths.length ? identity.modelData.paths.join("\n") : "Agent only") + " · " + identity.modelData.type
                                textFormat: Text.PlainText; color: Theme.Palette.foregroundDark
                                font { family: importButton.font.family; pixelSize: 10 }
                                topPadding: 5; bottomPadding: 5; wrapMode: Text.WrapAnywhere
                            }
                            Text {
                                width: parent.width; text: identity.modelData.fingerprint
                                textFormat: Text.PlainText; color: Theme.Palette.foregroundDark
                                font { family: importButton.font.family; pixelSize: 10 }
                                wrapMode: Text.WrapAnywhere
                            }
                            Item { width: 1; height: 12 }
                            Row {
                                spacing: 8
                                SshButton {
                                    small: true; text: "Public key"; visible: !!identity.modelData.public
                                    Accessible.name: "Show public SSH key " + identity.modelData.fingerprint
                                    onClicked: root.publicKey = root.publicKey === identity.modelData.public ? "" : identity.modelData.public
                                }
                                SshButton {
                                    small: true; text: "Unload"; visible: identity.modelData.loaded && identity.modelData.temporary
                                    Accessible.name: "Unload SSH key " + identity.modelData.fingerprint
                                    enabled: root.active && root.available && !root.busy
                                    onClicked: root.request("remove", identity.modelData.public)
                                }
                                SshButton {
                                    small: true; text: "Load"; visible: !identity.modelData.loaded && !!identity.modelData.importPath
                                    Accessible.name: "Load SSH key " + identity.modelData.fingerprint
                                    enabled: root.active && root.available && !root.busy
                                    onClicked: root.openForm("import", identity.modelData.importPath, identity.modelData.fingerprint)
                                }
                            }
                            Item { visible: disclosure.visible; width: 1; height: 10 }
                            Rectangle {
                                id: disclosure
                                visible: !!identity.modelData.public && root.publicKey === identity.modelData.public
                                width: parent.width; height: publicContent.implicitHeight + 24
                                radius: 8; color: Theme.Palette.backgroundDark
                                Column {
                                    id: publicContent
                                    x: 12; y: 12; width: parent.width - 24; spacing: 8
                                    Text {
                                        width: parent.width; text: identity.modelData.public
                                        textFormat: Text.PlainText; color: Theme.Palette.foreground
                                        font { family: importButton.font.family; pixelSize: 10 }
                                        wrapMode: Text.WrapAnywhere
                                    }
                                    SshButton {
                                        small: true; text: "Copy public key"
                                        Accessible.name: "Copy public SSH key " + identity.modelData.fingerprint
                                        enabled: !copy.running
                                        onYChanged: if (activeFocus) Qt.callLater(() => { if (activeFocus) root.reveal(this) })
                                        onClicked: { copy.value = identity.modelData.public; copy.stdinEnabled = true; copy.running = true }
                                    }
                                }
                                onHeightChanged: Qt.callLater(() => {
                                    const focused = root.Window.window?.activeFocusItem
                                    if (focused && publicContent.children.includes(focused)) root.reveal(focused)
                                })
                            }
                        }
                    }
                    Item { width: 1; height: 8 }
                }
            }
        }
        Column {
            visible: root.form !== ""
            width: parent.width
            Text {
                width: parent.width; topPadding: 14
                text: root.form === "import" ? "Import key" : "Generate key"
                font { family: importButton.font.family; pixelSize: 15 }
                color: Theme.Palette.primary
            }
            KeyCheck {
                id: fromFile
                visible: root.form === "import"
                text: "Import from file"; Accessible.name: "Import SSH key from file"
                onCheckedChanged: { root.expectedFingerprint = ""; privateKey.clear(); keyPath.clear(); passphrase.clear() }
            }
            KeyCheck {
                id: permanent
                visible: root.form === "generate"
                text: "Save permanently to a new file"; Accessible.name: "Save SSH key permanently"
            }
            FieldLabel { visible: privateInput.visible; text: "Private key text" }
            Controls.ScrollView {
                id: privateInput
                width: parent.width; height: 110
                visible: root.form === "import" && !fromFile.checked
                contentWidth: availableWidth; clip: true
                Controls.ScrollBar.horizontal.policy: Controls.ScrollBar.AlwaysOff
                Controls.TextArea {
                    id: privateKey
                    placeholderText: "Paste multiline private key"; Accessible.name: "Pasted SSH private key"
                    textFormat: TextEdit.PlainText; wrapMode: TextEdit.WrapAnywhere; selectByMouse: true
                    inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
                    Keys.onTabPressed: event => { passphrase.forceActiveFocus(); event.accepted = true }
                    font: importButton.font; color: Theme.Palette.foreground; placeholderTextColor: Theme.Palette.foregroundDark; padding: 10
                    background: Rectangle {
                        radius: 7; color: Theme.Palette.backgroundDark
                        border.width: privateKey.activeFocus ? 2 : 1
                        border.color: privateKey.activeFocus ? Theme.Palette.primary : Theme.Palette.border
                    }
                    onActiveFocusChanged: if (activeFocus) root.reveal(privateInput)
                }
            }
            FieldLabel { visible: keyPath.visible; text: root.form === "import" ? "Existing private key path" : "Save to a new key path" }
            KeyField {
                id: keyPath
                width: parent.width
                visible: (root.form === "import" && fromFile.checked) || (root.form === "generate" && permanent.checked)
                placeholderText: root.form === "import" ? "/absolute/path/to/key" : "/absolute/path/to/new/key"
                Accessible.name: "SSH key path"
                onTextChanged: root.expectedFingerprint = ""
                onAccepted: passphrase.forceActiveFocus()
            }
            FieldLabel { text: "Passphrase" }
            KeyField {
                id: passphrase
                width: parent.width; placeholderText: "Passphrase"; Accessible.name: "SSH key passphrase"
                onAccepted: { if (root.form === "import") root.request("import"); else confirmation.forceActiveFocus() }
                echoMode: TextInput.Password
            }
            FieldLabel { visible: confirmation.visible; text: "Confirm passphrase" }
            KeyField {
                id: confirmation
                width: parent.width; visible: root.form === "generate"
                placeholderText: "Confirm passphrase"; Accessible.name: "Confirm SSH passphrase"
                onAccepted: root.request("generate"); echoMode: TextInput.Password
            }
            Item { visible: unprotected.visible; width: 1; height: 14 }
            KeyCheck { id: unprotected; visible: root.form === "generate"; text: "Use no passphrase"; Accessible.name: "Generate SSH key without passphrase" }
            Item { width: 1; height: 20 }
            Row {
                width: parent.width; spacing: 8
                SshButton { width: (parent.width - 8) / 2; primary: true; text: root.form === "import" ? "Import key" : "Generate key"; Accessible.name: "Confirm SSH key action"; enabled: root.active && root.available && !root.busy; onClicked: root.request(root.form) }
                SshButton { width: (parent.width - 8) / 2; text: "Cancel"; Accessible.name: "Cancel SSH key action"; onClicked: root.cancel() }
            }
        }
        SshButton { visible: root.busy; text: "Cancel"; Accessible.name: "Cancel pending SSH action"; onClicked: root.cancel() }
    }
}
