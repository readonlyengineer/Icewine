pragma ComponentBehavior: Bound

import QtQuick
import qs.icewine.theme as Theme

Rectangle {
    id: root

    required property var player
    readonly property alias hovered: hover.hovered

    signal popoutActivated()
    signal mediaRequested()

    visible: player !== null
    implicitWidth: visible ? Math.min(content.implicitWidth + 12, 190) : 0
    implicitHeight: 29
    radius: height / 2
    color: hover.hovered ? Theme.Palette.selection
        : Theme.Palette.alpha(Theme.Palette.surface, 0.92)
    border.width: 1
    border.color: Theme.Palette.alpha(Theme.Palette.primary, 0.45)
    clip: true

    Row {
        id: content

        anchors {
            left: parent.left
            right: parent.right
            verticalCenter: parent.verticalCenter
            leftMargin: 7
            rightMargin: 7
        }
        spacing: 5

        Item {
            width: 24
            height: root.height
            Text {
                anchors.centerIn: parent
                text: root.player?.isPlaying ? "" : ""
                color: Theme.Palette.primary
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 10
            }
            TapHandler { onTapped: root.popoutActivated() }
        }

        Text {
            width: Math.min(implicitWidth, 145)
            height: root.height
            verticalAlignment: Text.AlignVCenter
            text: root.player?.trackTitle || root.player?.identity || "Unknown track"
            color: Theme.Palette.foreground
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 10
            elide: Text.ElideRight

            TapHandler {
                enabled: root.player?.canRaise ?? false
                onTapped: root.mediaRequested()
            }
        }
    }

    HoverHandler {
        id: hover

        cursorShape: Qt.PointingHandCursor
    }

    Behavior on implicitWidth {
        NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
    }

    Behavior on color {
        ColorAnimation { duration: 120 }
    }
}
