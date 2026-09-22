pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Services.Pipewire
import qs.theme as Theme

Flickable {
    id: root

    readonly property Item initialFocus: outputMute
    readonly property var sink: Pipewire.defaultAudioSink
    readonly property var source: Pipewire.defaultAudioSource
    readonly property var sinks: Pipewire.nodes.values.filter(node =>
        node.audio && node.isSink && !node.isStream)
    readonly property var sources: Pipewire.nodes.values.filter(node =>
        node.audio && !node.isSink && !node.isStream)

    signal advancedRequested(string tool)

    contentHeight: content.implicitHeight + 24
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    PwObjectTracker {
        objects: root.sinks.concat(root.sources)
    }

    Column {
        id: content

        x: 12
        y: 12
        width: root.width - 24
        spacing: 7

        Text {
            text: "Audio"
            color: Theme.Palette.primary
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 15
            font.bold: true
        }

        Toggle {
            id: outputMute

            width: parent.width
            text: "Output muted"
            enabled: !!root.sink?.audio
            checked: root.sink?.audio?.muted ?? true
            onToggled: {
                if (root.sink?.audio)
                    root.sink.audio.muted = checked
            }
        }

        Text {
            text: `Output volume  ${Math.round((root.sink?.audio?.volume ?? 0) * 100)}%`
            color: Theme.Palette.foreground
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 11
        }

        Slider {
            width: parent.width
            enabled: !!root.sink?.audio
            value: root.sink?.audio?.volume ?? 0
            onMoved: {
                if (root.sink?.audio) {
                    root.sink.audio.volume = value
                    root.sink.audio.muted = false
                }
            }
        }

        SectionLabel { text: "Output device" }

        Repeater {
            model: ScriptModel { values: root.sinks }

            DeviceRow {
                required property var modelData

                width: content.width
                label: modelData.description || modelData.nickname || modelData.name
                selected: root.sink?.id === modelData.id
                onActivated: Pipewire.preferredDefaultAudioSink = modelData
            }
        }

        Toggle {
            width: parent.width
            text: "Input muted"
            enabled: !!root.source?.audio
            checked: root.source?.audio?.muted ?? true
            onToggled: {
                if (root.source?.audio)
                    root.source.audio.muted = checked
            }
        }

        Text {
            text: `Input volume  ${Math.round((root.source?.audio?.volume ?? 0) * 100)}%`
            color: Theme.Palette.foreground
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 11
        }

        Slider {
            width: parent.width
            enabled: !!root.source?.audio
            value: root.source?.audio?.volume ?? 0
            onMoved: {
                if (root.source?.audio) {
                    root.source.audio.volume = value
                    root.source.audio.muted = false
                }
            }
        }

        SectionLabel { text: "Input device" }

        Repeater {
            model: ScriptModel { values: root.sources }

            DeviceRow {
                required property var modelData

                width: content.width
                label: modelData.description || modelData.nickname || modelData.name
                selected: root.source?.id === modelData.id
                onActivated: Pipewire.preferredDefaultAudioSource = modelData
            }
        }

        ActionButton {
            width: parent.width
            text: "Advanced · wiremix"
            onClicked: root.advancedRequested("wiremix")
        }
    }

    component SectionLabel: Text {
        topPadding: 5
        color: Theme.Palette.muted
        font.family: "JetBrainsMono Nerd Font"
        font.pixelSize: 10
    }

    component DeviceRow: Rectangle {
        id: deviceRow

        required property string label
        required property bool selected
        signal activated()

        height: 34
        activeFocusOnTab: true
        radius: 9
        color: selected ? Theme.Palette.selection
            : deviceHover.hovered ? Theme.Palette.surface : "transparent"
        border.width: activeFocus ? 1 : 0
        border.color: Theme.Palette.primary

        Keys.onReturnPressed: deviceRow.activated()
        Keys.onEnterPressed: deviceRow.activated()
        Keys.onSpacePressed: deviceRow.activated()
        Keys.onDownPressed: deviceRow.nextItemInFocusChain(true).forceActiveFocus(Qt.TabFocusReason)
        Keys.onUpPressed: deviceRow.nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 10
            anchors.right: marker.left
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            text: deviceRow.label
            color: deviceRow.selected ? Theme.Palette.primary : Theme.Palette.foreground
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 11
            elide: Text.ElideRight
        }

        Text {
            id: marker

            anchors.right: parent.right
            anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            text: deviceRow.selected ? "●" : "○"
            color: deviceRow.selected ? Theme.Palette.primary : Theme.Palette.muted
            font.pixelSize: 10
        }

        HoverHandler { id: deviceHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: deviceRow.activated() }
    }
}
