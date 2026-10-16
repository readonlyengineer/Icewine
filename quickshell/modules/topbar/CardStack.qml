pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import QtQuick.Templates as T

// Nonvisual arrangement and selection; card surfaces belong to Card.
FocusScope {
    id: root
    // Ponytail: fixed one-card/pair compositions; larger decks need a selection design.
    property list<Card> cards
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
    property real progress: 0
    property bool exchanging: false
    property bool available: visible && enabled

    Keys.priority: Keys.AfterItem
    Keys.onPressed: event => navigate(event)

    function navigate(event) {
        if (!available || cards.length !== 2 || event.modifiers !== Qt.NoModifier
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
            selectCard((selectedCard + (event.key === Qt.Key_Left ? -1 : 1) + cards.length) % cards.length)
    }

    function selectCard(index) {
        if (!available || !Number.isInteger(index) || index < 0 || index >= cards.length) return
        if (selectedCard === index) {
            if (exchanging && root.activeFocus) motionFocus.forceActiveFocus()
            return
        }
        motionFocus.activationKey = 0
        selectionChanging()
        if (root.activeFocus) motionFocus.forceActiveFocus()
        exchange.stop()
        if (!exchanging) {
            outgoingCard = frontCard
            progress = 0
        }
        selectedCard = index
        exchanging = true
        exchange.to = index === outgoingCard ? 0 : 1
        exchange.duration = 120 * Math.abs(exchange.to - progress)
        if (exchange.duration === 0) finishExchange()
        else exchange.start()
    }

    function finishExchange() {
        exchange.stop()
        frontCard = selectedCard
        exchanging = false
        progress = 0
        if (available && motionFocus.activeFocus) initialFocus?.forceActiveFocus()
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
            root.selectCard((root.selectedCard + 1) % root.cards.length)
        }
    }

}
