pragma ComponentBehavior: Bound

import QtQuick
import qs.icewine.theme as Theme

Rectangle {
    id: card
    property CardStack stack: null
    property int index: 0
    property Item initialFocus: null
    readonly property bool selected: !stack || stack.selectedCard === index
    readonly property bool active: stack ? stack.available && selected && !stack.exchanging : visible && enabled
    border.width: 0
    radius: 12
    color: Theme.Palette.backgroundDark
    clip: true
    readonly property bool outgoing: stack !== null && card.index === stack.outgoingCard
    readonly property real advance: stack ? stack.inOutCubic(stack.progress) : 0
    readonly property real sweep: !stack ? 0 : card.stack.progress < 0.5 ? card.stack.inOutCubic(card.stack.progress * 2)
        : 1 - Math.pow(1 - (card.stack.progress - 0.5) * 2, 3)
    width: !stack ? implicitWidth : Math.max(0, card.stack.width - (card.stack.stacked ? 34 : 0))
    height: !stack ? implicitHeight : Math.max(0, card.stack.height - (card.stack.stacked ? 64 : 0))
    x: !stack || !stack.stacked ? 0 : 8 + (!card.stack.exchanging ? (card.index === card.stack.frontCard ? 18 : 0)
        : !outgoing ? 18 * advance
        : card.stack.progress < 0.5 ? 18 + (-width - 30) * sweep : (-width - 12) * (1 - sweep))
    y: !stack || !stack.stacked ? 0 : 8 + (!card.stack.exchanging ? (card.index === card.stack.frontCard ? 48 : 0)
        : !outgoing ? 48 * advance
        : card.stack.progress < 0.5 ? 48 - 24 * sweep : 24 * (1 - sweep))
    // The outgoing card clears the clipped host before this handoff, also in reverse.
    z: !stack ? 0 : !card.stack.exchanging ? (card.index === card.stack.frontCard ? 2 : 1)
        : outgoing === (card.stack.progress < 0.5) ? 2 : 1
}
