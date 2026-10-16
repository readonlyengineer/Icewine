pragma ComponentBehavior: Bound

import QtQuick
import Quickshell.Services.SystemTray
import qs.icewine.theme as Theme

Widget {
    id: root
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

    implicitWidth: stack.implicitWidth
    implicitHeight: stack.implicitHeight
    width: implicitWidth
    height: implicitHeight
    CardStack {
        id: stack
        anchors.fill: parent
        cards: background.item ? [card, background.item] : [card]
        onSelectionChanging: background.item?.closeMenu()
        LauncherCard {
            id: card
            stack: stack
            engaged: root.engaged
            onHandoffRequested: root.handoffRequested()
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
