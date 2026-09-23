function shouldAlert(doNotDisturb, urgency) {
    return !doNotDisturb || urgency >= 2
}

function highestUrgency(notifications) {
    return notifications.reduce((highest, notification) =>
        Math.max(highest, Number(notification.urgency ?? 0)), 0)
}

function prependUnique(notifications, notification) {
    return [notification, ...notifications.filter(item => item.id !== notification.id)]
}

function toastTimeout(urgency, requestedTimeout) {
    if (urgency >= 2 || requestedTimeout === 0)
        return 0
    if (requestedTimeout > 0)
        return requestedTimeout
    return urgency === 0 ? 3000 : 5000
}

function sourceWindowAddress(notification, windows, desktopEntry) {
    const identities = [notification?.desktopEntry, desktopEntry?.id,
        desktopEntry?.startupClass]
        .map(identity => String(identity || "").replace(/\.desktop$/i, "").toLowerCase())
        .filter((identity, index, values) => identity && values.indexOf(identity) === index)
    if (!identities.length)
        return ""

    const matches = Array.from(windows || []).filter(window => {
        if (!window.wayland)
            return false
        const appId = String(window.wayland?.appId || window.lastIpcObject?.class || "")
            .replace(/\.desktop$/i, "").toLowerCase()
        return window.address && identities.includes(appId)
    })
    return matches.length === 1 ? matches[0].address : ""
}

if (typeof module !== "undefined")
    module.exports = { shouldAlert, highestUrgency, prependUnique, toastTimeout,
        sourceWindowAddress }
