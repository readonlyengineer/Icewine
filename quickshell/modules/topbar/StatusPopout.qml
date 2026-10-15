pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
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

    function revealFocus() {
        const item = root.Window.window?.activeFocusItem
        let page = item
        while (page && page !== pageLoader.item) page = page.parent
        if (!root.visible || !root.enabled || !page || item === page)
            return
        for (let scroll = item.parent; scroll; scroll = scroll.parent) {
            if (scroll instanceof Flickable && scroll.height > 0) {
                const top = item.mapToItem(scroll.contentItem, 0, 0).y
                const bottom = top + item.height
                const target = top < scroll.contentY ? top
                    : bottom > scroll.contentY + scroll.height ? bottom - scroll.height : scroll.contentY
                scroll.contentY = Math.max(scroll.originY, Math.min(target,
                    scroll.originY + Math.max(0, scroll.contentHeight - scroll.height)))
            }
            if (scroll === pageLoader.item) break
        }
    }

    onHeightChanged: Qt.callLater(root.revealFocus)
    Connections {
        target: root.Window.window
        function onActiveFocusItemChanged() { Qt.callLater(root.revealFocus) }
    }

    function capture(mode) {
        const page = pageLoader.item
        if (!page) return
        const command = ["hyprshot", "--freeze", "--mode", mode]
        if (mode === "output" && Quickshell.screens.length === 1)
            command.push("--mode", Quickshell.screens[0].name)
        if (page.clipboardOnly) command.push("--clipboard-only")
        if (page.delayCapture)
            command.unshift("sh", "-c", 'sleep 3 && exec "$@"', "icewine-screenshot")
        instantHandoffRequested()
        // Hide the popout before Hyprshot freezes the selection surface.
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
        }
    }
    Component {
        id: audioPage
        Popouts.Audio {}
    }
    Component {
        id: networkPage
        Popouts.Network {
            metrics: root.metrics
        }
    }
    Component {
        id: bluetoothPage
        Popouts.Bluetooth {}
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
            onCaptureRequested: mode => root.capture(mode)
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
