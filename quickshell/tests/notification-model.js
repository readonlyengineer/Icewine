const assert = require("node:assert/strict")
const notifications = require("../modules/notifications/Model.js")
// Native control interaction lives in controls.py; this check owns notification policy.
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
