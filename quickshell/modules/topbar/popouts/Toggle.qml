pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as Controls
import qs.icewine.theme as Theme

Controls.Switch {
    id: root

    focusPolicy: Qt.StrongFocus
    implicitHeight: 34
    font.family: "JetBrainsMono Nerd Font"
    font.pixelSize: 11

    Keys.onReturnPressed: root.click()
    Keys.onEnterPressed: root.click()

    indicator: Rectangle {
        x: root.width - width
        anchors.verticalCenter: parent.verticalCenter
        implicitWidth: 34
        implicitHeight: 18
        radius: height / 2
        color: root.checked ? Theme.Palette.primary : Theme.Palette.surface
        border.width: root.activeFocus ? 1 : 0
        border.color: Theme.Palette.foreground

        Rectangle {
            x: root.checked ? parent.width - width - 3 : 3
            anchors.verticalCenter: parent.verticalCenter
            width: 12
            height: 12
            radius: 6
            color: root.checked ? Theme.Palette.backgroundDark : Theme.Palette.muted

            Behavior on x {
                NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
            }
        }

        Behavior on color {
            ColorAnimation { duration: 120 }
        }
    }

    contentItem: Text {
        rightPadding: root.indicator.width + 10
        text: root.text
        color: root.enabled ? Theme.Palette.foreground : Theme.Palette.muted
        font: root.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
