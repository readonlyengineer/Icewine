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
        active: powerCard.active && !root.powerEntryPending
    }
    property string currentPage: "audio"
    readonly property bool powerPage: currentPage === "battery" || currentPage === "performance"
    readonly property Item currentItem: powerPage ? powerStack
        : currentPage === "network" ? networkLoader.item : pageLoader.item
    property bool powerEntryPending: true
    onCurrentPageChanged: {
        powerEntryPending = true
        if (powerEntry) powerEntry.restart()
    }
    onShownChanged: if (shown && powerEntry) {
        powerEntryPending = true
        powerEntry.restart()
    }
    Component.onCompleted: powerEntry.restart()

    // Wait for page visibility/enabled bindings before selecting; never poll.
    Timer {
        id: powerEntry
        interval: 0
        onTriggered: if (root.powerPage) root.openPowerPage(root.currentPage)
    }

    function openPowerPage(page) {
        if (!root.powerPage || !root.visible || !root.enabled) return
        powerEntryPending = true
        powerStack.resetSelection()
        if (page === "performance") powerStack.selectCard(1)
        powerEntryPending = false
    }
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
        visible: !root.powerPage && root.currentPage !== "network"
        Card {
            id: pageCard
            stack: parent
            implicitHeight: pageLoader.item?.implicitHeight ?? 0
            initialFocus: pageLoader.item?.initialFocus ?? null
            Loader {
                id: pageLoader
                anchors.fill: parent
                active: root.visible && !root.powerPage && root.currentPage !== "network"
                sourceComponent: root.currentPage === "audio" ? audioPage
                    : root.currentPage === "network" ? null
                    : root.currentPage === "bluetooth" ? bluetoothPage
                    : root.currentPage === "screenshot" ? screenshotPage
                    : root.currentPage === "media" ? mediaPage : notificationsPage
            }
        }
    }
    CardStack {
        id: powerStack
        anchors.fill: parent
        visible: root.powerPage
        cards: [powerCard, performanceCard]
        Card {
            id: powerCard
            stack: powerStack
            accessibleName: "Power card"
            implicitHeight: powerLoader.item?.implicitHeight ?? 0
            initialFocus: powerLoader.item?.initialFocus ?? selector
            Loader {
                id: powerLoader
                anchors.fill: parent
                active: root.visible && root.powerPage
                enabled: powerCard.active
                sourceComponent: batteryPage
            }
        }
        Card {
            id: performanceCard
            stack: powerStack
            index: 1
            accessibleName: "Performance card"
            implicitHeight: performanceLoader.item?.implicitHeight ?? 0
            initialFocus: performanceLoader.item?.initialFocus ?? selector
            Loader {
                id: performanceLoader
                anchors.fill: parent
                active: root.visible && root.powerPage
                enabled: performanceCard.active
                sourceComponent: performancePage
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
