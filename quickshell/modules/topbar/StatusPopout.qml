pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import "popouts" as Popouts
import qs.icewine.theme as Theme

Widget {
    id: root

    required property var compositor
    required property var notificationService
    required property var session
    required property var player
    required property var powerState
    required property var metrics
    required property string monitorName

    MonitorBrightness {
        id: monitorBrightness
        monitorName: root.monitorName
        active: root.visible && root.currentPage === "battery"
    }
    property string currentPage: "audio"
    signal mediaRequested()
    signal instantHandoffRequested()

    function focusInitial() {
        root.forceActiveFocus(Qt.ShortcutFocusReason)
        pageLoader.item?.initialFocus?.forceActiveFocus(Qt.ShortcutFocusReason)
    }

    function launch(tool) {
        handoffRequested()
        Quickshell.execDetached(["uwsm", "app", "--", "icewine-terminal-exec", tool])
    }

    function capture(mode, target) {
        const page = pageLoader.item
        if (!page || (!page.saveClipboard && !page.savePictures)) return
        const command = ["icewine-screenshot", mode, target,
            page.delayed ? "3" : "0",
            page.saveClipboard ? "1" : "0",
            page.savePictures ? "1" : "0"]
        if (mode === "region")
            instantHandoffRequested()
        else
            handoffRequested()
        // The popout must be gone before grimblast freezes the selection surface.
        Qt.callLater(() => Quickshell.execDetached(command))
    }

    width: 380
    implicitHeight: Math.min(620, pageLoader.item?.implicitHeight ?? 0)

    Rectangle {
        anchors.fill: parent
        radius: 12
        color: Theme.Palette.backgroundDark

        Loader {
            id: pageLoader
            anchors.fill: parent
            active: root.visible
            sourceComponent: root.currentPage === "audio" ? audioPage
                : root.currentPage === "performance" ? performancePage
                : root.currentPage === "network" ? networkPage
                        : root.currentPage === "bluetooth" ? bluetoothPage
                        : root.currentPage === "battery" ? batteryPage
                            : root.currentPage === "screenshot" ? screenshotPage
                            : root.currentPage === "media" ? mediaPage : notificationsPage
        }
    }

    Component {
        id: performancePage
        Popouts.Performance {
            metrics: root.metrics
            onAdvancedRequested: tool => root.launch(tool)
        }
    }
    Component {
        id: audioPage
        Popouts.Audio { onAdvancedRequested: tool => root.launch(tool) }
    }
    Component {
        id: networkPage
        Popouts.Network {
            metrics: root.metrics
            onAdvancedRequested: tool => root.launch(tool)
        }
    }
    Component {
        id: bluetoothPage
        Popouts.Bluetooth { onAdvancedRequested: tool => root.launch(tool) }
    }
    Component {
        id: notificationsPage
        Popouts.Notifications {
            compositor: root.compositor
            notificationService: root.notificationService
            onSourceRequested: address => {
                root.handoffRequested()
                Qt.callLater(() => root.compositor.activateWindow(address))
            }
        }
    }
    Component {
        id: batteryPage
        Popouts.Battery {
            powerState: root.powerState
            session: root.session
            brightness: monitorBrightness
        }
    }
    Component {
        id: screenshotPage
        Popouts.Screenshot {
            compositor: root.compositor
            onCaptureRequested: (mode, target) => root.capture(mode, target)
        }
    }
    Component {
        id: mediaPage
        Popouts.Media {
            player: root.player
            onRaiseRequested: root.mediaRequested()
        }
    }
}
