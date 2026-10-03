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
assert.match(card, /Accessible\.name:\s*"Go to source window"/,
    "Source navigation must have an accessible name")
assert.match(card, /Accessible\.role:\s*Accessible\.Button/,
    "Source navigation must expose button semantics")
assert.match(card, /Controls\.ToolTip\.text:\s*"Go to source window"/,
    "Source navigation must explain itself on hover")
assert.match(card, /notification\?\.appIcon === "battery-low"[\s\S]*?Quickshell\.iconPath\(notification\.appIcon, true\)/,
    "Battery notifications must prefer the battery app icon over the notification image")
const sourceButton = card.match(/Controls\.Button\s*\{\s*id:\s*sourceButton\b([\s\S]+?)\n    \}\n\n    Column/)[1]
assert.match(sourceButton, /root\.sourceRequested\(address\)/,
    "Source navigation must use its isolated action")
assert.doesNotMatch(sourceButton, /root\.dismissRequested\(\)/,
    "Source navigation must not duplicate the card-body dismissal signal")
assert.match(sourceButton, /text:\s*"󰅂"/,
    "Source navigation must use the known-rendering directional icon")

const window = (address, appId, fallbackClass = "") => ({
    address,
    wayland: appId === null ? null : { appId },
    lastIpcObject: { class: fallbackClass }
})
const kitty = { desktopEntry: "kitty.desktop" }
const kittyEntry = { id: "kitty", startupClass: "kitty" }
assert.equal(notifications.sourceWindowAddress(kitty,
    [window("0x1", "kitty")], kittyEntry), "0x1")
assert.equal(notifications.sourceWindowAddress(kitty,
    [window("0x1", "kitty"), window("0x2", "kitty")], kittyEntry), "",
    "Multiple matching windows must not select an arbitrary source")
assert.equal(notifications.sourceWindowAddress({ desktopEntry: "org.example.App" },
    [window("0x3", "org.example.App")],
    { id: "org.example.App", startupClass: "ExampleClass" }), "0x3")
assert.equal(notifications.sourceWindowAddress({ desktopEntry: "example" },
    [window("0x4", "", "Example")], { id: "example", startupClass: "Example" }), "0x4")
assert.equal(notifications.sourceWindowAddress({ appName: "kitty" },
    [window("0x5", "kitty")], null), "",
    "A display name alone must not establish source identity")
assert.equal(notifications.sourceWindowAddress({ desktopEntry: "power-alert" },
    [window("0x6", "kitty")], { id: "power-alert", startupClass: "" }), "")
assert.equal(notifications.sourceWindowAddress(kitty, [], kittyEntry), "",
    "Closed source windows must not leave an actionable address")
assert.equal(notifications.sourceWindowAddress(kitty,
    [window("0x7", null, "kitty")], kittyEntry), "",
    "A toplevel without an activatable Wayland handle must not be actionable")

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
