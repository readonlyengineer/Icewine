pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import Quickshell
import "popouts" as Popouts
import qs.icewine.theme as Theme

Widget {
    id: root
    floatingCards: currentItem?.stacked ?? false

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
    readonly property bool audioPage: currentPage === "audio" || currentPage === "bluetooth"
    readonly property Item currentItem: audioPage ? audioStack : powerPage ? powerStack
        : currentPage === "network" ? networkLoader.item : pageLoader.item
    property bool powerEntryPending: true
    onCurrentPageChanged: {
        powerEntryPending = true
        if (powerEntry) powerEntry.restart()
        if (audioEntry) audioEntry.restart()
    }
    onShownChanged: if (shown && powerEntry) {
        powerEntryPending = true
        powerEntry.restart()
        audioEntry.restart()
    }
    Component.onCompleted: { powerEntry.restart(); audioEntry.restart() }

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
    Timer {
        id: audioEntry
        interval: 0
        onTriggered: if (root.audioPage) root.openAudioPage(root.currentPage)
    }

    function openAudioPage(page) {
        if (!root.audioPage || !root.visible || !root.enabled) return
        audioStack.resetSelection()
        if (page === "bluetooth") audioStack.selectCard(1)
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
        shadowDrop: root.shadowDrop
        shadowHost: root.cardShadowHost
        anchors.fill: parent
        cards: [pageCard]
        visible: !root.audioPage && !root.powerPage && root.currentPage !== "network"
        Card {
            id: pageCard
            stack: parent
            implicitHeight: pageLoader.item?.implicitHeight ?? 0
            initialFocus: pageLoader.item?.initialFocus ?? null
            Loader {
                id: pageLoader
                anchors.fill: parent
                active: root.visible && !root.audioPage && !root.powerPage && root.currentPage !== "network"
                sourceComponent: root.currentPage === "screenshot" ? screenshotPage
                    : root.currentPage === "media" ? mediaPage
                    : root.currentPage === "notifications" ? notificationsPage : null
            }
        }
    }
    CardStack {
        shadowDrop: root.shadowDrop
        shadowHost: root.cardShadowHost
        id: audioStack
        anchors.fill: parent
        visible: root.audioPage
        cards: [audioCard, bluetoothCard]
        Card {
            id: audioCard
            stack: audioStack
            accessibleName: "Audio card"
            implicitHeight: audioLoader.item?.implicitHeight ?? 0
            initialFocus: audioLoader.item?.initialFocus?.enabled ? audioLoader.item.initialFocus : selector
            Loader {
                id: audioLoader
                anchors.fill: parent
                active: root.visible && root.audioPage
                enabled: audioCard.active
                sourceComponent: audioContent
            }
        }
        Card {
            id: bluetoothCard
            stack: audioStack
            index: 1
            accessibleName: "Bluetooth card"
            implicitHeight: bluetoothLoader.item?.implicitHeight ?? 0
            initialFocus: bluetoothLoader.item?.initialFocus?.enabled ? bluetoothLoader.item.initialFocus : selector
            Loader {
                id: bluetoothLoader
                anchors.fill: parent
                active: root.visible && root.audioPage
                enabled: bluetoothCard.active
                sourceComponent: bluetoothPage
                // Pair-to-connect ownership survives card/page changes and dismissal.
                onLoaded: active = true
            }
        }
    }
    CardStack {
        shadowDrop: root.shadowDrop
        shadowHost: root.cardShadowHost
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
        id: audioContent
        Popouts.Audio {}
    }
    Component {
        id: networkPage
        Popouts.Network {
            shadowDrop: root.shadowDrop
            shadowHost: root.cardShadowHost
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
