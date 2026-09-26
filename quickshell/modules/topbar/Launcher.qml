pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Services.SystemTray
import Quickshell.Widgets
import "LauncherSearch.js" as LauncherSearch
import qs.theme as Theme

Widget {
    id: root

    property bool showingBackground: false
    property bool excludeSteamApps: false

    SteamShortcuts { id: steamShortcuts }
    readonly property var backgroundItems: SystemTray.items.values
    readonly property int backgroundCount: backgroundItems.length
    readonly property bool backgroundAttention: backgroundItems.some(
        item => item.status === Status.NeedsAttention)

    function focusInitial() {
        search.forceActiveFocus(Qt.ShortcutFocusReason)
    }

    function showBackground() {
        if (backgroundCount === 0)
            return
        showingBackground = true
    }

    function hideBackground() {
        showingBackground = false
        Qt.callLater(() => {
            if (root.visible && root.engaged)
                search.forceActiveFocus()
        })
    }

    function launch(entry) {
        if (!entry || !visible)
            return

        handoffRequested()
        Quickshell.execDetached(LauncherSearch.launchOptions(entry, Quickshell.env("HOME")))
    }

    onVisibleChanged: {
        if (visible && excludeSteamApps)
            steamShortcuts.refresh()
        if (!visible) {
            search.text = ""
            showingBackground = false
        }
    }
    onBackgroundCountChanged: {
        if (backgroundCount === 0 && showingBackground)
            hideBackground()
    }

    width: 400
    height: 424

    Rectangle {
        id: surface

        anchors.fill: parent
        radius: 12
        color: Theme.Palette.backgroundDark

        Rectangle {
            id: searchFrame

            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
                margins: 12
            }
            visible: !root.showingBackground
            height: 38
            radius: 10
            color: Theme.Palette.surface

            Text {
                id: searchIcon

                anchors.left: parent.left
                anchors.leftMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                text: ""
                color: search.activeFocus ? Theme.Palette.primary : Theme.Palette.muted
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 13
            }

            TextInput {
                id: search

                property int launchKey: 0
                onActiveFocusChanged: if (!activeFocus) launchKey = 0

                anchors {
                    left: searchIcon.right
                    right: parent.right
                    verticalCenter: parent.verticalCenter
                    leftMargin: 9
                    rightMargin: 12
                }
                color: Theme.Palette.foreground
                selectionColor: Theme.Palette.primaryDark
                selectedTextColor: Theme.Palette.foreground
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 13
                clip: true

                Keys.onDownPressed: results.incrementCurrentIndex()
                Keys.onUpPressed: results.decrementCurrentIndex()
                Keys.onReturnPressed: event => { if (!event.isAutoRepeat) search.launchKey = event.key }
                Keys.onEnterPressed: event => { if (!event.isAutoRepeat) search.launchKey = event.key }
                Keys.onReleased: event => {
                    if (event.isAutoRepeat || event.key !== search.launchKey)
                        return
                    event.accepted = true
                    search.launchKey = 0
                    root.launch(results.currentItem?.entry)
                }

                Text {
                    anchors.fill: parent
                    visible: search.text.length === 0
                    text: "Search applications"
                    color: Theme.Palette.muted
                    font: search.font
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }

        Rectangle {
            id: backgroundHeader

            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
                margins: 12
            }
            visible: root.showingBackground
            height: 38
            radius: 10
            color: headerHover.hovered ? Theme.Palette.selection : Theme.Palette.surface

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                text: "←  Background applications"
                color: Theme.Palette.foreground
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 12
            }

            HoverHandler {
                id: headerHover
                cursorShape: Qt.PointingHandCursor
            }

            TapHandler {
                onTapped: backgroundPage.item?.back()
            }

            Behavior on color {
                ColorAnimation { duration: 100 }
            }
        }

        ListView {
            id: results

            anchors {
                top: searchFrame.bottom
                left: parent.left
                right: parent.right
                bottom: backgroundFooter.top
                topMargin: 8
                leftMargin: 12
                rightMargin: 12
                bottomMargin: backgroundFooter.visible ? 8 : 0
            }
            visible: !root.showingBackground
            clip: true
            spacing: 4
            currentIndex: count > 0 ? 0 : -1

            model: ScriptModel {
                values: LauncherSearch.applications(
                    DesktopEntries.applications.values, search.text,
                    root.excludeSteamApps, steamShortcuts.commands)
                onValuesChanged: results.currentIndex = values.length > 0 ? 0 : -1
            }

            delegate: Rectangle {
                id: result

                required property var modelData
                required property int index
                readonly property var entry: modelData

                width: ListView.view.width
                height: 48
                radius: 9
                color: index === results.currentIndex
                    ? Theme.Palette.selection : "transparent"

                HoverHandler {
                    id: resultHover
                    cursorShape: Qt.PointingHandCursor
                    onHoveredChanged: {
                        if (hovered)
                            results.currentIndex = result.index
                    }
                }

                TapHandler {
                    onTapped: root.launch(result.entry)
                }

                IconImage {
                    id: appIcon

                    anchors.left: parent.left
                    anchors.leftMargin: 9
                    anchors.verticalCenter: parent.verticalCenter
                    implicitSize: 30
                    source: Quickshell.iconPath(result.entry.icon, "application-x-executable")
                }

                Column {
                    anchors.left: appIcon.right
                    anchors.leftMargin: 10
                    anchors.right: parent.right
                    anchors.rightMargin: 9
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 1

                    Text {
                        width: parent.width
                        text: result.entry.name
                        color: Theme.Palette.foreground
                        font.family: "JetBrainsMono Nerd Font"
                        font.pixelSize: 12
                        elide: Text.ElideRight
                    }

                    Text {
                        width: parent.width
                        text: result.entry.comment || result.entry.genericName || ""
                        color: Theme.Palette.muted
                        font.family: "JetBrainsMono Nerd Font"
                        font.pixelSize: 10
                        elide: Text.ElideRight
                    }
                }

                Behavior on color {
                    ColorAnimation { duration: 100 }
                }
            }
        }

        Rectangle {
            id: backgroundFooter

            anchors {
                left: parent.left
                right: parent.right
                bottom: parent.bottom
                leftMargin: 12
                rightMargin: 12
                bottomMargin: 12
            }
            visible: !root.showingBackground && search.text.length === 0
                && root.backgroundCount > 0
            activeFocusOnTab: visible
            height: visible ? 38 : 0
            radius: 10
            color: footerHover.hovered || activeFocus
                ? Theme.Palette.selection : Theme.Palette.surface
            border.width: activeFocus ? 1 : 0
            border.color: Theme.Palette.primary

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                text: "  Background applications"
                color: Theme.Palette.foreground
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 11
            }

            Text {
                anchors.right: parent.right
                anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                text: root.backgroundCount + "  ›"
                color: Theme.Palette.secondary
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 11
            }

            HoverHandler {
                id: footerHover
                cursorShape: Qt.PointingHandCursor
            }

            TapHandler {
                onTapped: root.showBackground()
            }

            Keys.onReturnPressed: root.showBackground()
            Keys.onEnterPressed: root.showBackground()
            Keys.onSpacePressed: root.showBackground()

            Behavior on color {
                ColorAnimation { duration: 100 }
            }
        }

        Loader {
            id: backgroundPage

            anchors {
                top: backgroundHeader.bottom
                left: parent.left
                right: parent.right
                bottom: parent.bottom
                topMargin: 8
                leftMargin: 12
                rightMargin: 12
                bottomMargin: 12
            }
            active: root.showingBackground
            sourceComponent: BackgroundApps {
                items: root.backgroundItems
            }
            onLoaded: item.focusInitial()
        }

        Connections {
            target: backgroundPage.item

            function onBackRequested() {
                root.hideBackground()
            }

            function onHandoffRequested() {
                root.handoffRequested()
            }
        }
    }

}
