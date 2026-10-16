pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import Quickshell.Wayland
import "WindowSwitcherModel.js" as Model
import qs.icewine.theme as Theme

FocusScope {
    id: root
    required property var compositor
    required property string monitorName
    readonly property var rows: Model.rows(compositor.toplevels, monitorName)
    property var selected: null
    property var pendingWindow: null
    property int actionKey: 0
    implicitWidth: Math.max(360, 32 + Math.max(0, ...rows.map(row => row.windows.length * (240 + 12) - 12)))
    implicitHeight: Math.max(140, 32 + rows.length * (workspaceFont.height + 6 + 170 + 12)
        + Math.max(0, rows.length - 1) * 16)
    readonly property int cardWidth: Math.max(0, Math.min(240, width - 32))
    readonly property int cardHeight: Math.max(0, Math.min(170, height - 72))
    FontMetrics { id: workspaceFont; font.pixelSize: 16 }
    signal dismissRequested()
    signal activateRequested(var window)

    function navigate(horizontal, vertical) {
        selected = Model.move(rows, selected, horizontal, vertical)
    }

    function ensureVisible() {
        const position = Model.locate(rows, selected)
        if (!position) return
        // callLater can precede the positioner's polish after model/size changes.
        contents.forceLayout()
        const rowItem = rowViews.itemAt(position.row)
        if (!rowItem) return
        const top = rowItem.y + rowItem.list.y
        const bottom = top + cardHeight
        let target = viewport.contentY
        if (top < target) target = top
        else if (bottom > target + viewport.height) target = bottom - viewport.height
        viewport.contentY = Math.max(0, Math.min(target, viewport.contentHeight - viewport.height))
        rowItem.list.forceLayout()
        rowItem.list.positionViewAtIndex(position.column, ListView.Contain)
    }

    onRowsChanged: {
        selected = Model.reconcile(rows, selected, compositor.activeWindowAddress)
        Qt.callLater(ensureVisible)
    }
    onWidthChanged: Qt.callLater(ensureVisible)
    onHeightChanged: Qt.callLater(ensureVisible)
    onSelectedChanged: Qt.callLater(ensureVisible)
    Component.onCompleted: {
        selected = Model.reconcile(rows, selected, compositor.activeWindowAddress)
        Qt.callLater(ensureVisible)
    }
    onActiveFocusChanged: if (!activeFocus) { actionKey = 0; pendingWindow = null }
    Shortcut {
        sequence: "Escape"
        enabled: root.visible && root.enabled
        onActivated: root.dismissRequested()
    }
    Keys.onLeftPressed: navigate(-1, 0)
    Keys.onRightPressed: navigate(1, 0)
    Keys.onUpPressed: navigate(0, -1)
    Keys.onDownPressed: navigate(0, 1)
    Keys.onPressed: event => {
        if (![Qt.Key_Return, Qt.Key_Enter].includes(event.key)) return
        event.accepted = true
        if (!event.isAutoRepeat) {
            actionKey = event.key
            pendingWindow = selected
        }
    }
    Keys.onReleased: event => {
        if (event.isAutoRepeat || event.key !== actionKey) return
        event.accepted = true
        const window = pendingWindow
        actionKey = 0
        pendingWindow = null
        if (Model.locate(rows, window)) activateRequested(window)
    }

    Rectangle { anchors.fill: parent; color: Theme.Palette.backgroundDark; radius: 10 }
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons }
    Flickable {
        id: viewport
        anchors.fill: parent
        anchors.margins: 16
        clip: true
        contentWidth: width
        contentHeight: contents.height
        onContentHeightChanged: Qt.callLater(root.ensureVisible)
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        Column {
            id: contents
            width: viewport.width
            spacing: 16
            Repeater {
                id: rowViews
                model: root.rows
                Column {
                    id: workspaceRow
                    required property var modelData
                    width: contents.width
                    spacing: 6
                    property alias list: cards
                    Text {
                        width: parent.width
                        text: "Workspace " + (workspaceRow.modelData.name || workspaceRow.modelData.id)
                        color: Theme.Palette.foreground
                        elide: Text.ElideRight
                        font.pixelSize: 16
                    }
                    ListView {
                        id: cards
                        width: parent.width
                        height: root.cardHeight + 12
                        orientation: ListView.Horizontal
                        spacing: 12
                        model: workspaceRow.modelData.windows
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.horizontal: ScrollBar {}
                        delegate: Rectangle {
                            id: card
                            required property var modelData
                            width: root.cardWidth
                            height: root.cardHeight
                            radius: 8
                            color: Theme.Palette.surface
                            border.width: root.selected === modelData ? 3 : 1
                            border.color: root.selected === modelData ? Theme.Palette.primary : Theme.Palette.border
                            readonly property string label: modelData.title || modelData.wayland?.appId
                                || modelData.lastIpcObject?.class || "Window"
                            Accessible.role: Accessible.Button
                            Accessible.name: label
                            Accessible.selected: root.selected === modelData
                            // ListView virtualises cards; offscreen delegates do not keep a capture alive.
                            readonly property bool inView: x + width > cards.contentX && x < cards.contentX + cards.width
                                && workspaceRow.y + workspaceRow.height > viewport.contentY
                                && workspaceRow.y < viewport.contentY + viewport.height
                            Loader {
                                id: preview
                                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 8 }
                                height: parent.height - 48
                                active: card.inView
                                sourceComponent: ScreencopyView {
                                    captureSource: card.modelData.wayland
                                    live: true
                                    // Composite captured alpha over the existing card surface.
                                    layer.enabled: true
                                    constraintSize: Qt.size(preview.width, preview.height)
                                    anchors.centerIn: parent
                                    width: implicitWidth
                                    height: implicitHeight
                                }
                            }
                            Text {
                                anchors.centerIn: preview
                                width: preview.width
                                visible: !preview.item?.hasContent
                                text: card.label
                                color: Theme.Palette.foregroundDark
                                horizontalAlignment: Text.AlignHCenter
                                wrapMode: Text.Wrap
                                maximumLineCount: 3
                                elide: Text.ElideRight
                            }
                            Text {
                                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 10 }
                                text: card.label
                                color: Theme.Palette.foreground
                                elide: Text.ElideRight
                                font.pixelSize: 14
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: { root.selected = card.modelData; root.forceActiveFocus() }
                                onDoubleClicked: root.activateRequested(card.modelData)
                            }
                        }
                    }
                }
            }
        }
    }
    Text {
        anchors.centerIn: parent
        visible: root.rows.length === 0
        text: "No windows on this monitor"
        color: Theme.Palette.foreground
    }
}
