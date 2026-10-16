pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import QtQuick.Templates as T

// Nonvisual arrangement and selection; card surfaces belong to Card.
FocusScope {
    id: root
    // Ponytail: fixed one/two/three-card compositions; larger decks need a selection design.
    property list<Card> cards
    onCardsChanged: resetSelection()
    readonly property bool stacked: cards.length > 1
    property Item initialFocus: exchanging ? motionFocus : cards[selectedCard]?.initialFocus ?? null
    readonly property Item motionInitialFocus: motionFocus
    signal selectionChanging()
    implicitWidth: Math.max(0, ...cards.map(card => card.implicitWidth)) + (stacked ? 34 : 0)
    implicitHeight: Math.max(0, ...cards.map(card => card.implicitHeight)) + (stacked ? 64 : 0)
    clip: true
    onAvailableChanged: if (!available && exchanging) finishExchange()
    property int selectedCard: 0
    property int frontCard: 0
    property int outgoingCard: 0
    property int incomingCard: 0
    property int queuedCard: -1
    property real progress: 0
    property bool exchanging: false
    property bool available: visible && enabled

    Keys.priority: Keys.AfterItem
    Keys.onPressed: event => navigate(event)

    function navigate(event) {
        if (!available || cards.length < 2 || event.modifiers !== Qt.NoModifier
                || ![Qt.Key_Left, Qt.Key_Right].includes(event.key)) return
        const target = root.Window.window?.activeFocusItem
        // Owners retain even ignored endpoint keys, including composite groups.
        for (let item = target; item && item !== root; item = item.parent)
            if (cards.some(card => card.arrowKeyOwners.includes(item))) return
        const plainButton = target instanceof T.AbstractButton
            && !(target instanceof T.MenuItem || target instanceof T.RadioButton
                || target instanceof T.TabButton)
        // Other controls (text, sliders, scrollbars, etc.) never opt in by bubbling.
        if (!plainButton && target !== root && target !== motionFocus
                && !cards.some(card => target === card || target === card.selector)) return
        event.accepted = true
        if (!event.isAutoRepeat)
            selectCard(((queuedCard >= 0 ? queuedCard : selectedCard) + (event.key === Qt.Key_Left ? -1 : 1) + cards.length) % cards.length)
    }

    function selectCard(index) {
        if (!available || !Number.isInteger(index) || index < 0 || index >= cards.length) return
        motionFocus.activationKey = 0
        queuedCard = -1
        if (exchanging && index !== outgoingCard && index !== incomingCard) {
            queuedCard = index
            return
        }
        if (selectedCard === index) {
            if (exchanging && root.activeFocus) motionFocus.forceActiveFocus()
            return
        }
        selectionChanging()
        if (root.activeFocus) motionFocus.forceActiveFocus()
        exchange.stop()
        if (!exchanging) {
            outgoingCard = frontCard
            incomingCard = index
            progress = 0
        }
        selectedCard = index
        exchanging = true
        exchange.to = index === outgoingCard ? 0 : 1
        exchange.duration = 200 * Math.abs(exchange.to - progress)
        if (exchange.duration === 0) finishExchange()
        else exchange.start()
    }

    // Membership changes cancel queued intent before optional cards can disappear.
    function resetSelection() {
        motionFocus.activationKey = 0
        selectionChanging()
        exchange.stop()
        queuedCard = -1
        selectedCard = 0
        frontCard = 0
        outgoingCard = 0
        incomingCard = 0
        exchanging = false
        progress = 0
        if (available && root.activeFocus) initialFocus?.forceActiveFocus()
    }

    function finishExchange() {
        exchange.stop()
        frontCard = selectedCard
        const queued = queuedCard
        queuedCard = -1
        if (available && queued >= 0 && queued !== selectedCard) {
            // Continue without briefly enabling the intermediate card's content.
            outgoingCard = frontCard
            incomingCard = queued
            selectedCard = queued
            progress = 0
            motionFocus.activationKey = 0
            selectionChanging()
            exchange.to = 1
            exchange.duration = 200
            exchange.start()
            return
        }
        exchanging = false
        progress = 0
        if (available && motionFocus.activeFocus) initialFocus?.forceActiveFocus()
    }

    // The next declared rear card sits halfway between the far rear and front.
    function rearOffset(index, front) {
        return cards.length === 3 && (index - front + cards.length) % cards.length === 1 ? 0.5 : 0
    }

    function inOutCubic(t) {
        return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
    }

    NumberAnimation {
        id: exchange
        target: root
        property: "progress"
        easing.type: Easing.Linear
        onFinished: root.finishExchange()
    }

    // A stationary keyboard target while either card may be clipped by the sweep.
    Item {
        id: motionFocus
        anchors.fill: parent
        property int activationKey: 0
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
            root.selectCard(((root.queuedCard >= 0 ? root.queuedCard : root.selectedCard) + 1) % root.cards.length)
        }
    }

}
