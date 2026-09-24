pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import qs.theme as Theme

Rectangle {
    id: root

    required property var compositor
    required property var screen

    readonly property var monitor: compositor.monitorFor(screen)
    readonly property int activeId: monitor?.activeWorkspace?.id ?? 1
    readonly property var workspaceIds: compositor.workspaceIdsForMonitor(monitor)

    implicitWidth: workspaceRow.implicitWidth + 9
    implicitHeight: 29
    radius: height / 2
    color: Theme.Palette.alpha(Theme.Palette.surface, 0.92)
    border.color: Theme.Palette.alpha(Theme.Palette.secondary, 0.45)
    border.width: 1

    Row {
        id: workspaceRow

        anchors.centerIn: parent
        spacing: 2

        Repeater {
            model: root.workspaceIds

            WorkspaceButton {}
        }
    }

    component WorkspaceButton: Rectangle {
        id: workspaceButton

        required property int index

        required property int modelData

        readonly property int workspaceId: modelData
        readonly property var toplevels: root.compositor.toplevelsForWorkspace(workspaceId)
        readonly property bool active: root.activeId === workspaceId
        readonly property bool occupied: toplevels.length > 0

        implicitWidth: contents.implicitWidth + 9
        implicitHeight: 22
        radius: height / 2
        color: active ? Theme.Palette.primary : hover.hovered ? Theme.Palette.selection : "transparent"

        Row {
            id: contents

            anchors.centerIn: parent
            spacing: 3

            Text {
                text: workspaceButton.workspaceId
                color: workspaceButton.active ? Theme.Palette.backgroundDark
                    : workspaceButton.occupied ? Theme.Palette.foreground : Theme.Palette.muted
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 11
                font.bold: true
            }

            Repeater {
                model: ScriptModel {
                    values: workspaceButton.toplevels.slice(0, 5)
                }

                ApplicationIcon {
                    anchors.verticalCenter: parent.verticalCenter
                    workspaceActive: workspaceButton.active
                }
            }
        }

        HoverHandler {
            id: hover
            cursorShape: Qt.PointingHandCursor
        }

        TapHandler {
            onTapped: root.compositor.activateWorkspace(workspaceButton.workspaceId)
        }

        Behavior on implicitWidth {
            NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
        }

        Behavior on color {
            ColorAnimation { duration: 120 }
        }
    }

    component ApplicationIcon: Item {
        id: applicationIcon

        required property var modelData
        required property bool workspaceActive

        readonly property string appId: String(
            modelData.wayland?.appId ?? modelData.lastIpcObject?.class ?? "")
        readonly property string source: Quickshell.iconPath(
            DesktopEntries.heuristicLookup(appId)?.icon ?? "", true)
        readonly property bool focused: modelData.activated ?? false

        implicitWidth: 12
        implicitHeight: 12

        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            radius: 4
            color: applicationIcon.focused ? Theme.Palette.secondary : "transparent"
        }

        Image {
            id: appImage

            anchors.fill: parent
            visible: status === Image.Ready
            source: applicationIcon.source
            sourceSize.width: width
            sourceSize.height: height
            fillMode: Image.PreserveAspectFit
        }

        Text {
            anchors.centerIn: parent
            visible: applicationIcon.source === "" || appImage.status === Image.Error
            text: ""
            color: applicationIcon.workspaceActive ? Theme.Palette.backgroundDark : Theme.Palette.foregroundDark
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 9
        }
    }
}
