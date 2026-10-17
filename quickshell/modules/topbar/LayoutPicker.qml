pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "popouts" as Popouts
import "Layouts.js" as Layouts
import qs.icewine.theme as Theme

ColumnLayout {
    id: root
    required property var compositor
    readonly property var initialFocus: autofullscreen
    readonly property bool available: compositor.layoutAvailable && !compositor.layoutPending
    implicitHeight: 202
    spacing: 8

    Text {
        Layout.fillWidth: true
        Layout.margins: 12
        text: "Workspace " + root.compositor.layoutWorkspaceId
        color: Theme.Palette.foreground
        font.pixelSize: 13
        font.bold: true
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 12
        Layout.rightMargin: 12
        spacing: 6
        Repeater {
            model: ["scrolling", "dwindle", "master", "monocle"]
            Popouts.ActionButton {
                id: choice
                required property string modelData
                Layout.fillWidth: true
                implicitWidth: 80
                implicitHeight: 86
                enabled: root.available
                text: Layouts.label(modelData)
                Accessible.name: text + " layout"
                onClicked: root.compositor.selectLayout(modelData)
                contentItem: Column {
                    spacing: 8
                    Item {
                        width: parent.width
                        height: 42
                        Repeater {
                            model: choice.modelData === "scrolling" ? [[0,0,0.3,1],[0.35,0,0.3,1],[0.7,0,0.3,1]]
                                : choice.modelData === "dwindle" ? [[0,0,0.48,1],[0.53,0,0.47,0.48],[0.53,0.53,0.22,0.47],[0.8,0.53,0.2,0.47]]
                                : choice.modelData === "master" ? [[0,0,0.65,1],[0.7,0,0.3,0.48],[0.7,0.53,0.3,0.47]]
                                : [[0,0,0.8,0.8],[0.1,0.1,0.8,0.8],[0.2,0.2,0.8,0.8]]
                            Rectangle {
                                required property var modelData
                                x: 4 + modelData[0] * (parent.width - 8)
                                y: modelData[1] * parent.height
                                width: modelData[2] * (parent.width - 8)
                                height: modelData[3] * parent.height
                                radius: 3
                                color: Theme.Palette.surface
                                border.width: 1
                                border.color: root.compositor.layoutStatus?.effective === choice.modelData
                                    ? Theme.Palette.primary : Theme.Palette.muted
                            }
                        }
                    }
                    Text {
                        width: parent.width
                        text: choice.text
                        horizontalAlignment: Text.AlignHCenter
                        color: choice.enabled ? Theme.Palette.foreground : Theme.Palette.muted
                        font.pixelSize: 11
                    }
                }
            }
        }
    }
    Popouts.Toggle {
        id: autofullscreen
        Layout.fillWidth: true
        Layout.leftMargin: 12
        Layout.rightMargin: 12
        enabled: root.available
        text: "Autofullscreen"
        Accessible.name: text
        checked: root.compositor.layoutStatus?.autofullscreen === true
        onToggled: root.compositor.selectAutofullscreen(checked)
    }
    Text {
        Layout.fillWidth: true
        Layout.leftMargin: 12
        Layout.rightMargin: 12
        Layout.bottomMargin: 12
        visible: text.length > 0
        text: root.compositor.layoutError || root.compositor.layoutUnavailable
            || (!root.compositor.layoutAvailable ? "Hyprland unavailable" : "")
        color: root.compositor.layoutError || root.compositor.layoutUnavailable ? Theme.Palette.error : Theme.Palette.muted
        font.pixelSize: 11
        wrapMode: Text.Wrap
        maximumLineCount: 3
        elide: Text.ElideRight
    }
}
