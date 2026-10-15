pragma ComponentBehavior: Bound
import QtQuick
import "popouts" as Popouts
import "Layouts.js" as Layouts

Popouts.ActionButton {
    id: root
    required property var compositor
    signal activated()
    implicitHeight: 26
    implicitWidth: label.implicitWidth + 18
    text: "▥ " + (compositor.layoutAvailable
        ? Layouts.label(compositor.layoutStatus.effective) : "Layout")
    onClicked: activated()
    Accessible.name: "Workspace layout: " + text
    // Measure using the inherited font without changing the shared button.
    Text { id: label; visible: false; text: root.text; font: root.font }
}
