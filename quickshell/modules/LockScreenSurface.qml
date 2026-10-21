pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import Quickshell
import Quickshell.Services.Mpris
import qs.icewine.theme as Theme
import "topbar/popouts" as Popouts

FocusScope {
    id: root
    required property var session
    property var players: Mpris.players.values
    // Match the topbar: first playing player, then first available (including paused).
    readonly property var player: players.find(candidate => candidate.isPlaying) ?? players[0] ?? null
    readonly property bool animationsEnabled: Theme.Palette.animate
    readonly property real keyboardInset: session.keyboardHost === root && session.keyboardVisible
        ? session.keyboardHeight : 0
    readonly property Item passwordInput: password
    focus: true
    readonly property bool inputBusy: session.authenticating || (session.externalKeyboardBusy ?? false)
    Keys.forwardTo: !root.inputBusy && session.authenticationRequired
        && root.Window.window?.activeFocusItem === root ? [password] : []
    Keys.onReturnPressed: if (!root.inputBusy && !session.authenticationRequired) session.submit()
    Keys.onEnterPressed: if (!root.inputBusy && !session.authenticationRequired) session.submit()
    Component.onCompleted: Qt.callLater(() => {
        if (session.authenticationRequired) { if (!session.keyboardHost) session.keyboardHost = root; password.forceActiveFocus() }
    })

    Rectangle {
        objectName: "lockBackdrop"
        anchors.fill: parent
        color: Theme.Palette.backgroundDark
    }
    Image {
        id: wallpaper
        objectName: "lockWallpaper"
        anchors.fill: parent
        source: root.session.wallpaper?.sourceUrl ?? ""
        cache: false
        // Quickshell constructs this surface before requesting the native lock.
        // Decode off the GUI thread; the opaque backdrop does not depend on readiness.
        asynchronous: true
        fillMode: Image.PreserveAspectCrop
        visible: false
        onStatusChanged: if (status === Image.Error && root.session.wallpaper?.selectionAvailable)
            Qt.callLater(() => {
                if (wallpaper.status === Image.Error) root.session.wallpaper.selectionAvailable = false
            })
    }
    MultiEffect {
        anchors.fill: parent
        source: wallpaper
        visible: wallpaper.status === Image.Ready
        blurEnabled: true
        blurMax: 64
        blur: 1.0
        autoPaddingEnabled: false
    }
    Rectangle {
        anchors.fill: parent
        objectName: "lockScrim"
        // Keep foreground text readable with both light and dark palettes.
        color: Theme.Palette.alpha(Theme.Palette.background, 0.9)
    }
    // Re-enabling after logind resume samples wall time before the next minute tick.
    SystemClock { id: time; precision: SystemClock.Minutes; enabled: !root.session.preparingForSleep }
    Timer { id: editFeedback; interval: 180 }
    Column {
        anchors.horizontalCenter: parent.horizontalCenter
        y: Math.max(8, Math.min((root.height - root.keyboardInset - height) / 2,
            nowPlaying.visible ? nowPlaying.y - height - (root.keyboardInset > 0 ? 8 : 16) : root.height - root.keyboardInset - height - 8))
        width: Math.max(0, parent.width - 32)
        spacing: root.keyboardInset > 0 ? 4 : 8
        Text {
            id: clock
            objectName: "lockClock"
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width
            // Budget the clock after the other rows so media cannot crowd the OSK.
            height: Math.min(implicitHeight, Math.max(34, root.height - root.keyboardInset
                - date.height - (nowPlaying.visible ? nowPlaying.height : 0)
                - password.height - statusText.height - 3 * parent.spacing
                - (nowPlaying.visible ? 56 : 24)))
            horizontalAlignment: Text.AlignHCenter
            fontSizeMode: Text.Fit
            minimumPixelSize: 28
            text: Qt.formatTime(time.date, Qt.locale().timeFormat(Locale.ShortFormat))
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: Math.min(112, root.width / 5, Math.max(28, (root.height-root.keyboardInset)/3))
            font.weight: Font.Light
            // Preserve the bounded edit tint using the current theme foreground.
            color: editFeedback.running
                ? Qt.tint(Theme.Palette.foreground, Theme.Palette.alpha(Theme.Palette.primary, 0.25)) : Theme.Palette.foreground
            scale: root.animationsEnabled && editFeedback.running ? 1.025 : 1
            Behavior on scale { NumberAnimation { duration: root.animationsEnabled ? 120 : 0 } }
        }
        Text {
            id: date
            objectName: "lockDate"
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: Qt.formatDate(time.date, Qt.locale().dateFormat(Locale.LongFormat))
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 20
            color: Theme.Palette.foreground
            wrapMode: Text.WordWrap
        }
        TextInput {
            id: password
            objectName: "lockPassword"
            width: parent.width
            height: 1
            opacity: 0
            visible: root.session.authenticationRequired
            enabled: !root.inputBusy
            focus: root.session.authenticationRequired && !root.inputBusy
            echoMode: TextInput.NoEcho
            inputMethodHints: Qt.ImhHiddenText | Qt.ImhSensitiveData
                | Qt.ImhNoPredictiveText | Qt.ImhNoAutoUppercase
            Accessible.name: qsTr("Password")
            text: root.session.password
            KeyNavigation.tab: keyboardToggle
            KeyNavigation.backtab: playPause.enabled && nowPlaying.visible ? playPause : keyboardToggle
            onTextEdited: {
                if (root.session.password === text) return
                root.session.password = text
                root.session.failed = false
                editFeedback.restart()
            }
            onAccepted: root.session.submit()
            Keys.onPressed: event => {
                if (!activeFocus) forceActiveFocus()
                if (event.matches(StandardKey.Undo) || event.matches(StandardKey.Redo)) {
                    event.accepted = true
                } else if (event.key === Qt.Key_Escape
                        || (event.key === Qt.Key_U && event.modifiers === Qt.ControlModifier)) {
                    if (text !== "") {
                        clear()
                        root.session.password = ""
                        root.session.failed = false
                        editFeedback.restart()
                    }
                    event.accepted = true
                }
            }
        }
        Text {
            id: statusText
            objectName: "lockStatus"
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.session.authenticating ? qsTr("Authenticating…")
                : root.session.failed ? qsTr("Incorrect password")
                : !root.session.authenticationRequired ? qsTr("Tap or press Enter to unlock") : ""
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 16
            color: Theme.Palette.foreground
            wrapMode: Text.WordWrap
        }
    }
    Item {
        id: nowPlaying
        objectName: "lockNowPlaying"
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: root.keyboardInset + 12
        width: Math.max(0, Math.min(parent.width - 128, 440))
        visible: root.player !== null
        height: Math.max(metadata.height, playPause.height)
        Column {
            id: metadata
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(0, parent.width - playPause.width - 12)
            spacing: 4
            Text {
                objectName: "lockTrackTitle"
                width: parent.width
                text: root.player ? "♫ " + (root.player.trackTitle || qsTr("Unknown track")) : ""
                textFormat: Text.PlainText
                horizontalAlignment: Text.AlignHCenter
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 16
                color: Theme.Palette.foreground
                elide: Text.ElideRight
                maximumLineCount: 1
            }
            Text {
                objectName: "lockTrackArtist"
                width: parent.width
                text: root.player?.trackArtist || root.player?.identity || ""
                textFormat: Text.PlainText
                visible: text !== ""
                horizontalAlignment: Text.AlignHCenter
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 14
                color: Theme.Palette.foreground
                elide: Text.ElideRight
                maximumLineCount: 1
            }
        }
        Popouts.ActionButton {
            id: playPause
            objectName: "lockPlayPause"
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: 96
            height: 44
            font.pixelSize: 14
            text: root.player?.isPlaying ? qsTr("Pause") : qsTr("Play")
            Accessible.name: text
            focusPolicy: Qt.TabFocus
            enabled: !root.inputBusy && (root.player?.canTogglePlaying ?? false)
            KeyNavigation.tab: password.visible ? password : keyboardToggle
            KeyNavigation.backtab: keyboardToggle
            onClicked: {
                if (root.player?.canTogglePlaying) root.player.togglePlaying()
                if (root.session.authenticationRequired) password.forceActiveFocus()
                else root.forceActiveFocus()
            }
        }
    }
    TapHandler {
        enabled: !root.inputBusy && !root.session.authenticationRequired
        onTapped: root.session.submit()
    }
    ToolButton {
        id: keyboardToggle
        objectName: "lockKeyboard"
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: 12
        anchors.bottomMargin: 12 + root.keyboardInset
        font.family: "JetBrainsMono Nerd Font"
        palette.buttonText: Theme.Palette.foreground
        text: "󰌌"
        font.pixelSize: 24
        width: 44
        height: 44
        Accessible.name: qsTr("Toggle virtual keyboard")
        focusPolicy: Qt.TabFocus
        enabled: root.session.authenticationRequired && !root.inputBusy
        KeyNavigation.tab: root.session.keyboardVisible ? root.session.keyboardView.firstControl
            : playPause.enabled && nowPlaying.visible ? playPause : password
        KeyNavigation.backtab: password
        onClicked: {
            password.forceActiveFocus()
            root.session.toggleKeyboard(root)
        }
    }
    onInputBusyChanged: {
        // A finite external chord can overlap lock acquisition. Keep all lock
        // text fields unfocused until its final roundtrip/exit has settled.
        if (inputBusy) { root.forceActiveFocus(); session.keyboardView?.cancel() }
        else if (session.authenticationRequired) password.forceActiveFocus()
    }
    Connections {
        target: root.Window.window
        function onActiveChanged() { if (root.Window.window.active && root.session.locked) root.session.keyboardHost = root }
    }
    onActiveFocusChanged: if (activeFocus && session.locked) session.keyboardHost = root
    Connections {
        target: root.session
        function onPasswordChanged() {
            if (!root.session.authenticating && password.text !== root.session.password)
                password.text = root.session.password
        }
        function onAuthenticatingChanged() {
            // PAM consumes the shared response; conceal and clear local copies now.
            password.text = root.session.authenticating ? "" : root.session.password
            if (!root.inputBusy && root.session.authenticationRequired)
                password.forceActiveFocus()
        }
    }
}
