pragma ComponentBehavior: Bound

import QtQuick
import Quickshell

Rectangle {
    id: root

    required property var session

    color: "#171a21"

    Image {
        anchors.fill: parent
        source: "file://" + Quickshell.env("HOME") + "/.local/share/wallpapers/current_blurr.jpg"
        fillMode: Image.PreserveAspectCrop
    }

    Rectangle {
        anchors.fill: parent
        color: "#b8171a21"
    }

    Column {
        anchors.centerIn: parent
        width: Math.min(parent.width - 48, 520)
        spacing: 28

        Text {
            id: clock
            property var now: new Date()

            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: now.toLocaleTimeString(Qt.locale(), "HH:mm")
            color: "#c7d5e0"
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 72
            font.bold: true

            Timer {
                running: true
                repeat: true
                interval: 1000
                onTriggered: clock.now = new Date()
            }
        }

        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: clock.now.toLocaleDateString(Qt.locale(), "dddd, d MMMM yyyy")
            color: "#8f98a0"
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 18
        }

        Column {
            width: parent.width
            spacing: 14
            visible: root.session.authenticationRequired

            Rectangle {
                width: parent.width
                height: 58
                radius: 18
                color: "#df1b2838"
                border.width: password.activeFocus ? 2 : 1
                border.color: password.activeFocus ? "#1a9fff" : "#557b9bbd"

                TextInput {
                    id: password
                    anchors {
                        fill: parent
                        leftMargin: 20
                        rightMargin: 20
                    }
                    verticalAlignment: TextInput.AlignVCenter
                    focus: root.session.authenticationRequired
                    enabled: !root.session.authenticating
                    echoMode: TextInput.Password
                    inputMethodHints: Qt.ImhSensitiveData
                    color: "#c7d5e0"
                    selectionColor: "#1a9fff"
                    selectedTextColor: "#171a21"
                    font.family: "JetBrainsMono Nerd Font"
                    font.pixelSize: 18
                    onTextChanged: root.session.password = text
                    onAccepted: root.session.submit()

                    Connections {
                        target: root.session
                        function onPasswordChanged() {
                            if (password.text !== root.session.password)
                                password.text = root.session.password
                        }
                    }
                }
            }

            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: root.session.failed ? "Incorrect password" : "Enter password to unlock"
                color: root.session.failed ? "#ff8b8b" : "#8f98a0"
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 15
            }
        }

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 180
            height: 54
            radius: 18
            visible: !root.session.authenticationRequired
            color: touch.pressed ? "#66c0f4" : "#1a9fff"

            Text {
                anchors.centerIn: parent
                text: "Unlock"
                color: "#171a21"
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 17
                font.bold: true
            }

            MouseArea {
                id: touch
                anchors.fill: parent
                onClicked: root.session.releaseLock(true)
            }
        }
    }
}
