import QtQuick
import QtQuick.VirtualKeyboard.Styles
import qs.icewine.theme as Theme

KeyboardStyle {
    id: root
    keyboardDesignWidth: 900
    keyboardDesignHeight: 300
    keyboardBackground: Rectangle {
        objectName: "icewineKeyboardBackground"
        color: Theme.Palette.backgroundDark
    }
    component NativeKey: KeyPanel {
        id: key
        objectName: "icewineKeyboardKey"
        property string label: control.displayText
        Rectangle {
            anchors.fill: parent
            anchors.margins: 3 * root.scaleHint
            radius: 4 * root.scaleHint
            color: key.control.pressed ? Theme.Palette.selection : Theme.Palette.surface
            border.color: Theme.Palette.border
            Text {
                anchors.centerIn: parent
                width: parent.width - 4 * root.scaleHint
                text: key.label
                color: Theme.Palette.foreground
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 20 * root.scaleHint
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
            }
        }
    }
    keyPanel: NativeKey {}
    backspaceKeyPanel: NativeKey { label: "⌫" }
    languageKeyPanel: NativeKey { label: "Lang" }
    enterKeyPanel: NativeKey { label: "↵" }
    hideKeyPanel: NativeKey { label: "Hide" }
    shiftKeyPanel: NativeKey { label: control.uppercased ? "⇪" : "⇧" }
    spaceKeyPanel: NativeKey { label: "Space" }
    symbolKeyPanel: NativeKey { label: control.displayText || "?123" }
    modeKeyPanel: NativeKey {}
    handwritingKeyPanel: NativeKey { label: "Write" }
    alternateKeysListItemWidth: 48 * scaleHint
    alternateKeysListItemHeight: 48 * scaleHint
    alternateKeysListDelegate: Text {
        width: root.alternateKeysListItemWidth
        height: root.alternateKeysListItemHeight
        text: model.text
        color: Theme.Palette.foreground
        font.pixelSize: 20 * root.scaleHint
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    alternateKeysListHighlight: Rectangle { color: Theme.Palette.selection }
    alternateKeysListBackground: Rectangle { color: Theme.Palette.backgroundDark }
    selectionListHeight: 40 * scaleHint
    selectionListDelegate: SelectionListItem {
        width: candidate.implicitWidth + 20 * root.scaleHint
        Text {
            id: candidate
            anchors.centerIn: parent
            text: display
            color: Theme.Palette.foreground
            font.pixelSize: 20 * root.scaleHint
        }
    }
    selectionListHighlight: Rectangle { color: Theme.Palette.selection }
    selectionListBackground: Rectangle { color: Theme.Palette.backgroundDark }
    navigationHighlight: Rectangle { color: "transparent"; border.color: Theme.Palette.primary; border.width: 2 }
}
