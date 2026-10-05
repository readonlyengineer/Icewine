pragma ComponentBehavior: Bound

import QtQuick
import qs.icewine.theme as Theme

Flickable {
    id: root

    required property var player
    readonly property Item initialFocus: playPause
    signal raiseRequested()

    implicitHeight: contentHeight
    contentHeight: content.implicitHeight + 32
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    Timer {
        running: root.visible && (root.player?.isPlaying ?? false)
        interval: 1000
        repeat: true
        onTriggered: root.player?.positionChanged()
    }

    Column {
        id: content
        x: 16
        y: 16
        width: root.width - 32
        spacing: 8

        Text {
            width: parent.width
            text: "Now Playing"
            color: Theme.Palette.primary
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 15
            font.bold: true
        }

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 144
            height: 144
            radius: 12
            color: Theme.Palette.surface
            clip: true

            TapHandler {
                enabled: root.player?.canRaise ?? false
                onTapped: root.raiseRequested()
            }
            HoverHandler { cursorShape: root.player?.canRaise ? Qt.PointingHandCursor : Qt.ArrowCursor }

            Image {
                id: artwork

                anchors.fill: parent
                source: root.player?.trackArtUrl ?? ""
                asynchronous: true
                cache: true
                fillMode: Image.PreserveAspectCrop
            }

            Text {
                anchors.centerIn: parent
                visible: artwork.status !== Image.Ready
                text: "󰎆"
                color: Theme.Palette.muted
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 38
            }
        }

        Text {
            width: parent.width
            text: root.player?.trackTitle || "Unknown track"
            color: Theme.Palette.foreground
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 13
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            font.underline: activeFocus

            activeFocusOnTab: root.player?.canRaise ?? false
            Accessible.role: Accessible.Button
            Accessible.name: "Show " + (root.player?.identity || "media player")
            Accessible.onPressAction: if (root.player?.canRaise) root.raiseRequested()
            property int activationKey: 0
            onActiveFocusChanged: if (!activeFocus) activationKey = 0
            Keys.onReturnPressed: event => { if (!event.isAutoRepeat) activationKey = event.key }
            Keys.onSpacePressed: event => { if (!event.isAutoRepeat) activationKey = event.key }
            Keys.onReleased: event => {
                if (event.isAutoRepeat || event.key !== activationKey) return
                event.accepted = true
                activationKey = 0
                if (root.player?.canRaise) root.raiseRequested()
            }
            TapHandler {
                enabled: root.player?.canRaise ?? false
                onTapped: root.raiseRequested()
            }
            HoverHandler { cursorShape: root.player?.canRaise ? Qt.PointingHandCursor : Qt.ArrowCursor }
        }

        Text {
            width: parent.width
            text: root.player?.trackArtist || root.player?.identity || "Unknown artist"
            color: Theme.Palette.muted
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 10
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
        }

        Slider {
            width: parent.width
            enabled: (root.player?.canSeek && root.player?.positionSupported
                && root.player?.length > 0) ?? false
            value: root.player?.length > 0 ? root.player.position / root.player.length : 0
            onMoved: root.player.position = value * root.player.length
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 7

            ActionButton {
                width: 72
                text: ""
                Accessible.name: "Previous track"
                enabled: root.player?.canGoPrevious ?? false
                onClicked: root.player.previous()
            }

            ActionButton {
                id: playPause

                width: 86
                text: root.player?.isPlaying ? "" : ""
                Accessible.name: root.player?.isPlaying ? "Pause" : "Play"
                enabled: root.player?.canTogglePlaying ?? false
                onClicked: root.player.togglePlaying()
            }

            ActionButton {
                width: 72
                text: ""
                Accessible.name: "Next track"
                enabled: root.player?.canGoNext ?? false
                onClicked: root.player.next()
            }
        }
    }
}
