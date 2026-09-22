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

if (typeof module !== "undefined")
    module.exports = { shouldAlert, highestUrgency, prependUnique, toastTimeout }
