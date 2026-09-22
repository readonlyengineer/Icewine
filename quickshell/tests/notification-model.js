const assert = require("node:assert/strict")
const notifications = require("../modules/notifications/Model.js")
const { readFileSync } = require("node:fs")
const { join } = require("node:path")

// Guard the scene's input boundary; compositor click delivery needs a live session.
const toasts = readFileSync(join(__dirname, "../modules/NotificationToasts.qml"), "utf8")
const card = readFileSync(join(__dirname, "../modules/notifications/NotificationCard.qml"), "utf8")
assert.doesNotMatch(toasts, /mask:\s*Region\s*\{\s*\}/,
    "An empty input region sends notification clicks to the window below")
assert.match(card, /MouseArea\s*\{\s*anchors.fill: parent\s*onClicked: root.dismissRequested\(\)/,
    "The notification body must dismiss on click")
for (const handler of card.matchAll(/TapHandler\s*\{([^}]+)\}/g))
    assert.match(handler[1], /gesturePolicy: TapHandler.WithinBounds/,
        "Buttons must capture clicks before the body-dismiss MouseArea")

for (const urgency of [0, 1, 2]) {
    assert.equal(notifications.shouldAlert(false, urgency), true)
    assert.equal(notifications.shouldAlert(true, urgency), urgency === 2)
}

assert.equal(notifications.highestUrgency([]), 0)
assert.equal(notifications.highestUrgency([{ urgency: 0 }, { urgency: 2 }]), 2)

const old = { id: 7, summary: "old" }
const replacement = { id: 7, summary: "new" }
const other = { id: 4, summary: "other" }
assert.deepEqual(notifications.prependUnique([old, other], replacement),
    [replacement, other])

assert.equal(notifications.toastTimeout(0, -1), 3000)
assert.equal(notifications.toastTimeout(1, -1), 5000)
assert.equal(notifications.toastTimeout(1, 1200), 1200)
assert.equal(notifications.toastTimeout(1, 0), 0)
assert.equal(notifications.toastTimeout(2, 1200), 0)

console.log("notification model checks passed")
