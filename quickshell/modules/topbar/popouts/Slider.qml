pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as Controls
import qs.theme as Theme

Controls.Slider {
    id: root

    focusPolicy: Qt.StrongFocus
    from: 0
    to: 1
    stepSize: 0.01
    implicitHeight: 24

    background: Rectangle {
        x: root.leftPadding
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: root.availableWidth
        height: 4
        radius: 2
        color: Theme.Palette.surface

        Rectangle {
            width: root.visualPosition * parent.width
            height: parent.height
            radius: parent.radius
            color: Theme.Palette.primary
        }
    }

    handle: Rectangle {
        x: root.leftPadding + root.visualPosition * (root.availableWidth - width)
        y: root.topPadding + root.availableHeight / 2 - height / 2
        implicitWidth: 14
        implicitHeight: 14
        radius: 7
        color: root.pressed ? Theme.Palette.primaryDark : Theme.Palette.primary
        border.width: root.activeFocus ? 1 : 0
        border.color: Theme.Palette.foreground
    }
}
