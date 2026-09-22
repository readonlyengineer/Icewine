pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.theme as Theme

Variants {
    model: Quickshell.screens

    PanelWindow {
        required property var modelData
        screen: modelData
        color: Theme.Palette.background

        anchors {
            top: true
            bottom: true
            left: true
            right: true
        }

        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "quickshell:wallpaper"
        WlrLayershell.layer: WlrLayer.Background
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        mask: Region {}

        Image {
            anchors.fill: parent
            source: "file://" + Quickshell.env("HOME") + "/.local/share/wallpapers/current.jpg"
            fillMode: Image.PreserveAspectCrop
        }
    }
}
