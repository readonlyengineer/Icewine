pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as Controls
import qs.icewine.theme as Theme
import qs.config as Config

Item {
    id: root
    property color accent: Theme.Palette.primary
    required property var history
    property bool pasteBusy: false
    readonly property Item initialFocus: clear
    signal pasteRequested(string entry)
    implicitHeight: 390

    Row {
        id: header
        x: 12; y: 12
        width: parent.width - 24
        height: 34
        spacing: 6
        Text {
            width: parent.width - clear.width - parent.spacing
            anchors.verticalCenter: parent.verticalCenter
            text: "Clipboard"
            textFormat: Text.PlainText
            color: root.accent
            font { family: "JetBrainsMono Nerd Font"; pixelSize: 15; bold: true }
        }
        ActionButton {
            id: clear
            width: 108
            text: "Clear history"
            Accessible.name: "Clear clipboard history"
            enabled: root.history.available && !root.history.busy && !root.pasteBusy
                && (root.history.entries.length > 0 || root.history.error !== "")
            onClicked: root.history.request("clear")
        }
    }
    Controls.ComboBox {
        id: expiry
        x: 12; y: header.y + header.height + 8
        width: parent.width - 24
        model: ["Expire history: Off", "Expire history: 5 minutes", "Expire history: 30 minutes",
            "Expire history: 1 hour", "Expire history: 24 hours"]
        currentIndex: Config.Settings.clipboardExpiryChoices.indexOf(Config.Settings.clipboardExpiry)
        Accessible.name: "Clipboard history age limit"
        enabled: root.history.available && !root.history.busy && !root.pasteBusy
        onActivated: Config.Settings.setClipboardExpiry(Config.Settings.clipboardExpiryChoices[currentIndex])
    }
    Text {
        id: hint
        x: 12; y: expiry.y + expiry.height + 8
        width: parent.width - 24
        text: "Session only · text/PNG · 50 items, 5 MB each\nClick to load; ↑ sends Ctrl+V to the original app.\nAge starts on copy; loading does not renew it.\nShorter limits apply now; current clipboard is kept."
        textFormat: Text.PlainText
        color: Theme.Palette.muted
        font { family: "JetBrainsMono Nerd Font"; pixelSize: 10 }
        wrapMode: Text.WordWrap
    }
    Text {
        id: status
        x: 12; y: hint.y + hint.height + 8
        width: parent.width - 24
        text: root.history.error || (!root.history.available ? "Clipboard unavailable"
            : root.history.busy || root.pasteBusy ? "Working…"
            : root.history.entries.length === 0 ? "No clipboard history" : "")
        textFormat: Text.PlainText
        color: root.history.error ? Theme.Palette.secondary : Theme.Palette.muted
        font { family: "JetBrainsMono Nerd Font"; pixelSize: 11 }
        wrapMode: Text.WordWrap
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }
    Controls.ScrollView {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 12; top: status.bottom; topMargin: 8 }
        clip: true
        contentWidth: availableWidth
        Controls.ScrollBar.horizontal.policy: Controls.ScrollBar.AlwaysOff
        Column {
            width: parent.width
            spacing: 6
            Repeater {
                model: root.history.entries
                delegate: Rectangle {
                    id: row
                    required property var modelData
                    width: parent.width
                    height: 58
                    radius: 9
                    color: "transparent"
                    border.width: root.history.activeEntry === modelData.id ? 2 : 0
                    border.color: Theme.Palette.primary
                    Row {
                        anchors { fill: parent; margins: 4 }
                        spacing: 4
                        ActionButton {
                            id: load
                            width: Math.max(0, row.width - 8 - 2 * 38 - 2 * parent.spacing)
                            height: parent.height
                            enabled: root.history.available && !root.history.busy && !root.pasteBusy
                            text: row.modelData.preview
                            Accessible.name: "Load clipboard entry: " + (row.modelData.image ? "PNG image" : row.modelData.preview)
                            Accessible.description: root.history.activeEntry === row.modelData.id ? "Current clipboard" : ""
                            contentItem: Item {
                                Image {
                                    id: thumbnail
                                    anchors.centerIn: parent
                                    width: Math.min(64, parent.width); height: parent.height
                                    source: row.modelData.image ? row.modelData.thumbnail ?? "" : ""
                                    sourceSize { width: 64; height: 48 }
                                    fillMode: Image.PreserveAspectFit
                                    asynchronous: true
                                    cache: false
                                    visible: row.modelData.image && thumbnail.status === Image.Ready
                                }
                                Text {
                                    anchors.fill: parent
                                    visible: !thumbnail.visible
                                    text: row.modelData.image ? "PNG image · preview unavailable" : load.text
                                    textFormat: Text.PlainText
                                    color: Theme.Palette.foreground
                                    font: load.font
                                    wrapMode: Text.WrapAnywhere
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                            onClicked: root.history.request("load", row.modelData.id)
                        }
                        ActionButton {
                            width: 38; height: parent.height
                            text: "↑"
                            Accessible.name: "Paste clipboard entry: " + (row.modelData.image ? "PNG image" : row.modelData.preview)
                            enabled: root.history.available && !root.history.busy && !root.pasteBusy
                            onClicked: root.pasteRequested(row.modelData.id)
                        }
                        ActionButton {
                            width: 38; height: parent.height
                            text: "×"
                            Accessible.name: "Remove clipboard entry: " + (row.modelData.image ? "PNG image" : row.modelData.preview)
                            enabled: root.history.available && !root.history.busy && !root.pasteBusy
                            onClicked: root.history.request("remove", row.modelData.id)
                        }
                    }
                }
            }
        }
    }
}
