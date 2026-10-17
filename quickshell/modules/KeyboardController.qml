pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "KeyboardModel.js" as Model

Scope {
    id: root
    required property var compositor
    required property var session
    property bool desktopVisible: false
    property var output: null
    property var destination: null
    property bool controllerReady: true
    property string controllerError: ""
    property string error: ""
    onControllerReadyChanged: if (!controllerReady) desktopKeyboard.cancel()
    property bool pending: false
    property string deliveryInput: ""
    readonly property bool busy: delivery.running || pending
    readonly property var view: session.locked ? session.keyboardView : desktopKeyboard
    readonly property bool visible: session.locked ? session.keyboardVisible : desktopVisible

    function show() {
        if (session.locked) { session.toggleKeyboard(session.keyboardHost); return }
        const target = compositor.toplevels.find(window => window.address === compositor.activeWindowAddress)
        const screen = Quickshell.screens.find(screen => compositor.monitorFor(screen)?.focused) ?? Quickshell.screens[0]
        if (!target || !screen || busy) return
        destination = target
        output = screen
        error = ""
        desktopVisible = true
    }
    signal hiding()
    function prepareHide() { hiding() }
    function hide() {
        if (visible) prepareHide()
        desktopVisible = false
        desktopKeyboard.cancel()
        if (session.keyboardEnabled) { session.keyboardEnabled = false; session.keyboardView.cancel(); Qt.inputMethod.hide() }
    }
    function toggle() { if (visible) hide(); else show() }
    function send(action) {
        // No queue: a child owns one complete key/chord. A busy repeat is dropped.
        if (!controllerReady || error !== "" || busy || !desktopVisible || session.locked || !destination
                || !compositor.toplevels.includes(destination)
                || compositor.activeWindowAddress !== destination.address) return
        pending = true
        deliveryInput = Model.command(action).join(" ") + "\n"
        delivery.running = true
    }
    function controller(event) { if (visible) view.controller(event) }
    Connections {
        target: root.compositor
        function onActiveWindowAddressChanged() {
            if (root.desktopVisible && root.compositor.activeWindowAddress !== root.destination?.address) root.hide()
        }
    }
    Connections {
        target: root.session
        function onLockedChanged() { root.desktopVisible = false; desktopKeyboard.cancel() }
    }
    Connections {
        target: Quickshell
        function onScreensChanged() { if (root.desktopVisible && !Quickshell.screens.includes(root.output)) root.hide() }
    }
    Process {
        id: delivery
        // QS prints command argv on FailedToStart. Keep it constant; only the
        // generated whitespace-free tokens go over stdin. No eval or globbing.
        command: ["sh", "-c", 'IFS= read -r args || exit 1; set -f; exec $args >/dev/null 2>&1']
        stdinEnabled: true
        onStarted: { write(root.deliveryInput); root.deliveryInput = "" }
        onRunningChanged: if (!running && root.pending && !settling.running) {
            // FailedToStart emits runningChanged, but no exited signal.
            root.deliveryInput = ""
            root.error = qsTr("Input failed; close and reopen the keyboard")
            desktopKeyboard.cancel()
            settling.restart()
        }
        // wtype roundtrips its explicit key-up and final modifier clears. Let
        // finite work settle on hide/focus changes; never replay it.
        onExited: (code, status) => {
            // Ponytail: this gives queued Qt input time to drain, not a compositor
            // fence. Use a supported compositor acknowledgement if device checks
            // expose late delivery; finite chords are not focus transactions.
            settling.restart()
            if (code !== 0 || status !== 0) {
                root.error = qsTr("Input failed; close and reopen the keyboard")
                desktopKeyboard.cancel()
            }
        }
    }
    Timer { id: settling; interval: 50; onTriggered: root.pending = false }
    PanelWindow {
        screen: root.output ?? Quickshell.screens[0]
        visible: root.desktopVisible && !root.session.locked
        anchors { top: true; bottom: true; left: true; right: true }
        color: "transparent"
        exclusiveZone: 0
        WlrLayershell.namespace: "icewine:keyboard"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        mask: Region { item: desktopKeyboard }
        KeyboardView {
            id: desktopKeyboard
            visible: root.desktopVisible
            busy: root.busy || root.error !== "" || !root.controllerReady
            error: root.error || root.controllerError || (!root.controllerReady ? qsTr("Capturing controller…") : "")
            onActivated: action => root.send(action)
            onHideRequested: root.hide()
        }
    }
    IpcHandler {
        target: "keyboard"
        function toggle(): void { root.toggle() }
        function hide(): void { root.hide() }
        function status(): string { return JSON.stringify({visible: root.visible, busy: root.busy, error: root.error}) }
    }
}
