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
    readonly property Item currentItem: currentPage === "network" ? networkLoader.item : pageLoader.item
    signal mediaRequested()
    signal instantHandoffRequested()

    function focusInitial() {
        root.forceActiveFocus(Qt.ShortcutFocusReason)
        root.currentItem?.initialFocus?.forceActiveFocus(Qt.ShortcutFocusReason)
    }

    function revealFocus() {
        const item = root.Window.window?.activeFocusItem
        let page = item
        while (page && page !== root.currentItem) page = page.parent
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
            if (scroll === root.currentItem) break
        }
    }

    onHeightChanged: Qt.callLater(root.revealFocus)
    Connections {
        target: root.Window.window
        function onActiveFocusItemChanged() { Qt.callLater(root.revealFocus) }
    }

    function capture(command) {
        instantHandoffRequested()
        // Hide the popout before Hyprshot freezes the selection surface.
        Qt.callLater(() => Quickshell.execDetached(command))
    }

    width: 380
    implicitHeight: Math.min(620, root.currentItem?.implicitHeight ?? 0)

    CardStack {
        anchors.fill: parent
        cards: [pageCard]
        visible: root.currentPage !== "network"
        Card {
            id: pageCard
            stack: parent
            implicitHeight: pageLoader.item?.implicitHeight ?? 0
            initialFocus: pageLoader.item?.initialFocus ?? null
            Loader {
                id: pageLoader
                anchors.fill: parent
                active: root.visible && root.currentPage !== "network"
                sourceComponent: root.currentPage === "audio" ? audioPage
                    : root.currentPage === "performance" ? performancePage
                    : root.currentPage === "network" ? null
                            : root.currentPage === "bluetooth" ? bluetoothPage
                            : root.currentPage === "battery" ? batteryPage
                                : root.currentPage === "screenshot" ? screenshotPage
                                : root.currentPage === "media" ? mediaPage : notificationsPage
            }
        }
    }
    // Network owns asynchronous mutations and their feedback across popout/page changes.
    Loader {
        id: networkLoader
        anchors.fill: parent
        active: root.visible && root.currentPage === "network"
        visible: root.currentPage === "network"
        sourceComponent: networkPage
        // Replace the visibility binding after first load to retain the operation owner.
        onLoaded: active = true
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
            onCaptureRequested: command => root.capture(command)
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
