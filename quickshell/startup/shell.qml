import QtQuick
import Quickshell
import Quickshell.Wayland
import "theme" as Theme

ShellRoot {
    Timer {
        interval: 30000
        running: true
        onTriggered: Qt.quit()
    }

    Variants {
        model: Quickshell.screens

        PanelWindow {
            required property var modelData
            screen: modelData
            color: Theme.Palette.background
            focusable: false
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            mask: Region {}

            anchors {
                top: true
                bottom: true
                left: true
                right: true
            }

            Column {
                anchors.centerIn: parent
                spacing: 28

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: ""
                    color: Theme.Palette.tertiary
                    font.family: "JetBrainsMono Nerd Font"
                    font.pixelSize: 96
                    font.bold: true
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: ""
                    color: Theme.Palette.primary
                    font.family: "JetBrainsMono Nerd Font"
                    font.pixelSize: 42

                    RotationAnimator on rotation {
                        from: 0
                        to: 360
                        duration: 900
                        loops: Animation.Infinite
                        running: true
                    }
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Starting Icewine"
                    color: Theme.Palette.foreground
                    font.family: "JetBrainsMono Nerd Font"
                    font.pixelSize: 20
                }
            }
        }
    }
}
