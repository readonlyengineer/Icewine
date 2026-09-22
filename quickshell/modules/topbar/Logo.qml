pragma ComponentBehavior: Bound

import QtQuick
import qs.theme as Theme

Rectangle {
    id: root

    signal activated()
    readonly property alias hovered: hover.hovered
    property int backgroundCount: 0
    property bool backgroundAttention: false

    implicitWidth: 29
    implicitHeight: 29
    radius: height / 2
    color: hover.hovered ? Theme.Palette.selection : Theme.Palette.alpha(Theme.Palette.surface, 0.92)
    border.color: Theme.Palette.alpha(Theme.Palette.tertiary, 0.55)
    border.width: 1

    Text {
        anchors.centerIn: parent
        text: ""
        color: Theme.Palette.tertiary
        font.family: "JetBrainsMono Nerd Font"
        font.pixelSize: 17
        font.bold: true
    }

    Rectangle {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 3
        visible: root.backgroundCount > 0
        width: 6
        height: 6
        radius: 3
        color: root.backgroundAttention ? Theme.Palette.error : Theme.Palette.secondary
    }

    HoverHandler {
        id: hover
        cursorShape: Qt.PointingHandCursor
    }

    TapHandler {
        onTapped: root.activated()
    }

    Behavior on color {
        ColorAnimation { duration: 120 }
    }
}
