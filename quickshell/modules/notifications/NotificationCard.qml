pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as Controls
import Quickshell
import Quickshell.Services.Notifications
import "Model.js" as NotificationModel
import qs.theme as Theme

Rectangle {
    id: root

    required property var notification
    required property var compositor
    readonly property var desktopEntry: notification?.desktopEntry
        ? DesktopEntries.byId(notification.desktopEntry) : null
    readonly property string sourceWindowAddress: NotificationModel.sourceWindowAddress(
        notification, compositor.toplevels, desktopEntry)
    readonly property color accent: notification?.urgency === NotificationUrgency.Critical
        ? Theme.Palette.error : notification?.urgency === NotificationUrgency.Normal
            ? Theme.Palette.secondary : Theme.Palette.muted
    readonly property string iconSource: notification?.appIcon === "battery-low"
        ? Quickshell.iconPath(notification.appIcon, true)
        : notification?.image || Quickshell.iconPath(notification?.appIcon ?? "", true)

    signal dismissRequested()
    signal sourceRequested(string address)

    implicitHeight: Math.max(58, details.implicitHeight + 20)
    radius: 10
    color: Theme.Palette.surface
    border.width: 1
    border.color: Theme.Palette.alpha(accent, 0.55)

    MouseArea {
        anchors.fill: parent
        onClicked: root.dismissRequested()
    }

    Rectangle {
        width: 3
        anchors {
            top: parent.top
            bottom: parent.bottom
            left: parent.left
            topMargin: 8
            bottomMargin: 8
        }
        radius: width / 2
        color: root.accent
    }

    Rectangle {
        id: iconFrame

        anchors {
            top: parent.top
            left: parent.left
            topMargin: 10
            leftMargin: 11
        }
        width: 36
        height: 36
        radius: 9
        color: Theme.Palette.alpha(root.accent, 0.18)

        Image {
            id: appIcon

            anchors.fill: parent
            anchors.margins: 6
            source: root.iconSource
            sourceSize.width: width
            sourceSize.height: height
            fillMode: Image.PreserveAspectFit
        }

        Text {
            anchors.centerIn: parent
            visible: appIcon.status === Image.Error || root.iconSource.length === 0
            text: root.notification?.appIcon === "battery-low" ? "" : "󰂚"
            color: root.accent
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 15
        }
    }

    Controls.Button {
        id: dismissButton

        anchors { top: parent.top; right: parent.right; margins: 8 }
        width: 36
        height: 36
        focusPolicy: Qt.StrongFocus
        Accessible.role: Accessible.Button
        Accessible.name: "Dismiss"
        Controls.ToolTip.visible: hovered
        Controls.ToolTip.text: "Dismiss"
        onClicked: root.dismissRequested()

        background: Rectangle {
            radius: 9
            color: dismissButton.down ? Theme.Palette.primaryDark
                : dismissButton.hovered ? Theme.Palette.selection : "transparent"
            border.width: dismissButton.activeFocus ? 1 : 0
            border.color: Theme.Palette.primary
        }

        contentItem: Text {
            text: "×"
            color: Theme.Palette.foreground
            font.pixelSize: 20
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    Controls.Button {
        id: sourceButton

        anchors {
            top: parent.top
            right: dismissButton.left
            topMargin: 8
            rightMargin: 4
        }
        visible: root.sourceWindowAddress !== ""
        width: 36
        height: 36
        focusPolicy: Qt.StrongFocus
        Accessible.role: Accessible.Button
        Accessible.name: "Go to source window"
        Controls.ToolTip.visible: hovered
        Controls.ToolTip.text: "Go to source window"
        onClicked: {
            const address = root.sourceWindowAddress
            if (address)
                root.sourceRequested(address)
        }

        background: Rectangle {
            radius: 9
            color: sourceButton.down ? Theme.Palette.primaryDark
                : sourceButton.hovered ? Theme.Palette.selection : "transparent"
            border.width: sourceButton.activeFocus ? 1 : 0
            border.color: Theme.Palette.primary
        }

        contentItem: Text {
            text: "󰅂"
            color: Theme.Palette.foreground
            font.pixelSize: 18
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    Column {
        id: details

        anchors {
            top: parent.top
            left: iconFrame.right
            right: parent.right
            topMargin: 9
            leftMargin: 10
            rightMargin: sourceButton.visible ? 92 : 52
        }
        spacing: 2

        Text {
            width: parent.width
            visible: text.length > 0
            text: root.notification?.appName ?? ""
            color: root.accent
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 9
            elide: Text.ElideRight
        }

        Text {
            width: parent.width
            text: root.notification?.summary || "Notification"
            color: Theme.Palette.foreground
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 11
            font.bold: true
            elide: Text.ElideRight
        }

        Text {
            width: parent.width
            visible: text.length > 0
            text: root.notification?.body ?? ""
            textFormat: Text.PlainText
            color: Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 10
            wrapMode: Text.Wrap
            maximumLineCount: 4
            elide: Text.ElideRight
        }

        Flow {
            id: actions

            width: parent.width
            height: visible ? childrenRect.height : 0
            visible: (root.notification?.actions.length ?? 0) > 0
            spacing: 5

            Repeater {
                model: root.notification?.actions ?? []

                Rectangle {
                    id: action

                    required property var modelData

                    width: Math.min(actions.width, actionText.implicitWidth + 16)
                    height: 26
                    radius: 8
                    color: actionHover.hovered ? Theme.Palette.selection
                        : Theme.Palette.backgroundDark

                    Text {
                        id: actionText

                        anchors.centerIn: parent
                        width: Math.min(implicitWidth, parent.width - 16)
                        text: action.modelData.text
                        color: Theme.Palette.foreground
                        font.family: "JetBrainsMono Nerd Font"
                        font.pixelSize: 9
                        elide: Text.ElideRight
                    }

                    HoverHandler { id: actionHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler {
                        gesturePolicy: TapHandler.WithinBounds
                        onTapped: action.modelData.invoke()
                    }
                }
            }
        }
    }
}
