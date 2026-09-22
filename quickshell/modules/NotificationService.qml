pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Services.Notifications
import "notifications/Model.js" as NotificationModel

Scope {
    id: root

    readonly property var items: [...server.trackedNotifications.values].reverse()
    readonly property int count: items.length
    readonly property int highestUrgency: NotificationModel.highestUrgency(items)
    property bool doNotDisturb: false
    property var popups: []

    onDoNotDisturbChanged: {
        if (doNotDisturb) {
            for (const notification of popups.slice()) {
                if (!NotificationModel.shouldAlert(true, notification.urgency))
                    hidePopup(notification)
            }
        }
    }
    property int pulseToken: 0

    function dismissAll() {
        for (const notification of items.slice())
            notification.dismiss()
    }

    function hidePopup(notification) {
        popups = popups.filter(item => item !== notification)
        if (notification?.transient && notification.tracked)
            notification.expire()
    }

    function playSound(name) {
        Quickshell.execDetached(["canberra-gtk-play", "-i", name])
    }

    onItemsChanged: {
        popups = popups.filter(notification => items.includes(notification))
    }

    NotificationServer {
        id: server

        keepOnReload: true
        persistenceSupported: true
        actionsSupported: true
        imageSupported: true

        onNotification: notification => {
            notification.tracked = true
            if (notification.lastGeneration)
                return
            if (!NotificationModel.shouldAlert(root.doNotDisturb, notification.urgency)) {
                root.hidePopup(notification)
                return
            }

            root.popups = NotificationModel.prependUnique(root.popups, notification)
            root.pulseToken++

            if (notification.urgency === NotificationUrgency.Normal) {
                root.playSound("message-new-instant")
            } else if (notification.urgency === NotificationUrgency.Critical) {
                root.playSound("alarm-clock-elapsed")
            }
        }
    }
}
