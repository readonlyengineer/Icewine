import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "theme" as Theme
import "StartupSplash.js" as Startup

ShellRoot {
    id: root

    readonly property bool steam: Quickshell.env("ICEWINE_SPLASH_MODE") === "steam"
    property bool delayed: false

    Process {
        command: ["xprop", "-root", "-spy", "GAMESCOPE_FOCUSED_APP_GFX"]
        running: root.steam
        stdout: SplitParser {
            onRead: line => {
                if (Startup.steamUiReady(line))
                    Qt.quit()
            }
        }
        // Presentation failure must not interfere with the primary Steam child.
        onExited: if (root.steam) Qt.quit()
    }

    Timer {
        interval: 45000
        running: root.steam
        onTriggered: root.delayed = true
    }

    Timer {
        interval: 120000
        running: root.steam
        onTriggered: Qt.quit()
    }

    Timer {
        interval: 30000
        running: !root.steam
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
                    text: root.delayed ? "" : ""
                    color: Theme.Palette.primary
                    font.family: "JetBrainsMono Nerd Font"
                    font.pixelSize: 42

                    RotationAnimator on rotation {
                        from: 0
                        to: 360
                        duration: 900
                        loops: Animation.Infinite
                        running: !root.delayed
                    }
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: root.delayed ? "Steam is taking longer than expected"
                        : root.steam ? "Starting Steam" : "Starting Icewine"
                    color: Theme.Palette.foreground
                    font.family: "JetBrainsMono Nerd Font"
                    font.pixelSize: 20
                }
            }
        }
    }
}
