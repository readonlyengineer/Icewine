pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import "../../notifications" as NotificationParts
import qs.theme as Theme

Item {
    id: root

    required property var compositor
    required property var notificationService
    readonly property Item initialFocus: dnd
    signal sourceRequested(string address)

    Item {
        id: header

        anchors {
            top: parent.top
            left: parent.left
            right: parent.right
            margins: 12
        }
        height: 34

        Text {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            text: root.notificationService.count > 0
                ? "Notifications  " + root.notificationService.count : "Notifications"
            color: Theme.Palette.secondary
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 15
            font.bold: true
        }

        ActionButton {
            anchors.right: parent.right
            anchors.rightMargin: 30
            width: 82
            height: 30
            visible: root.notificationService.count > 0
            text: "Clear all"
            onClicked: root.notificationService.dismissAll()
        }
    }

    Toggle {
        id: dnd
        anchors {
            top: header.bottom
            left: parent.left
            right: parent.right
            leftMargin: 12
            rightMargin: 12
        }
        text: "Do Not Distrub"
        checked: root.notificationService.doNotDisturb
        onToggled: root.notificationService.doNotDisturb = checked
    }

    ListView {
        id: list

        anchors {
            top: dnd.bottom
            left: parent.left
            right: parent.right
            bottom: parent.bottom
            topMargin: 4
            leftMargin: 12
            rightMargin: 12
            bottomMargin: 12
        }
        spacing: 8
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        model: ScriptModel {
            values: root.notificationService.items
        }

        delegate: NotificationParts.NotificationCard {
            required property var modelData

            width: ListView.view.width
            notification: modelData
            compositor: root.compositor
            onDismissRequested: modelData.dismiss()
            onSourceRequested: address => {
                modelData.dismiss()
                root.sourceRequested(address)
            }
        }

        add: Transition {
            NumberAnimation {
                properties: "opacity,scale"
                from: 0
                duration: 180
                easing.type: Easing.OutCubic
            }
        }

        remove: Transition {
            NumberAnimation {
                properties: "opacity,scale"
                to: 0
                duration: 140
                easing.type: Easing.InCubic
            }
        }

        displaced: Transition {
            NumberAnimation {
                property: "y"
                duration: 180
                easing.type: Easing.OutCubic
            }
        }
    }

    Text {
        anchors.centerIn: list
        visible: root.notificationService.count === 0
        text: "󰂜\nAll caught up"
        color: Theme.Palette.muted
        font.family: "JetBrainsMono Nerd Font"
        font.pixelSize: 12
        horizontalAlignment: Text.AlignHCenter
        lineHeight: 1.6
    }
}
