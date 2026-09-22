pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as Controls
import qs.theme as Theme

Controls.Button {
    id: root

    property int activationKey: 0
    onActiveFocusChanged: if (!activeFocus) activationKey = 0

    focusPolicy: Qt.StrongFocus
    implicitHeight: 34
    font.family: "JetBrainsMono Nerd Font"
    font.pixelSize: 11

    Keys.onReturnPressed: event => { if (!event.isAutoRepeat) root.activationKey = event.key }
    Keys.onEnterPressed: event => { if (!event.isAutoRepeat) root.activationKey = event.key }
    Keys.onReleased: event => {
        if (event.isAutoRepeat || event.key !== root.activationKey)
            return
        event.accepted = true
        root.activationKey = 0
        root.click()
    }

    background: Rectangle {
        radius: 9
        color: root.down ? Theme.Palette.primaryDark
            : root.hovered ? Theme.Palette.selection : Theme.Palette.surface
        border.width: root.activeFocus ? 1 : 0
        border.color: Theme.Palette.primary

        Behavior on color {
            ColorAnimation { duration: 100 }
        }
    }

    contentItem: Text {
        text: root.text
        color: root.enabled ? Theme.Palette.foreground : Theme.Palette.muted
        font: root.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
