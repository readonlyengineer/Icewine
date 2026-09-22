pragma ComponentBehavior: Bound

import QtQuick

FocusScope {
    id: root

    property bool engaged: false
    readonly property alias hovered: hover.hovered
    default property alias contentData: content.data

    signal dismissRequested()
    signal engageRequested()
    signal handoffRequested()

    clip: true

    HoverHandler { id: hover }

    FocusScope {
        id: viewport
        anchors.fill: parent
        focus: true

        property bool escapeHeld: false
        onActiveFocusChanged: if (!activeFocus) escapeHeld = false

        Keys.onEscapePressed: event => { if (!event.isAutoRepeat) viewport.escapeHeld = true }
        Keys.onReleased: event => {
            if (event.key !== Qt.Key_Escape)
                return
            event.accepted = true
            if (event.isAutoRepeat || !viewport.escapeHeld)
                return
            viewport.escapeHeld = false
            root.dismissRequested()
        }

        // Blank widget areas consume input too, so touches never reach the dial.
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onWheel: event => { root.engageRequested(); event.accepted = true }
        }
        Item { id: content; anchors.fill: parent }
    }

    // Observe before child controls accept the event, without taking their grab.
    Item {
        anchors.fill: parent
        z: 1
        PointHandler {
            acceptedButtons: Qt.AllButtons
            onActiveChanged: if (active) {
                root.engageRequested()
                root.forceActiveFocus(Qt.MouseFocusReason)
            }
        }
        WheelHandler {
            onWheel: event => {
                root.engageRequested()
                root.forceActiveFocus(Qt.MouseFocusReason)
                event.accepted = false
            }
        }
    }
}
