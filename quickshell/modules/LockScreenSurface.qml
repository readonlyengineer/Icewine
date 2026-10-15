pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.breeze.components as Breeze
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami
import org.kde.ki18n
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
    LayoutMirroring.enabled: Application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true
    Component.onCompleted: {
        Qt.callLater(() => {
            if (root.session.authenticationRequired) password.forceActiveFocus()
            else submit.forceActiveFocus()
        })
    }
    Keys.forwardTo: !session.authenticating && session.authenticationRequired
        && [root, form, form.userList].includes(root.Window.window?.activeFocusItem) ? [password] : []

    // Native Breeze components expect KDE's translation context. Forward to
    // KI18n, retaining their translation domains and translated accessibility.
    readonly property KI18nContext translations: KI18nContext {
        translationDomain: "plasma_lookandfeel_org.kde.lookandfeel"
    }
    function i18n(...args) { return translations.i18n(...args) }
    function i18nc(...args) { return translations.i18nc(...args) }
    function i18nd(...args) { return translations.i18nd(...args) }
    function i18ndc(...args) { return translations.i18ndc(...args) }

    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.Complementary
    Kirigami.Theme.backgroundColor: Theme.Palette.dark ? "#000000" : "#ffffff"
    Kirigami.Theme.textColor: Theme.Palette.foreground
    Kirigami.Theme.disabledTextColor: Theme.Palette.muted
    Kirigami.Theme.highlightColor: Theme.Palette.primary
    Kirigami.Theme.highlightedTextColor: Theme.Palette.highlightedText
    Kirigami.Theme.negativeTextColor: Theme.Palette.error

    Rectangle {
        objectName: "lockBackdrop"
        anchors.fill: parent
        color: root.Kirigami.Theme.backgroundColor
    }
    function revealPassword() {
        form.y = 0
        if (keyboardInset > 0)
            form.y = Math.min(0, height - keyboardInset
                - password.mapToItem(form, 0, password.height).y - Kirigami.Units.largeSpacing)
    }
    onHeightChanged: Qt.callLater(revealPassword)
    onWidthChanged: Qt.callLater(revealPassword)
    onKeyboardInsetChanged: Qt.callLater(revealPassword)

    Breeze.Clock {
        anchors.horizontalCenter: parent.horizontalCenter
        y: (form.userList.y + form.y) / 2 - height / 2
        visible: y > 0
    }
    Breeze.SessionManagementScreen {
        id: form
        width: parent.width
        height: parent.height + Kirigami.Units.gridUnit * 3
        focus: true
        enabled: !root.session.authenticating
        userListCurrentIndex: 0
        userListModel: ListModel {
            Component.onCompleted: append({ name: Quickshell.env("USER") || "User",
                realName: Quickshell.env("USER") || "User", icon: "", needsPassword: root.session.authenticationRequired })
        }
        notificationMessage: root.session.authenticating ? qsTr("Authenticating…")
            : root.session.failed ? qsTr("Incorrect password") : ""
        onNotificationMessageChanged: Qt.callLater(root.revealPassword)
        onUserSelected: password.forceActiveFocus()
        actionItemsVisible: root.keyboardInset === 0
        actionItems: [
            Breeze.ActionButton {
                icon.name: "system-reboot"
                text: qsTr("Restart")
                onClicked: root.session.requestReboot()
            },
            Breeze.ActionButton {
                icon.name: "system-shutdown"
                text: qsTr("Shut Down")
                onClicked: root.session.requestShutdown()
            }
        ]
        RowLayout {
            Layout.fillWidth: true
            PlasmaExtras.PasswordField {
                id: password
                objectName: "lockPassword"
                Layout.fillWidth: true
                font.pointSize: Kirigami.Theme.defaultFont.pointSize + 1
                visible: root.session.authenticationRequired
                focus: root.session.authenticationRequired
                text: root.session.password
                placeholderText: qsTr("Password")
                Accessible.name: placeholderText
                Kirigami.Theme.inherit: false
                Kirigami.Theme.backgroundColor: Theme.Palette.backgroundDark
                Kirigami.Theme.textColor: Theme.Palette.foreground
                Kirigami.Theme.disabledTextColor: Theme.Palette.foregroundDark
                Kirigami.Theme.highlightColor: Theme.Palette.primary
                Kirigami.Theme.highlightedTextColor: Theme.Palette.highlightedText
                Keys.onPressed: event => {
                    if (event.matches(StandardKey.Undo)) event.accepted = true
                    else if (!activeFocus) {
                        forceActiveFocus()
                        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                            event.accepted = true
                    }
                }
                rightActions: [] // Match the upstream login field.
                onTextChanged: {
                    if (!root.session.authenticating && root.session.password !== text)
                        root.session.password = text
                }
                onAccepted: root.session.submit()
                onActiveFocusChanged: if (activeFocus) Qt.callLater(root.revealPassword)
            }
            PlasmaComponents.Button {
                id: submit
                focus: !root.session.authenticationRequired
                objectName: "lockSubmit"
                Accessible.name: qsTr("Unlock")
                Kirigami.Theme.inherit: false
                Kirigami.Theme.backgroundColor: Theme.Palette.surface
                Kirigami.Theme.textColor: Theme.Palette.foreground
                Kirigami.Theme.highlightColor: Theme.Palette.primary
                Layout.preferredHeight: password.implicitHeight
                Layout.preferredWidth: root.session.authenticationRequired ? height : implicitWidth
                icon.name: root.session.authenticationRequired
                    ? (root.LayoutMirroring.enabled ? "go-previous" : "go-next") : ""
                text: root.session.authenticationRequired ? "" : qsTr("Unlock")
                onClicked: root.session.submit()
                Keys.onEnterPressed: clicked()
                Keys.onReturnPressed: clicked()
            }
        }
    }
    PlasmaComponents.ToolButton {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: Kirigami.Units.smallSpacing
        anchors.bottomMargin: Kirigami.Units.smallSpacing + root.keyboardInset
        text: qsTr("Virtual Keyboard")
        focusPolicy: Qt.TabFocus
        icon.name: root.keyboardInset > 0 ? "input-keyboard-virtual-on" : "input-keyboard-virtual-off"
        visible: root.session.authenticationRequired
        onClicked: {
            password.forceActiveFocus()
            root.session.toggleKeyboard(root)
        }
    }
    Breeze.RejectPasswordAnimation { id: rejection; target: form }
    Connections {
        target: root.session
        function onPasswordChanged() {
            if (!root.session.authenticating && password.text !== root.session.password)
                password.text = root.session.password
        }
        function onAuthenticatingChanged() {
            // PAM retains its pending response; clear the visible field without
            // erasing that response before PamContext has consumed it.
            password.text = root.session.authenticating ? "" : root.session.password
            if (!root.session.authenticating) {
                password.forceActiveFocus()
                if (root.session.failed && root.animationsEnabled) rejection.start()
            }
        }
    }
}
