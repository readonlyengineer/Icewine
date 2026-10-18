pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Widgets
import "LauncherSearch.js" as LauncherSearch
import qs.icewine.theme as Theme

Card {
    id: root

    property bool engaged: false
    signal handoffRequested()
    initialFocus: search

    property bool excludeSteamApps: false

    SteamShortcuts { id: steamShortcuts }

    function focusInitial() {
        search.forceActiveFocus(Qt.ShortcutFocusReason)
    }

    function launch(entry) {
        if (!entry || !active)
            return

        handoffRequested()
        Quickshell.execDetached(LauncherSearch.launchOptions(entry, Quickshell.env("HOME")))
    }

    onActiveChanged: {
        if (active && excludeSteamApps)
            steamShortcuts.refresh()
    }
    onVisibleChanged: if (!visible) search.text = ""
    onSelectedChanged: if (!selected) search.text = ""

    implicitWidth: 400
    implicitHeight: 424

    Item {
        id: surface

        anchors.fill: parent
        enabled: root.active

        Rectangle {
            id: searchFrame

            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
                margins: 12
            }
            height: 38
            radius: 10
            color: Theme.Palette.surface

            Text {
                id: searchIcon

                anchors.left: parent.left
                anchors.leftMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                text: ""
                color: search.activeFocus ? root.accent : Theme.Palette.muted
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

        ListView {
            id: results

            anchors {
                top: searchFrame.bottom
                left: parent.left
                right: parent.right
                bottom: parent.bottom
                topMargin: 8
                leftMargin: 12
                rightMargin: 12
                bottomMargin: 12
            }
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

    }

}
