pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as Controls
import qs.theme as Theme
import "WinterModel.js" as WinterModel

Item {
    id: root

    required property var controller
    readonly property real scaleFactor: WinterModel.scaleFactor(width, height)
    readonly property real keyboardInset: WinterModel.keyboardInset(controller.keyboardHost,
        root, controller.keyboardVisible, controller.keyboardHeight)

    Rectangle {
        anchors.fill: parent
        color: "#000000"
    }

    component TextButton: Controls.Button {
        id: button
        property color normalColor: Theme.Palette.muted
        property color hoverColor: Theme.Palette.foreground
        property real labelSize: 12 * root.scaleFactor

        focusPolicy: Qt.StrongFocus
        background: null
        contentItem: Text {
            text: button.text
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            color: button.down || button.hovered || button.activeFocus
                ? button.hoverColor : button.normalColor
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: button.labelSize
            font.letterSpacing: 2 * root.scaleFactor
            font.bold: button.activeFocus
        }
        Keys.onReturnPressed: click()
        Keys.onEnterPressed: click()
    }

    Column {
        anchors.top: parent.top
        anchors.topMargin: 120 * root.scaleFactor
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 15 * root.scaleFactor

        Text {
            id: clock
            property date now: new Date()

            anchors.horizontalCenter: parent.horizontalCenter
            text: Qt.formatTime(now, "HH:mm")
            color: Theme.Palette.primary
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 180 * root.scaleFactor
            font.weight: Font.Thin

            Timer {
                interval: 1000
                running: true
                repeat: true
                onTriggered: clock.now = new Date()
            }
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: Qt.formatDate(clock.now, "dddd, MMMM d").toUpperCase()
            color: Theme.Palette.success
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 18 * root.scaleFactor
            font.letterSpacing: 12 * root.scaleFactor
            font.weight: Font.DemiBold
        }
    }

    Column {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: root.keyboardInset > 0
            ? -100 * root.scaleFactor : 160 * root.scaleFactor
        width: Math.min(parent.width - 48, 400 * root.scaleFactor)
        spacing: 25 * root.scaleFactor

        TextButton {
            width: parent.width
            height: 42 * root.scaleFactor
            visible: root.controller.users.length > 0
            enabled: root.controller.users.length > 1 && !root.controller.busy
            Accessible.name: "Select user"
            text: root.controller.userLabel.toUpperCase()
            normalColor: Theme.Palette.foreground
            hoverColor: Theme.Palette.primary
            labelSize: 18 * root.scaleFactor
            onClicked: root.controller.nextUser()
        }

        Item {
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(parent.width, 320 * root.scaleFactor)
            height: 50 * root.scaleFactor
            visible: root.controller.authenticationRequired

            TextInput {
                id: password
                anchors.fill: parent
                horizontalAlignment: TextInput.AlignHCenter
                verticalAlignment: TextInput.AlignVCenter
                enabled: !root.controller.busy
                focus: true
                echoMode: root.controller.secretInput ? TextInput.Password : TextInput.Normal
                inputMethodHints: root.controller.secretInput
                    ? Qt.ImhSensitiveData : Qt.ImhNone
                color: Theme.Palette.foreground
                selectionColor: Theme.Palette.primary
                selectedTextColor: Theme.Palette.backgroundDark
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 24 * root.scaleFactor
                font.letterSpacing: root.controller.secretInput ? 8 * root.scaleFactor : 1
                Accessible.name: root.controller.prompt || "Password"
                onTextChanged: {
                    if (root.controller.password !== text)
                        root.controller.password = text
                }
                onAccepted: root.controller.submit()

                Text {
                    anchors.centerIn: parent
                    visible: password.text.length === 0
                    text: root.controller.prompt.toUpperCase()
                    color: Theme.Palette.muted
                    opacity: 0.75
                    font.family: "JetBrainsMono Nerd Font"
                    font.pixelSize: 14 * root.scaleFactor
                    font.letterSpacing: 4 * root.scaleFactor
                }

                Connections {
                    target: root.controller
                    function onPasswordChanged() {
                        if (password.text !== root.controller.password)
                            password.text = root.controller.password
                    }
                }
            }

            Rectangle {
                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                height: password.activeFocus ? 2 : 1
                width: password.activeFocus ? parent.width : parent.width * 0.3
                color: root.controller.failed ? Theme.Palette.error : Theme.Palette.foreground
                opacity: password.activeFocus ? 0.9 : 0.35
                Behavior on width { NumberAnimation { duration: 250; easing.type: Easing.OutQuart } }
            }
        }

        Text {
            width: parent.width
            height: 18 * root.scaleFactor
            horizontalAlignment: Text.AlignHCenter
            text: root.controller.message
            color: root.controller.failed ? Theme.Palette.error : Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 11 * root.scaleFactor
            font.letterSpacing: 1 * root.scaleFactor
        }

        TextButton {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 180 * root.scaleFactor
            height: 48 * root.scaleFactor
            visible: !root.controller.authenticationRequired
            Accessible.name: "Unlock"
            text: "UNLOCK"
            normalColor: Theme.Palette.foreground
            hoverColor: Theme.Palette.primary
            onClicked: root.controller.submit()
        }
    }

    Row {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.leftMargin: 50 * root.scaleFactor
        anchors.bottomMargin: 50 * root.scaleFactor + root.keyboardInset
        spacing: 12 * root.scaleFactor
        visible: root.controller.sessions.length > 0

        TextButton {
            height: 40 * root.scaleFactor
            enabled: root.controller.sessions.length > 1 && !root.controller.busy
            Accessible.name: "Select session"
            text: "SESSION  |  " + root.controller.sessionLabel.toUpperCase()
            normalColor: Theme.Palette.primary
            onClicked: root.controller.nextSession()
        }
    }

    Row {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: 50 * root.scaleFactor
        anchors.bottomMargin: 50 * root.scaleFactor + root.keyboardInset
        spacing: 25 * root.scaleFactor

        TextButton {
            width: 120 * root.scaleFactor
            height: 40 * root.scaleFactor
            Accessible.name: "Keyboard"
            text: "KEYBOARD"
            onClicked: {
                if (!root.controller.keyboardVisible || root.controller.keyboardHost !== root)
                    password.forceActiveFocus()
                root.controller.toggleKeyboard(root)
            }
        }
        TextButton {
            width: 100 * root.scaleFactor
            height: 40 * root.scaleFactor
            Accessible.name: "Reboot"
            text: "REBOOT"
            onClicked: root.controller.requestReboot()
        }
        TextButton {
            width: 120 * root.scaleFactor
            height: 40 * root.scaleFactor
            Accessible.name: "Shutdown"
            text: "SHUTDOWN"
            hoverColor: Theme.Palette.error
            onClicked: root.controller.requestShutdown()
        }
    }

}
