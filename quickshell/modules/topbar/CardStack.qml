pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Window
import QtQuick.Effects

// Nonvisual arrangement and selection; card surfaces belong to Card.
FocusScope {
    id: root
    property list<Card> cards
    onCardsChanged: resetSelection()
    readonly property bool stacked: cards.length > 1
    property int shadowDrop: 4
    property Item shadowHost: null
    readonly property int shadowGap: Math.floor(shadowDrop / Math.max(1, cards.length))
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

    // Each receiving plane gets its own projection. Receiver children remain below
    // every higher sibling card; the window plane sits below all card surfaces.
    Repeater {
        model: root.stacked ? [null].concat(root.cards) : []
        delegate: Item {
            id: receiverDelegate
            required property var modelData
            Item {
                id: plane
                readonly property Card receiver: receiverDelegate.modelData
                parent: receiver ?? root.shadowHost ?? root
                visible: root.visible
                x: receiver ? -receiver.x : root.shadowHost ? root.x + root.parent.mapToItem(root.shadowHost, 0, 0).x : 0
                y: receiver ? -receiver.y : root.shadowHost ? root.y + root.parent.mapToItem(root.shadowHost, 0, 0).y : 0
                width: root.width
                height: root.height
                z: receiver ? 1000 : -1
                Repeater {
                    model: root.cards
                    delegate: MultiEffect {
                        id: projection
                        required property Card modelData
                        readonly property Card caster: modelData
                        readonly property int casterRank: root.cards.filter(card => card && caster && card.z < caster.z).length
                        readonly property int receiverRank: plane.receiver
                            ? root.cards.filter(card => card && plane.receiver && card.z < plane.receiver.z).length : 0
                        anchors.fill: parent
                        visible: caster !== null && caster.visible && (!plane.receiver || caster.z > plane.receiver.z)
                        source: silhouette
                        // Fixed stack coordinates keep the mask and caster aligned during motion.
                        autoPaddingEnabled: plane.receiver === null && root.shadowHost !== null
                        shadowEnabled: true
                        shadowColor: "#000000"
                        shadowOpacity: 0.35
                        shadowBlur: 0.6
                        blurMax: 16
                        shadowVerticalOffset: plane.receiver
                            ? root.shadowGap * (casterRank - receiverRank)
                            : root.shadowDrop - root.shadowGap * (root.cards.length - 1 - casterRank)
                        maskEnabled: plane.receiver !== null
                        maskSource: receiverMask
                        Item {
                            id: silhouette
                            clip: true
                            width: root.width; height: root.height
                            visible: false
                            layer.enabled: true
                            Rectangle {
                                x: projection.caster?.x ?? 0; y: projection.caster?.y ?? 0
                                width: projection.caster?.width ?? 0; height: projection.caster?.height ?? 0
                                radius: projection.caster?.radius ?? 0
                                color: projection.caster?.color ?? "transparent"
                            }
                        }
                        Item {
                            id: receiverMask
                            width: root.width; height: root.height
                            visible: false
                            layer.enabled: true
                            Rectangle {
                                x: plane.receiver?.x ?? 0; y: plane.receiver?.y ?? 0
                                width: plane.receiver?.width ?? 0; height: plane.receiver?.height ?? 0
                                radius: plane.receiver?.radius ?? 0
                                color: "white"
                            }
                        }
                    }
                }
            }
        }
    }

    readonly property bool ownsFocus: {
        const target = root.Window.window?.activeFocusItem
        // Modal/popup focus outside this stack stays native.
        for (let item = target; item; item = item.parent)
            if (item === root) return available
        return false
    }
    readonly property bool ownsTab: ownsFocus
        && !(root.Window.window?.activeFocusItem instanceof TextEdit
            && !root.Window.window.activeFocusItem.tabChangesFocus)
    // Explicit traversal escapes controls whose native semantics own every arrow.
    Shortcut {
        sequence: "Ctrl+Tab"
        enabled: root.ownsFocus && !root.exchanging
        autoRepeat: false
        onActivated: root.cards[root.selectedCard]?.moveFocus(root.Window.window.activeFocusItem, true)
    }
    Shortcut {
        sequences: ["Ctrl+Shift+Tab", "Ctrl+Backtab"]
        enabled: root.ownsFocus && !root.exchanging
        autoRepeat: false
        onActivated: root.cards[root.selectedCard]?.moveFocus(root.Window.window.activeFocusItem, false)
    }
    Shortcut {
        sequence: "Tab"
        enabled: root.ownsTab
        autoRepeat: false
        onActivated: root.cycleCard(1)
    }
    Shortcut {
        sequences: ["Shift+Tab", "Backtab"]
        enabled: root.ownsTab
        autoRepeat: false
        onActivated: root.cycleCard(-1)
    }

    function cycleCard(direction) {
        if (available && cards.length)
            selectCard(((queuedCard >= 0 ? queuedCard : selectedCard) + direction + cards.length) % cards.length)
    }

    function selectCard(index) {
        if (!available || !Number.isInteger(index) || index < 0 || index >= cards.length) return
        for (const card of cards) card.selector.activationKey = 0
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
        for (const card of cards) card.selector.activationKey = 0
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

    // Distribute every rear card within the existing fixed stack allowance.
    function rearOffset(index, front) {
        return cards.length < 2 ? 0 : 1 - ((index - front + cards.length) % cards.length) / (cards.length - 1)
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
