import QtQuick
import qs.theme as Theme

Item {
    id: root

    required property date now

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight

    Text {
        id: label

        anchors.centerIn: parent
        text: Qt.formatDateTime(root.now, "ddd d  HH:mm")
        color: Theme.Palette.tertiary
        font.family: "JetBrainsMono Nerd Font"
        font.pixelSize: 14
        font.bold: true
    }
}
