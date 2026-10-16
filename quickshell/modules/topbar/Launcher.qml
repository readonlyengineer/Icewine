pragma ComponentBehavior: Bound

import QtQuick

Widget {
    id: root
    property alias showingBackground: card.showingBackground
    property alias excludeSteamApps: card.excludeSteamApps
    readonly property alias backgroundCount: card.backgroundCount
    readonly property alias backgroundAttention: card.backgroundAttention
    function focusInitial() { card.focusInitial() }
    function showBackground() { card.showBackground() }
    function hideBackground() { card.hideBackground() }
    width: 400
    height: 424
    CardStack {
        anchors.fill: parent
        cards: [card]
        LauncherCard {
            id: card
            stack: parent
            engaged: root.engaged
            onHandoffRequested: root.handoffRequested()
        }
    }
}
