pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import "notifications" as NotificationParts
import "notifications/Model.js" as NotificationModel

Scope {
    id: root

    required property var compositor
    required property var notificationService
    readonly property var focusedScreen: Quickshell.screens.find(screen =>
        compositor.monitorFor(screen)?.focused) ?? Quickshell.screens[0]

    PanelWindow {
        id: window

        screen: root.focusedScreen
        visible: root.notificationService.popups.length > 0
        implicitWidth: 380
        implicitHeight: Math.min(toasts.implicitHeight, (screen?.height ?? 480) - 24)
        exclusiveZone: 0
        color: "transparent"

        anchors.top: true
        margins.top: 12

        WlrLayershell.namespace: "quickshell:notifications"
        WlrLayershell.exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay

        Item {
            id: toasts

            anchors.fill: parent
            clip: true

            implicitHeight: stack.implicitHeight

            Column {
                id: stack

                width: parent.width
                spacing: 8

                Repeater {
                    model: ScriptModel {
                        values: root.notificationService.popups.slice(0, 3)
                    }

                    delegate: Item {
                        id: toast

                        required property var modelData
                        property bool entered: false

                        width: stack.width
                        height: card.implicitHeight
                        opacity: entered ? 1 : 0
                        scale: entered ? 1 : 0.85

                        Component.onCompleted: entered = true

                        NotificationParts.NotificationCard {
                            id: card

                            width: parent.width
                            notification: toast.modelData
                            compositor: root.compositor
                            onDismissRequested: toast.modelData.dismiss()
                            onSourceRequested: address => {
                                toast.modelData.dismiss()
                                root.compositor.activateWindow(address)
                            }
                        }

                        Timer {
                            interval: NotificationModel.toastTimeout(
                                toast.modelData.urgency, toast.modelData.expireTimeout)
                            running: interval > 0
                            onTriggered: root.notificationService.hidePopup(toast.modelData)
                        }

                        Behavior on opacity {
                            NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
                        }

                        Behavior on scale {
                            NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
                        }

                        Behavior on y {
                            NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
                        }
                    }
                }
            }
        }
    }
}
