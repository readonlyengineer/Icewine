pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import QtQuick.Controls
import Quickshell
import Quickshell.Services.SystemTray
import qs.config as Config
import "CardModules.js" as Cards
import "popouts" as Popouts
import qs.icewine.theme as Theme

// One host per output. Module loaders retain asynchronous ownership after first use.
Widget {
    id: root
    required property var compositor
    property var notificationService: null
    property var session: null
    property var player: null
    property var powerState: null
    property var metrics: null
    property string monitorName: ""
    property var clipboardHistory: null
    property bool pasteBusy: false
    property bool excludeSteamApps: false
    property bool layoutsEnabled: true
    property var backgroundItems: SystemTray.items.values
    readonly property int backgroundCount: backgroundItems.length
    readonly property bool backgroundAvailable: backgroundCount > 0
    readonly property bool backgroundAttention: backgroundItems.some(item => item.status === Status.NeedsAttention)
    property var cardStacks: Config.Settings.cardStacks
    property string currentPage: "audio"
    readonly property var configuration: Cards.containing(cardStacks, currentPage)
    readonly property var modules: configuration?.modules ?? []
    readonly property var availableModules: modules.filter(name => (name !== "layout" || layoutsEnabled)
        && (name !== "background" || backgroundAvailable))
    readonly property alias currentItem: stack
    readonly property bool layoutActive: cardFor("layout")?.layoutActive ?? false
    floatingCards: stack.stacked
    implicitWidth: stack.implicitWidth
    implicitHeight: Math.min(620, stack.implicitHeight)
    width: implicitWidth
    height: implicitHeight

    signal mediaRequested()
    signal keyboardRequested()
    signal pasteRequested(string entry)

    property var loadedCards: ({})
    function cardFor(name) {
        return loadedCards[name] ?? null
    }
    function focusInitial() {
        root.forceActiveFocus(Qt.ShortcutFocusReason)
        stack.initialFocus?.forceActiveFocus(Qt.ShortcutFocusReason)
    }
    property var selections: ({})
    property string openedStackId: ""
    property bool restoreEntry: false
    function rememberSelection() {
        if (!entryPending && configuration && availableModules[stack.selectedCard])
            selections = Object.assign({}, selections, {[configuration.id]: availableModules[stack.selectedCard]})
    }
    function openPage(page, restore = false) {
        if (!shown || !stack.visible || !stack.enabled) return
        const target = restore ? selections[configuration?.id] ?? page : page
        entryPending = true
        stack.resetSelection()
        const index = availableModules.indexOf(target)
        if (index > 0) stack.selectCard(index)
        openedStackId = configuration?.id ?? ""
        entryPending = false
        rememberSelection()
        if (engaged) focusInitial()
    }
    // Preserve existing explicit opening intents, including IPC calls.
    function openLauncher() {
        openPage("launcher")
    }
    function openLayout() {
        openPage("layout")
    }
    function openPowerPage(page) {
        currentPage = page
        openPage(page)
    }
    function openAudioPage(page) {
        currentPage = page
        openPage(page)
    }
    property bool entryPending: true
    onCurrentPageChanged: {
        restoreEntry = configuration?.id !== openedStackId
        entryPending = true
        entry.restart()
    }
    onShownChanged: if (shown && entryPending) entry.restart()
    onAvailableModulesChanged: {
        restoreEntry = configuration?.id !== openedStackId
        entryPending = true
        entry.restart()
    }
    Component.onCompleted: entry.restart()
    Timer { id: entry; interval: 0; onTriggered: root.openPage(root.currentPage, root.restoreEntry) }

    function revealFocus() {
        const item = root.Window.window?.activeFocusItem
        let page = item
        while (page && page !== stack) page = page.parent
        if (!root.visible || !root.enabled || !page || item === page) return
        for (let scroll = item.parent; scroll; scroll = scroll.parent) {
            if (scroll instanceof Flickable && scroll.height > 0) {
                const top = item.mapToItem(scroll.contentItem, 0, 0).y
                const bottom = top + item.height
                const target = top < scroll.contentY ? top
                    : bottom > scroll.contentY + scroll.height ? bottom - scroll.height : scroll.contentY
                scroll.contentY = Math.max(scroll.originY, Math.min(target,
                    scroll.originY + Math.max(0, scroll.contentHeight - scroll.height)))
            }
            if (scroll === stack) break
        }
    }
    onHeightChanged: Qt.callLater(root.revealFocus)
    Connections {
        target: root.Window.window
        function onActiveFocusItemChanged() { Qt.callLater(root.revealFocus) }
    }

    MonitorBrightness {
        id: monitorBrightness
        monitorName: root.monitorName
        active: !root.entryPending && (root.cardFor("battery")?.active ?? false)
    }
    CardStack {
        id: stack
        shadowDrop: root.shadowDrop
        shadowHost: root.cardShadowHost
        anchors.fill: parent
        onSelectedCardChanged: root.rememberSelection()
        cards: root.availableModules.map(name => root.cardFor(name)).filter(card => card !== null)
        available: visible && enabled && !(cards[selectedCard]?.navigationBlocked ?? false)
        // A pending password owns focus without enabling the other cards.
        initialFocus: cards[selectedCard]?.navigationBlocked ? cards[selectedCard].initialFocus
            : exchanging ? motionInitialFocus : cards[selectedCard]?.initialFocus ?? null
        Repeater {
            id: moduleCards
            model: Cards.modules
            delegate: Loader {
                id: moduleLoader
                required property string modelData
                readonly property int configuredIndex: root.modules.indexOf(modelData)
                readonly property int cardIndex: root.availableModules.indexOf(modelData)
                readonly property color accent: [Theme.Palette.primary, Theme.Palette.secondary,
                    Theme.Palette.tertiary][Math.max(0, configuredIndex) % 3]
                active: root.availableModules.includes(modelData)
                sourceComponent: modelData === "launcher" ? launcherCard
                    : modelData === "layout" ? layoutCard : contentCard
                onLoaded: {
                    active = true
                    item.parent = stack
                    root.loadedCards = Object.assign({}, root.loadedCards, {[modelData]: item})
                    entry.restart()
                }
                Component {
                    id: launcherCard
                    LauncherCard {
                        stack: stack
                        index: moduleLoader.cardIndex
                        visible: index >= 0
                        accent: moduleLoader.accent
                        accessibleName: "Launcher card"
                        engaged: root.engaged
                        excludeSteamApps: root.excludeSteamApps
                        onHandoffRequested: root.handoffRequested()
                        onKeyboardRequested: root.keyboardRequested()
                    }
                }
                Component {
                    id: layoutCard
                    LayoutCard {
                        stack: stack
                        index: moduleLoader.cardIndex
                        visible: index >= 0
                        accent: moduleLoader.accent
                        compositor: root.compositor
                    }
                }
                Component {
                    id: contentCard
                    Card {
                        id: card
                        stack: stack
                        index: moduleLoader.cardIndex
                        visible: index >= 0
                        accent: moduleLoader.accent
                        accessibleName: (moduleLoader.modelData === "network" ? "Networking"
                            : moduleLoader.modelData === "battery" ? "Power"
                            : moduleLoader.modelData === "ssh" ? "SSH"
                            : moduleLoader.modelData === "background" ? "Background applications"
                            : moduleLoader.modelData[0].toUpperCase() + moduleLoader.modelData.slice(1)) + " card"
                        implicitWidth: moduleLoader.modelData === "background" ? 400 : 380
                        implicitHeight: body.item?.implicitHeight ?? 0
                        readonly property bool navigationBlocked: body.item?.navigationBlocked ?? false
                        initialFocus: body.item?.initialFocus?.enabled ? body.item.initialFocus : selector
                        arrowKeyOwners: moduleLoader.modelData === "background" && body.item ? [body.item] : []
                        Loader {
                            id: body
                            anchors.fill: parent
                            active: root.visible && card.visible
                            // Keep service owners alive when the stack changes or closes.
                            onLoaded: active = true
                            visible: card.visible
                            enabled: card.selected && !stack.exchanging && root.enabled
                            sourceComponent: moduleLoader.modelData === "audio" ? audio
                                : moduleLoader.modelData === "bluetooth" ? bluetooth
                                : moduleLoader.modelData === "battery" ? battery
                                : moduleLoader.modelData === "performance" ? performance
                                : moduleLoader.modelData === "network" ? network
                                : moduleLoader.modelData === "tailscale" ? tailscale
                                : moduleLoader.modelData === "ssh" ? ssh
                                : moduleLoader.modelData === "clipboard" ? clipboard
                                : moduleLoader.modelData === "notifications" ? notifications
                                : moduleLoader.modelData === "media" ? media : background
                        }
                        Component { id: audio; Popouts.Audio { accent: card.accent } }
                        Component { id: bluetooth; Popouts.Bluetooth { accent: card.accent } }
                        Component { id: battery; Popouts.Battery {
                            accent: card.accent
                            powerState: root.powerState; session: root.session; brightness: monitorBrightness
                        } }
                        Component { id: performance; Popouts.Performance { accent: card.accent; metrics: root.metrics } }
                        Component { id: network; Popouts.Network {
                            accent: card.accent; metrics: root.metrics
                            active: card.active
                        } }
                        Component { id: tailscale; Item {
                            implicitHeight: page.implicitHeight + 44
                            Text { x: 12; y: 12; text: "Tailscale"; color: card.accent
                                font { family: "JetBrainsMono Nerd Font"; pixelSize: 15; bold: true } }
                            Popouts.Tailscale { id: page; anchors.fill: parent; anchors.topMargin: 44; active: card.active }
                        } }
                        Component { id: ssh; Item {
                            implicitHeight: page.implicitHeight + 53
                            Text { x: 16; y: 18; text: "SSH"; color: card.accent
                                font { family: "JetBrainsMono Nerd Font"; pixelSize: 15 } }
                            Popouts.Ssh { id: page; anchors.fill: parent; anchors.topMargin: 53; active: card.active }
                        } }
                        Component { id: clipboard; Popouts.Clipboard {
                            accent: card.accent; history: root.clipboardHistory; pasteBusy: root.pasteBusy
                            onPasteRequested: entry => root.pasteRequested(entry)
                        } }
                        Component { id: media; Popouts.Media {
                            accent: card.accent; player: root.player; onRaiseRequested: root.mediaRequested()
                        } }
                        Component { id: notifications; Popouts.Notifications {
                            accent: card.accent; compositor: root.compositor; notificationService: root.notificationService
                            onSourceRequested: address => {
                                root.handoffRequested()
                                Qt.callLater(() => root.compositor.activateWindow(address))
                            }
                        } }
                        Component { id: background; Item {
                            implicitHeight: 424
                            readonly property Item initialFocus: apps.initialFocus
                            Text { x: 12; y: 12; text: "Background applications"; color: card.accent
                                font { family: "JetBrainsMono Nerd Font"; pixelSize: 15; bold: true } }
                            BackgroundApps {
                                id: apps
                                anchors.fill: parent; anchors.margins: 12; anchors.topMargin: 50
                                items: root.backgroundItems
                                enabled: card.active
                                onEnabledChanged: if (!enabled) closeMenu()
                                onBackRequested: stack.selectCard(0)
                                onHandoffRequested: root.handoffRequested()
                            }
                        } }
                    }
                }
            }
        }
    }
}
