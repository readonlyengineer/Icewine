pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.theme as Theme

import "Wallpaper.js" as Wallpaper

Scope {
    id: root

    readonly property string dataHome: Quickshell.env("XDG_DATA_HOME")
        || (Quickshell.env("HOME") + "/.local/share")
    property string revision: "initial"
    property bool selectionAvailable: true

    IpcHandler {
        target: "wallpaper"

        function refresh(newRevision: string): string {
            root.selectionAvailable = true
            root.revision = newRevision
            return "refreshed"
        }
    }

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
                cache: false
                source: Wallpaper.source(root.dataHome, root.selectionAvailable, root.revision)
                fillMode: Image.PreserveAspectCrop
                onStatusChanged: {
                    if (status === Image.Error && root.selectionAvailable)
                        root.selectionAvailable = false
                }
            }
        }
    }
}
