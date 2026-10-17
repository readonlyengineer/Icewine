pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.icewine.theme as Theme

import "Wallpaper.js" as Wallpaper

Scope {
    id: root

    readonly property string dataHome: Quickshell.env("XDG_DATA_HOME")
        || (Quickshell.env("HOME") + "/.local/share")
    property string revision: "initial"
    property bool selectionAvailable: true
    readonly property url sourceUrl: Wallpaper.source(dataHome, selectionAvailable, revision)

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
            // Ponytail: Hyprland 0.56 misses layers on output moves. Track the final
            // origin across coalesced polish; four anchors keep size 0x0. Remove after native repair.
            implicitWidth: modelData.x
            implicitHeight: modelData.y
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
                source: root.sourceUrl
                fillMode: Image.PreserveAspectCrop
                onStatusChanged: {
                    if (status === Image.Error && root.selectionAvailable)
                        Qt.callLater(() => {
                            if (status === Image.Error) root.selectionAvailable = false
                        })
                }
            }
        }
    }
}
