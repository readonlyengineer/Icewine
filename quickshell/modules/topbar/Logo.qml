pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Widgets
import qs.icewine.theme as Theme

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

    IconImage {
        anchors.centerIn: parent
        implicitSize: 17
        source: Quickshell.iconPath(Quickshell.env("ICEWINE_DISTRO_LOGO") || "distributor-logo", "computer")
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
