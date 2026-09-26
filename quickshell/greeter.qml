import Quickshell
import Quickshell.Wayland
import QtQuick.VirtualKeyboard
import "modules" as Modules

ShellRoot {
    Modules.Greeter {
        id: greeter
        keyboardHeight: keyboard.height
    }

    InputPanel {
        id: keyboard
        parent: greeter.keyboardHost
        width: parent?.width ?? 0
        y: (parent?.height ?? 0) - height
        z: 100
        visible: active && parent !== null
    }

    Variants {
        model: Quickshell.screens

        PanelWindow {
            required property var modelData
            screen: modelData
            color: "#000000"
            anchors { top: true; bottom: true; left: true; right: true }
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.namespace: "icewine:greeter"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

            Modules.WinterScreen {
                anchors.fill: parent
                controller: greeter
            }
        }
    }
}
