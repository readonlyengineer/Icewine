pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import QtQuick.Controls

Card {
    id: root
    required property var compositor
    readonly property bool layoutActive: active
    accessibleName: "Workspace layout"
    function revealFocus() {
        const item = root.Window.window?.activeFocusItem
        let owner = item
        while (owner && owner !== picker) owner = owner.parent
        if (!active || !owner) return
        const scroll = layoutScroll.contentItem
        const top = item.mapToItem(scroll.contentItem, 0, 0).y
        const bottom = top + item.height
        const target = top < scroll.contentY ? top
            : bottom > scroll.contentY + scroll.height ? bottom - scroll.height : scroll.contentY
        scroll.contentY = Math.max(0, Math.min(target, Math.max(0, scroll.contentHeight - scroll.height)))
    }
    onHeightChanged: Qt.callLater(revealFocus)
    Connections {
        target: root.Window.window
        function onActiveFocusItemChanged() { Qt.callLater(root.revealFocus) }
    }
    implicitWidth: 400
    implicitHeight: 424
    initialFocus: picker.available && root.active ? picker.initialFocus : selector
    ScrollView {
        id: layoutScroll
        // Let ordinary controls navigate before ScrollView consumes arrows to scroll.
        Keys.onPressed: event => root.navigate(event)
        anchors.fill: parent
        enabled: root.active
        clip: true
        contentWidth: availableWidth
        LayoutPicker {
            id: picker
            width: layoutScroll.availableWidth
            compositor: root.compositor
            accent: root.accent
        }
    }
}
