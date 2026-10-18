pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import qs.icewine.theme as Theme
import "KeyboardModel.js" as Model

Rectangle {
    id: root
    readonly property Item firstControl: pinControl
    property bool locked: false
    property bool busy: false
    property string error: ""
    property bool pinned: true
    property int selected: 0
    property int modifiers: 0
    property bool caps: false
    property int armed: -1
    property bool repeated: false
    property string heldDirection: ""
    // Grow the whole keyboard up to 2x; retain scrollable 44-unit keys on small outputs.
    readonly property real sizeScale: Math.max(1, Math.min(2, ((parent?.width ?? 0) - 24) / 1040,
        (parent?.height ?? 0) * 0.55 / 344))
    readonly property real pitch: Math.max(48 * sizeScale, (width - 12 * sizeScale) / 16)
    readonly property real rowPitch: 48 * sizeScale
    readonly property real keyHeight: 44 * sizeScale
    signal activated(var action)
    signal hideRequested()
    objectName: "sharedKeyboard"
    width: Math.max(0, Math.min(1040 * sizeScale, (parent?.width ?? 0) - 24))
    height: Math.max(0, Math.min(344 * sizeScale, (parent?.height ?? 0) * 0.55))
    radius: 12 * sizeScale
    color: Theme.Palette.alpha(Theme.Palette.backgroundDark, Theme.Palette.keyboardOpacity)
    border.color: Theme.Palette.border
    border.width: 1
    clip: true

    function place() {
        if (!parent) return
        x = pinned ? (parent.width-width)/2 : Math.max(0, Math.min(x, parent.width-width))
        y = pinned ? Math.max(0, parent.height-height-12) : Math.max(0, Math.min(y, parent.height-height))
    }
    function cancelGesture() { if (repeated) modifiers = 0; armed = -1; repeatDelay.stop(); repeatTick.stop(); repeated = false }
    function cancel() { cancelGesture(); modifiers = 0; caps = false; heldDirection = ""; navigation.stop() }
    function allowed(key) { return !locked || key.caps || key.modifier === Model.shift || Model.lockAllowed(key, modifiers) }
    function activate(index) {
        const key = Model.keys[index]
        if (!key || !allowed(key) || !visible || !enabled || busy) return
        if (key.modifier) { modifiers ^= key.modifier; return }
        if (key.caps) { caps = !caps; return }
        activated(Model.action(key, modifiers, caps))
        if (!repeated) modifiers = 0
    }
    function arm(index) {
        cancelGesture()
        if (busy || !allowed(Model.keys[index])) return
        selected = index; armed = index
        if (Model.keys[index].repeat && !(modifiers & (Model.control|Model.alt|Model.meta))) repeatDelay.restart()
    }
    function release(index) {
        if (armed !== index) return
        const emit = !repeated
        repeatDelay.stop(); repeatTick.stop(); armed = -1
        if (emit) activate(index)
        if (!emit) modifiers = 0
        repeated = false
    }
    function repeatKey() {
        if (armed < 0 || busy || !visible || !enabled) return
        repeated = true
        activate(armed)
    }
    function move(direction) {
        cancelGesture()
        selected = Model.move(selected, direction)
        revealSelected()
    }
    function revealSelected() {
        const key = Model.keys[selected]
        const left = key.column * pitch, top = key.row * rowPitch
        viewport.contentX = Math.max(0, Math.min(left, Math.max(viewport.contentX, left + key.units*pitch - viewport.width)))
        viewport.contentY = Math.max(0, Math.min(top, Math.max(viewport.contentY, top + keyHeight - viewport.height)))
    }
    function controller(event) {
        const direction = /^ui_(left|right|up|down)$/.exec(event.action)
        if (direction) {
            if (event.pressed) { heldDirection = direction[1]; move(heldDirection); navigation.interval = 400; navigation.restart() }
            else if (heldDirection === direction[1]) { heldDirection = ""; navigation.stop() }
        } else if (event.action === "ui_accept") {
            if (event.pressed) arm(selected)
            else release(selected)
        } else if (event.action === "ui_back" && !event.pressed) hideRequested()
    }
    onSelectedChanged: revealSelected()
    onPinnedChanged: place()
    onWidthChanged: place()
    onHeightChanged: place()
    onVisibleChanged: { cancel(); if (visible) { pinned = true; selected = 0; place(); revealSelected() } }
    onEnabledChanged: if (!enabled) cancel()
    Component.onCompleted: place()
    Connections { target: root.parent; function onWidthChanged() { root.place() } function onHeightChanged() { root.place() } }
    Timer { id: repeatDelay; interval: 450; onTriggered: { root.repeatKey(); repeatTick.start() } }
    Timer { id: repeatTick; interval: 70; repeat: true; onTriggered: root.repeatKey() }
    Timer { id: navigation; interval: 400; repeat: true; onTriggered: { root.move(root.heldDirection); interval = 90 } }

    Row {
        id: header
        x: 8 * root.sizeScale; y: 2 * root.sizeScale
        width: Math.max(0, root.width - 16 * root.sizeScale)
        height: root.keyHeight; spacing: 4 * root.sizeScale
        ToolButton {
            id: pinControl
            objectName: "keyboardPin"
            text: root.pinned ? qsTr("Unpin") : qsTr("Pin")
            Accessible.name: root.pinned ? qsTr("Unpin keyboard") : qsTr("Pin keyboard")
            palette.buttonText: Theme.Palette.foreground
            focusPolicy: Qt.TabFocus
            width: Math.max(0, Math.min(80 * root.sizeScale, (header.width - 2 * header.spacing) / 2))
            height: root.keyHeight
            font.pixelSize: 13 * root.sizeScale
            onClicked: root.pinned = !root.pinned
        }
        Label {
            text: root.error || qsTr("Keyboard")
            color: Theme.Palette.foreground
            height: root.keyHeight
            font.pixelSize: 13 * root.sizeScale
            verticalAlignment: Text.AlignVCenter
            width: Math.max(0, header.width - pinControl.width - hideControl.width - 2 * header.spacing)
            elide: Text.ElideRight
            DragHandler {
                target: root
                enabled: !root.pinned
                xAxis.minimum: 0; xAxis.maximum: Math.max(0, (root.parent?.width ?? 0) - root.width)
                yAxis.minimum: 0; yAxis.maximum: Math.max(0, (root.parent?.height ?? 0) - root.height)
                onActiveChanged: if (active) root.cancelGesture()
            }
        }
        ToolButton { id: hideControl; objectName: "keyboardHide"; text: qsTr("Hide"); palette.buttonText: Theme.Palette.foreground; focusPolicy: Qt.TabFocus; width: Math.max(0, Math.min(80 * root.sizeScale, (header.width - 2 * header.spacing) / 2)); height: root.keyHeight; font.pixelSize: 13 * root.sizeScale; onClicked: root.hideRequested() }
    }
    Flickable {
        id: viewport
        x: 8 * root.sizeScale; y: root.rowPitch
        width: Math.max(0, parent.width - 16 * root.sizeScale); height: Math.max(0, parent.height - 56 * root.sizeScale)
        contentWidth: 16*root.pitch - 4 * root.sizeScale; contentHeight: 6 * root.rowPitch - 4 * root.sizeScale
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        onMovementStarted: root.cancelGesture()
        onWidthChanged: Qt.callLater(root.revealSelected)
        onHeightChanged: Qt.callLater(root.revealSelected)
        onContentWidthChanged: Qt.callLater(root.revealSelected)
        Repeater {
            model: Model.keys
            Button {
                id: keyButton
                required property var modelData
                readonly property bool latched: modelData.caps ? root.caps : !!(root.modifiers & (modelData.modifier || 0))
                objectName: "oskKey" + modelData.index
                x: modelData.column*root.pitch; y: modelData.row*root.rowPitch
                width: modelData.units*root.pitch - 4 * root.sizeScale; height: root.keyHeight
                text: modelData.text === " " ? qsTr("Space") : Model.text(modelData, root.modifiers, root.caps) || modelData.label
                Accessible.name: text
                focusPolicy: Qt.TabFocus
                enabled: root.allowed(modelData)
                onPressed: root.arm(modelData.index)
                onClicked: root.release(modelData.index)
                onCanceled: root.cancelGesture()
                // Passive tracking sees mouse and touch departure while held,
                // without treating an ordinary inside release as cancellation.
                PointHandler {
                    onPointChanged: if (active && root.armed === keyButton.modelData.index
                        && (point.position.x < 0 || point.position.y < 0
                            || point.position.x >= keyButton.width || point.position.y >= keyButton.height)) root.cancelGesture()
                }
                Keys.onPressed: event => {
                    const directions = ({[Qt.Key_Left]:"left", [Qt.Key_Right]:"right", [Qt.Key_Up]:"up", [Qt.Key_Down]:"down"})
                    if (directions[event.key]) { event.accepted = true; root.move(directions[event.key]); viewport.contentItem.children.find(item => item.objectName === "oskKey"+root.selected)?.forceActiveFocus() }
                    else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { event.accepted = true; if (!event.isAutoRepeat) root.arm(modelData.index) }
                }
                Keys.onReleased: event => { if ([Qt.Key_Return, Qt.Key_Enter].includes(event.key)) { event.accepted = true; root.release(modelData.index) } }
                background: Rectangle {
                    radius: 6 * root.sizeScale
                    color: root.armed === keyButton.modelData.index || keyButton.latched ? Theme.Palette.primary : Theme.Palette.surface
                    border.width: keyButton.activeFocus || root.selected === keyButton.modelData.index ? 2 : 1
                    border.color: keyButton.activeFocus || root.selected === keyButton.modelData.index ? Theme.Palette.primary : Theme.Palette.border
                    opacity: keyButton.enabled ? 1 : 0.4
                }
                contentItem: Text {
                    text: keyButton.text; font.pixelSize: 13 * root.sizeScale; elide: Text.ElideRight
                    color: root.armed === keyButton.modelData.index || keyButton.latched ? Theme.Palette.highlightedText : Theme.Palette.foreground
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }
}
