pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Services.SystemTray
import Quickshell.Widgets
import "BackgroundAppsModel.js" as BackgroundAppsModel
import qs.icewine.theme as Theme

FocusScope {
    id: root

    property var items: []
    property var activeItem: null
    property var menuPath: []
    readonly property var menuHandle: menuPath.length > 0
        ? menuPath[menuPath.length - 1] : activeItem?.menu ?? null
    readonly property string menuTitle: menuPath.length > 0
        ? String(menuPath[menuPath.length - 1].text)
        : String(activeItem?.title || activeItem?.id || "Application")

    signal backRequested()
    signal handoffRequested()

    function focusInitial() {
        apps.currentIndex = apps.count > 0 ? 0 : -1
        apps.forceActiveFocus()
    }

    function focusMenu() {
        Qt.callLater(() => {
            menuEntries.currentIndex = firstMenuIndex()
            menuEntries.forceActiveFocus()
        })
    }

    function firstMenuIndex() {
        return BackgroundAppsModel.nextEnabled(menuOpener.children.values, -1, 1)
    }

    function moveMenu(step) {
        const entries = menuOpener.children.values
        const index = BackgroundAppsModel.nextEnabled(
            entries, menuEntries.currentIndex, step)
        if (index < 0)
            return

        menuEntries.currentIndex = index
        menuEntries.positionViewAtIndex(index, ListView.Contain)
    }

    function openItem(item) {
        if (!item)
            return
        if (!item.hasMenu) {
            item.activate()
            handoffRequested()
            return
        }

        activeItem = item
        menuPath = []
        focusMenu()
    }

    function trigger(entry) {
        if (!entry || entry.isSeparator || !entry.enabled)
            return
        if (entry.hasChildren) {
            menuPath = menuPath.concat([entry])
            focusMenu()
        } else {
            entry.triggered()
            handoffRequested()
        }
    }

    function back() {
        if (menuPath.length > 0) {
            menuPath = menuPath.slice(0, -1)
            focusMenu()
        } else if (activeItem) {
            activeItem = null
            focusInitial()
        } else {
            backRequested()
        }
    }

    onItemsChanged: {
        if (!activeItem || items.indexOf(activeItem) === -1) {
            activeItem = null
            menuPath = []
        }
    }

    QsMenuOpener {
        id: menuOpener
        menu: root.menuHandle
    }

    ListView {
        id: apps

        property int activationKey: 0
        onActiveFocusChanged: if (!activeFocus) activationKey = 0

        anchors.fill: parent
        visible: !root.activeItem
        clip: true
        spacing: 4
        keyNavigationWraps: true
        model: root.items

        Keys.onDownPressed: incrementCurrentIndex()
        Keys.onUpPressed: decrementCurrentIndex()
        Keys.onReturnPressed: event => { if (!event.isAutoRepeat) apps.activationKey = event.key }
        Keys.onEnterPressed: event => { if (!event.isAutoRepeat) apps.activationKey = event.key }
        Keys.onReleased: event => {
            if (event.isAutoRepeat || event.key !== apps.activationKey)
                return
            event.accepted = true
            apps.activationKey = 0
            root.openItem(currentItem?.trayEntry)
        }
        Keys.onEscapePressed: root.back()

        delegate: Rectangle {
            id: app

            required property var modelData
            required property int index
            readonly property var trayEntry: modelData

            width: ListView.view.width
            height: 48
            radius: 9
            color: index === apps.currentIndex
                ? Theme.Palette.selection : "transparent"

            IconImage {
                anchors.left: parent.left
                anchors.leftMargin: 9
                anchors.verticalCenter: parent.verticalCenter
                implicitSize: 26
                source: app.modelData.icon
            }

            Column {
                anchors.left: parent.left
                anchors.leftMargin: 45
                anchors.right: actionHint.left
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                spacing: 1

                Text {
                    width: parent.width
                    text: app.modelData.title || app.modelData.id
                    color: Theme.Palette.foreground
                    font.family: "JetBrainsMono Nerd Font"
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }

                Text {
                    width: parent.width
                    text: app.modelData.status === Status.NeedsAttention
                        ? "Needs attention" : "Running"
                    color: app.modelData.status === Status.NeedsAttention
                        ? Theme.Palette.error : Theme.Palette.muted
                    font.family: "JetBrainsMono Nerd Font"
                    font.pixelSize: 9
                }
            }

            Text {
                id: actionHint

                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                text: app.modelData.hasMenu ? "Actions  ›" : "Open  ›"
                color: Theme.Palette.secondary
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 10
            }

            HoverHandler {
                id: appHover
                cursorShape: Qt.PointingHandCursor
                onHoveredChanged: {
                    if (hovered)
                        apps.currentIndex = app.index
                }
            }

            TapHandler {
                onTapped: root.openItem(app.trayEntry)
            }

            Behavior on color {
                ColorAnimation { duration: 100 }
            }
        }
    }

    Text {
        id: menuTitle

        anchors {
            top: parent.top
            left: parent.left
            right: parent.right
        }
        visible: !!root.activeItem
        height: visible ? 28 : 0
        text: root.menuTitle
        color: Theme.Palette.secondary
        font.family: "JetBrainsMono Nerd Font"
        font.pixelSize: 10
        font.bold: true
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    ListView {
        id: menuEntries

        property int activationKey: 0
        onActiveFocusChanged: if (!activeFocus) activationKey = 0

        anchors {
            top: menuTitle.bottom
            left: parent.left
            right: parent.right
            bottom: parent.bottom
        }
        visible: !!root.activeItem
        clip: true
        spacing: 4
        model: menuOpener.children

        onCountChanged: {
            if (visible && currentIndex < 0)
                currentIndex = root.firstMenuIndex()
        }

        Keys.onDownPressed: root.moveMenu(1)
        Keys.onUpPressed: root.moveMenu(-1)
        Keys.onRightPressed: event => { if (!event.isAutoRepeat) menuEntries.activationKey = event.key }
        Keys.onLeftPressed: root.back()
        Keys.onReturnPressed: event => { if (!event.isAutoRepeat) menuEntries.activationKey = event.key }
        Keys.onEnterPressed: event => { if (!event.isAutoRepeat) menuEntries.activationKey = event.key }
        Keys.onReleased: event => {
            if (event.isAutoRepeat || event.key !== menuEntries.activationKey)
                return
            event.accepted = true
            menuEntries.activationKey = 0
            root.trigger(currentItem?.menuEntry)
        }
        Keys.onEscapePressed: root.back()

        delegate: Rectangle {
            id: entry

            required property var modelData
            required property int index
            readonly property var menuEntry: modelData
            readonly property bool selectable: !modelData.isSeparator && modelData.enabled

            width: ListView.view.width
            height: modelData.isSeparator ? 5 : 38
            radius: 8
            color: selectable && index === menuEntries.currentIndex
                ? Theme.Palette.selection : "transparent"

            Rectangle {
                anchors.centerIn: parent
                visible: entry.modelData.isSeparator
                width: parent.width - 12
                height: 1
                color: Theme.Palette.alpha(Theme.Palette.secondary, 0.35)
            }

            IconImage {
                id: entryIcon

                anchors.left: parent.left
                anchors.leftMargin: 9
                anchors.verticalCenter: parent.verticalCenter
                visible: !entry.modelData.isSeparator && entry.modelData.icon !== ""
                implicitSize: 18
                source: entry.modelData.icon
            }

            Text {
                anchors.left: parent.left
                anchors.leftMargin: entryIcon.visible ? 35 : 10
                anchors.right: submenuIndicator.left
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                visible: !entry.modelData.isSeparator
                text: entry.modelData.text
                color: entry.modelData.enabled
                    ? Theme.Palette.foreground : Theme.Palette.muted
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 10
                elide: Text.ElideRight
            }

            Text {
                id: submenuIndicator

                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                visible: !entry.modelData.isSeparator && entry.modelData.hasChildren
                text: "›"
                color: Theme.Palette.secondary
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 13
            }

            HoverHandler {
                id: entryHover
                enabled: entry.selectable
                cursorShape: Qt.PointingHandCursor
                onHoveredChanged: {
                    if (hovered)
                        menuEntries.currentIndex = entry.index
                }
            }

            TapHandler {
                enabled: entry.selectable
                onTapped: root.trigger(entry.menuEntry)
            }

            Behavior on color {
                ColorAnimation { duration: 100 }
            }
        }
    }
}
