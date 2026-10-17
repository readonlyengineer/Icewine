pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import Quickshell
import qs.icewine.theme as Theme

FocusScope {
    id: root
    required property var session
    readonly property bool animationsEnabled: Theme.Palette.animate
    readonly property real keyboardInset: session.keyboardHost === root && session.keyboardVisible
        ? session.keyboardHeight : 0
    readonly property Item passwordInput: password
    focus: true
    Keys.forwardTo: !session.authenticating && session.authenticationRequired
        && root.Window.window?.activeFocusItem === root ? [password] : []
    Keys.onReturnPressed: if (!session.authenticationRequired) session.submit()
    Keys.onEnterPressed: if (!session.authenticationRequired) session.submit()
    Component.onCompleted: Qt.callLater(() => {
        if (session.authenticationRequired) password.forceActiveFocus()
    })

    Rectangle {
        objectName: "lockBackdrop"
        anchors.fill: parent
        color: "#101014"
    }
    Image {
        id: wallpaper
        objectName: "lockWallpaper"
        anchors.fill: parent
        source: root.session.wallpaper?.sourceUrl ?? ""
        cache: false
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
        color: "#99000000"
    }
    SystemClock { id: time; precision: SystemClock.Minutes }
    Timer { id: editFeedback; interval: 180 }
    Column {
        anchors.horizontalCenter: parent.horizontalCenter
        y: Math.max(16, (root.height - root.keyboardInset - height) / 2)
        width: Math.max(0, parent.width - 32)
        spacing: 8
        Text {
            id: clock
            objectName: "lockClock"
            anchors.horizontalCenter: parent.horizontalCenter
            text: Qt.formatTime(time.date, Qt.locale().timeFormat(Locale.ShortFormat))
            font.pixelSize: Math.min(112, root.width / 5)
            font.weight: Font.Light
            // A pale accent keeps the large clock readable over any dimmed image.
            color: editFeedback.running
                ? Qt.tint("#ffffff", Theme.Palette.alpha(Theme.Palette.primary, 0.25)) : "#ffffff"
            scale: root.animationsEnabled && editFeedback.running ? 1.025 : 1
            Behavior on scale { NumberAnimation { duration: root.animationsEnabled ? 120 : 0 } }
        }
        Text {
            objectName: "lockDate"
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: Qt.formatDate(time.date, Qt.locale().dateFormat(Locale.LongFormat))
            font.pixelSize: 20
            color: "#ffffff"
            wrapMode: Text.WordWrap
        }
        TextInput {
            id: password
            objectName: "lockPassword"
            width: parent.width
            height: 1
            opacity: 0
            visible: root.session.authenticationRequired
            enabled: !root.session.authenticating
            focus: root.session.authenticationRequired
            echoMode: TextInput.NoEcho
            inputMethodHints: Qt.ImhHiddenText | Qt.ImhSensitiveData
                | Qt.ImhNoPredictiveText | Qt.ImhNoAutoUppercase
            Accessible.name: qsTr("Password")
            text: root.session.password
            KeyNavigation.tab: keyboardToggle
            KeyNavigation.backtab: keyboardToggle
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
            objectName: "lockStatus"
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.session.authenticating ? qsTr("Authenticating…")
                : root.session.failed ? qsTr("Incorrect password")
                : !root.session.authenticationRequired ? qsTr("Tap or press Enter to unlock") : ""
            font.pixelSize: 16
            color: "#ffffff"
            wrapMode: Text.WordWrap
        }
    }
    TapHandler {
        enabled: !root.session.authenticationRequired
        onTapped: root.session.submit()
    }
    ToolButton {
        id: keyboardToggle
        objectName: "lockKeyboard"
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: 12
        anchors.bottomMargin: 12 + root.keyboardInset
        text: qsTr("Virtual Keyboard")
        Accessible.name: text
        focusPolicy: Qt.TabFocus
        visible: root.session.authenticationRequired
        enabled: !root.session.authenticating
        KeyNavigation.tab: password
        KeyNavigation.backtab: password
        onClicked: {
            password.forceActiveFocus()
            root.session.toggleKeyboard(root)
        }
    }
    Connections {
        target: root.session
        function onPasswordChanged() {
            if (!root.session.authenticating && password.text !== root.session.password)
                password.text = root.session.password
        }
        function onAuthenticatingChanged() {
            // PAM consumes the shared response; conceal and clear local copies now.
            password.text = root.session.authenticating ? "" : root.session.password
            if (!root.session.authenticating && root.session.authenticationRequired)
                password.forceActiveFocus()
        }
    }
}
