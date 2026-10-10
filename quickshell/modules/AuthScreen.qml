pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Effects
import "AuthModel.js" as AuthModel

Item {
    id: root

    required property var controller
    required property var palette
    property url backdropSource: ""
    signal backdropFailed()
    readonly property real scaleFactor: AuthModel.scaleFactor(width, height)
    readonly property real keyboardInset: AuthModel.keyboardInset(controller.keyboardHost,
        root, controller.keyboardVisible, controller.keyboardHeight)

    function revealItem(item) {
        const top = item.mapToItem(content, 0, 0).y
        const bottom = top + item.height + 16
        if (top < scroll.contentY || bottom > scroll.contentY + scroll.height)
            scroll.contentY = Math.max(0, Math.min(bottom - scroll.height,
                scroll.contentHeight - scroll.height))
    }
    function revealPassword() {
        if (password.activeFocus) revealItem(statusText)
    }
    onKeyboardInsetChanged: Qt.callLater(revealPassword)

    Item {
        id: backdrop
        anchors.fill: parent
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0; color: root.palette.backgroundDark }
                GradientStop { position: 0.55; color: root.palette.surface }
                GradientStop { position: 1; color: root.palette.background }
            }
        }
        Image {
            objectName: "authBackdrop"
            anchors.fill: parent
            source: root.backdropSource
            cache: false
            fillMode: Image.PreserveAspectCrop
            onStatusChanged: if (status === Image.Error) root.backdropFailed()
        }
    }

    Item {
        id: panel
        objectName: "authPanel"
        width: Math.min(root.width, Math.max(360 * root.scaleFactor, root.width / 3))
        height: root.height
        clip: true

        ShaderEffectSource {
            id: frostSource
            sourceItem: backdrop
            sourceRect: Qt.rect(0, 0, panel.width, panel.height)
            width: panel.width
            height: panel.height
            visible: false
        }
        MultiEffect {
            anchors.fill: parent
            source: frostSource
            blurEnabled: true
            blur: 1
            blurMax: 48
            autoPaddingEnabled: false
        }
        Rectangle {
            anchors.fill: parent
            color: root.palette.background
            opacity: 0.86
        }
        Rectangle {
            anchors.right: parent.right
            height: parent.height
            width: 1
            color: root.palette.border
            opacity: 0.4
        }

        component TextButton: Controls.Button {
            id: button
            property color normalColor: root.palette.foreground
            property color hoverColor: root.palette.primary
            property real labelSize: 14 * root.scaleFactor
            implicitHeight: Math.max(44, 44 * root.scaleFactor)
            focusPolicy: Qt.StrongFocus
            leftPadding: 0
            rightPadding: 0
            background: Rectangle {
                color: "transparent"
                border.width: button.activeFocus ? 1 : 0
                border.color: root.palette.primary
                radius: 4
            }
            contentItem: Text {
                text: button.text
                elide: Text.ElideRight
                verticalAlignment: Text.AlignVCenter
                color: button.down || button.hovered || button.activeFocus
                    ? button.hoverColor : button.normalColor
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: Math.max(12, button.labelSize)
            }
            onActiveFocusChanged: if (activeFocus && parent !== footer)
                Qt.callLater(() => root.revealItem(button))
            Keys.onReturnPressed: click()
            Keys.onEnterPressed: click()
        }

        Controls.ScrollView {
            id: body
            objectName: "authBody"
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: footer.top
            anchors.margins: 32 * root.scaleFactor
            clip: true
            contentWidth: availableWidth
            // Keep the form reachable when the keyboard leaves little vertical space.
            contentItem: Flickable {
                id: scroll
                clip: true
                contentWidth: body.availableWidth
                contentHeight: content.height
                boundsBehavior: Flickable.StopAtBounds
                Column {
                    id: content
                    width: scroll.width
                    spacing: 14 * root.scaleFactor

                    Item { width: 1; height: Math.max(0, root.height * 0.12 - 32 * root.scaleFactor) }
                    Text {
                        id: clock
                        property date now: new Date()
                        text: Qt.formatTime(now, "HH:mm")
                        color: root.palette.foreground
                        font.family: "JetBrainsMono Nerd Font"
                        font.pixelSize: 64 * root.scaleFactor
                        font.weight: Font.Light
                        Timer {
                            interval: 1000
                            running: true
                            repeat: true
                            onTriggered: clock.now = new Date()
                        }
                    }
                    Text {
                        width: parent.width
                        text: Qt.formatDate(clock.now, "dddd, MMMM d")
                        color: root.palette.foregroundDark
                        font.family: "JetBrainsMono Nerd Font"
                        font.pixelSize: Math.max(12, 14 * root.scaleFactor)
                        wrapMode: Text.WordWrap
                    }
                    Item { width: 1; height: 24 * root.scaleFactor }
                    TextButton {
                        width: parent.width
                        visible: root.controller.userCount > 0
                        enabled: root.controller.userCount > 1 && !root.controller.busy
                        Accessible.name: "Select user"
                        text: root.controller.userLabel
                        labelSize: 18 * root.scaleFactor
                        onClicked: root.controller.nextUser()
                    }
                    Row {
                        width: parent.width
                        spacing: 8 * root.scaleFactor
                        visible: root.controller.authenticationRequired
                        Controls.TextField {
                            id: password
                            objectName: "authPassword"
                            width: parent.width - submit.width - parent.spacing
                            height: Math.max(44, 48 * root.scaleFactor)
                            enabled: !root.controller.busy
                            focus: true
                            KeyNavigation.tab: submit
                            echoMode: root.controller.secretInput ? TextInput.Password : TextInput.Normal
                            inputMethodHints: root.controller.secretInput
                                ? Qt.ImhSensitiveData | Qt.ImhNoPredictiveText : Qt.ImhNone
                            placeholderText: root.controller.prompt || "Password"
                            placeholderTextColor: root.palette.foregroundDark
                            color: root.palette.foreground
                            selectionColor: root.palette.primary
                            selectedTextColor: root.palette.backgroundDark
                            font.family: "JetBrainsMono Nerd Font"
                            font.pixelSize: 16 * root.scaleFactor
                            Accessible.name: root.controller.prompt || "Password"
                            background: Rectangle {
                                color: root.palette.backgroundDark
                                radius: 4
                                border.width: password.activeFocus ? 2 : 1
                                border.color: root.controller.failed ? root.palette.error
                                    : password.activeFocus ? root.palette.primary : root.palette.border
                            }
                            onActiveFocusChanged: if (activeFocus) Qt.callLater(root.revealPassword)
                            onTextChanged: {
                                if (root.controller.password !== text)
                                    root.controller.password = text
                            }
                            onAccepted: root.controller.submit()
                            Connections {
                                target: root.controller
                                function onPasswordChanged() {
                                    if (password.text !== root.controller.password)
                                        password.text = root.controller.password
                                }
                                function onBusyChanged() {
                                    if (!root.controller.busy) password.forceActiveFocus()
                                }
                            }
                        }
                        TextButton {
                            id: submit
                            KeyNavigation.backtab: password
                            width: 44 * root.scaleFactor
                            height: password.height
                            enabled: !root.controller.busy
                            Accessible.name: "Continue"
                            text: "→"
                            labelSize: 24 * root.scaleFactor
                            onClicked: root.controller.submit()
                        }
                    }
                    Text {
                        id: statusText
                        objectName: "authStatus"
                        width: parent.width
                        text: root.controller.busy ? (root.controller.message || "Authenticating…")
                            : root.controller.message
                        color: root.controller.failed ? root.palette.error : root.palette.foregroundDark
                        font.family: "JetBrainsMono Nerd Font"
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                        Accessible.role: Accessible.StaticText
                        Accessible.name: text
                    }
                    TextButton {
                        width: parent.width
                        visible: !root.controller.authenticationRequired
                        enabled: !root.controller.busy
                        Accessible.name: "Unlock"
                        text: "Unlock"
                        onClicked: root.controller.submit()
                    }
                    Row {
                        spacing: 24 * root.scaleFactor
                        TextButton {
                            width: 80 * root.scaleFactor
                            visible: root.controller.canReboot
                            Accessible.name: "Reboot"
                            text: "Reboot"
                            onClicked: root.controller.requestReboot()
                        }
                        TextButton {
                            width: 96 * root.scaleFactor
                            visible: root.controller.canShutdown
                            Accessible.name: "Shutdown"
                            text: "Shutdown"
                            hoverColor: root.palette.error
                            onClicked: root.controller.requestShutdown()
                        }
                    }
                }
            }
        }
        Column {
            id: footer
            objectName: "authFooter"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.leftMargin: 32 * root.scaleFactor
            anchors.rightMargin: 32 * root.scaleFactor
            anchors.bottomMargin: 24 * root.scaleFactor + root.keyboardInset
            TextButton {
                width: parent.width
                Accessible.name: "Keyboard"
                text: root.controller.keyboardVisible && root.controller.keyboardHost === root
                    ? "Hide keyboard" : "Keyboard"
                onClicked: {
                    password.forceActiveFocus()
                    root.controller.toggleKeyboard(root)
                }
            }
            TextButton {
                width: parent.width
                visible: root.controller.sessionCount > 0
                enabled: root.controller.sessionCount > 1 && !root.controller.busy
                Accessible.name: "Select session"
                text: "Session · " + root.controller.sessionLabel
                onClicked: root.controller.nextSession()
            }
        }
    }
}
