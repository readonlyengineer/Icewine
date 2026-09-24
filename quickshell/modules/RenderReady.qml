import QtQuick

QtObject {
    id: root

    required property Item item
    signal ready()

    property Connections frame: Connections {
        target: root.item.Window.window
        enabled: !root.readyReported
        function onFrameSwapped() {
            root.readyReported = true
            root.ready()
        }
    }
    property bool readyReported: false
}
