pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import QtQuick.Controls
import Quickshell.Services.SystemTray
import qs.icewine.theme as Theme

Widget {
    id: root
    required property var compositor
    property bool layoutsEnabled: true
    readonly property bool layoutActive: layout.item?.active ?? false
    property alias excludeSteamApps: card.excludeSteamApps
    property var backgroundItems: SystemTray.items.values
    readonly property int backgroundCount: backgroundItems.length
    readonly property bool backgroundAttention: backgroundItems.some(
        item => item.status === Status.NeedsAttention)

    function focusInitial() { stack.initialFocus?.forceActiveFocus() }
    function openLauncher() {
        stack.resetSelection()
        focusInitial()
    }

    function openLayout() {
        if (!shown || !stack.available || !layout.item) return
        stack.selectCard(layout.item.index)
        if (engaged) focusInitial()
    }

    implicitWidth: stack.implicitWidth
    implicitHeight: stack.implicitHeight
    width: implicitWidth
    height: implicitHeight
    CardStack {
        id: stack
        anchors.fill: parent
        cards: [card].concat(background.item ? [background.item] : [], layout.item ? [layout.item] : [])
        onSelectionChanging: background.item?.closeMenu()
        LauncherCard {
            id: card
            stack: stack
            engaged: root.engaged
            onHandoffRequested: root.handoffRequested()
        }
        Loader {
            id: layout
            active: root.layoutsEnabled
            sourceComponent: Card {
                id: layoutCard
                parent: stack
                stack: stack
                index: background.item ? 2 : 1
                accessibleName: "Workspace layout"
                arrowKeyOwners: [layoutScroll]
                function revealFocus() {
                    const item = layoutCard.Window.window?.activeFocusItem
                    let owner = item
                    while (owner && owner !== picker) owner = owner.parent
                    if (!active || !owner) return
                    const scroll = layoutScroll.contentItem
                    const top = item.mapToItem(scroll.contentItem, 0, 0).y
                    const bottom = top + item.height
                    const target = top < scroll.contentY ? top
                        : bottom > scroll.contentY + scroll.height ? bottom - scroll.height : scroll.contentY
                    scroll.contentY = Math.max(0, Math.min(target, Math.max(0, scroll.contentHeight - scroll.height)))
                }
                onHeightChanged: Qt.callLater(revealFocus)
                Connections {
                    target: layoutCard.Window.window
                    function onActiveFocusItemChanged() { Qt.callLater(layoutCard.revealFocus) }
                }
                implicitWidth: 400
                implicitHeight: 424
                initialFocus: picker.available && layoutCard.active ? picker.initialFocus : selector
                ScrollView {
                    id: layoutScroll
                    anchors.fill: parent
                    enabled: layoutCard.active
                    clip: true
                    contentWidth: availableWidth
                    LayoutPicker {
                        id: picker
                        width: layoutScroll.availableWidth
                        compositor: root.compositor
                    }
                }
            }
        }
        Loader {
            id: background
            active: root.backgroundCount > 0
            sourceComponent: Card {
                id: backgroundCard
                parent: stack
                stack: stack
                index: 1
                accessibleName: "Background applications"
                implicitWidth: 400
                implicitHeight: 424
                initialFocus: apps.initialFocus
                arrowKeyOwners: [apps]
                function closeMenu() { apps.closeMenu() }
                onActiveChanged: if (!active) apps.closeMenu()
                Text {
                    x: 12; y: 12
                    text: "Background applications"
                    color: Theme.Palette.foreground
                    font.family: "JetBrainsMono Nerd Font"
                    font.pixelSize: 12
                }
                BackgroundApps {
                    id: apps
                    anchors.fill: parent
                    anchors.margins: 12
                    anchors.topMargin: 50
                    enabled: backgroundCard.active
                    items: root.backgroundItems
                    onBackRequested: stack.selectCard(0)
                    onHandoffRequested: root.handoffRequested()
                }
            }
        }
    }
}
