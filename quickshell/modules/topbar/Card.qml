pragma ComponentBehavior: Bound

import QtQuick
import qs.icewine.theme as Theme

Rectangle {
    id: card
    property CardStack stack: null
    property int index: 0
    property Item initialFocus: selector
    // Reserve custom arrow owners (and their descendants), including ignored endpoints.
    property list<Item> arrowKeyOwners
    property string accessibleName: "Card"
    readonly property alias selector: selector
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
    readonly property real rearStart: stack ? stack.rearOffset(index, stack.outgoingCard) : 0
    readonly property real rearEnd: stack ? stack.rearOffset(index, stack.incomingCard) : 0
    readonly property real depth: !stack ? 0 : !stack.exchanging
        ? (index === stack.frontCard ? 1 : stack.rearOffset(index, stack.frontCard))
        : index === stack.incomingCard ? rearStart + (1 - rearStart) * advance
        : rearStart + (rearEnd - rearStart) * advance
    x: !stack || !stack.stacked ? 0 : 8 + (stack.exchanging && outgoing
        ? stack.progress < 0.5 ? 18 + (-width - 30) * sweep
            : -width - 12 + (width + 12 + 18 * rearEnd) * sweep
        : 18 * depth)
    y: !stack || !stack.stacked ? 0 : 8 + (stack.exchanging && outgoing
        ? stack.progress < 0.5 ? 48 - 24 * sweep : 24 + (48 * rearEnd - 24) * sweep
        : 48 * depth)
    // The outgoing card clears the clipped host before the incoming card takes front.
    z: !stack ? 0 : !stack.exchanging ? (index === stack.frontCard ? 2 : 1 + depth)
        : outgoing ? (stack.progress < 0.5 ? 2 : 1 + rearEnd)
        : index === stack.incomingCard ? (stack.progress < 0.5 ? 1 + rearStart : 2) : 1 + depth

    // Explicit keyboard selection and a plain target for stack arrow navigation.
    Item {
        id: selector
        width: parent.width
        height: Math.min(44, parent.height)
        activeFocusOnTab: card.stack !== null && card.stack.stacked && !card.stack.exchanging
        readonly property bool checked: card.selected
        property int activationKey: 0
        Accessible.ignored: !card.stack || !card.stack.stacked
        Accessible.role: Accessible.RadioButton
        Accessible.name: card.accessibleName
        Accessible.checkable: true
        Accessible.checked: checked
        Accessible.onPressAction: if (card.stack) card.stack.selectCard(card.index)
        onActiveFocusChanged: if (!activeFocus) activationKey = 0
        Keys.onPressed: event => {
            if (![Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space].includes(event.key)) return
            event.accepted = true
            if (!event.isAutoRepeat) activationKey = event.key
        }
        Keys.onReleased: event => {
            if (event.isAutoRepeat || event.key !== activationKey) return
            event.accepted = true
            activationKey = 0
            if (card.stack) card.stack.selectCard(card.index)
        }
    }
    // Above rear/moving content; below front controls, catching blank-surface clicks.
    MouseArea {
        anchors.fill: parent
        z: card.active ? -1 : 100
        enabled: card.stack !== null && card.stack.available
        acceptedButtons: Qt.AllButtons
        onWheel: event => event.accepted = true
        onClicked: event => {
            if (event.button !== Qt.LeftButton || (card.selected && !card.stack.exchanging)) return
            if (card.stack.exchanging) card.stack.motionInitialFocus.forceActiveFocus()
            else selector.forceActiveFocus(Qt.MouseFocusReason)
            card.stack.selectCard(card.index)
        }
    }
}
