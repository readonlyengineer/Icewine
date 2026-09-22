const assert = require("node:assert/strict")
const backgroundApps = require("../modules/topbar/BackgroundAppsModel.js")

const entries = [
    { isSeparator: true, enabled: true },
    { isSeparator: false, enabled: false },
    { isSeparator: false, enabled: true },
    { isSeparator: false, enabled: true }
]

assert.equal(backgroundApps.nextEnabled(entries, -1, 1), 2)
assert.equal(backgroundApps.nextEnabled(entries, 2, 1), 3)
assert.equal(backgroundApps.nextEnabled(entries, 3, 1), 2)
assert.equal(backgroundApps.nextEnabled(entries, 2, -1), 3)
assert.equal(backgroundApps.nextEnabled(entries, -1, -1), 3)
assert.equal(backgroundApps.nextEnabled([], -1, 1), -1)
assert.equal(backgroundApps.nextEnabled([
    { isSeparator: true, enabled: true },
    { isSeparator: false, enabled: false }
], -1, 1), -1)

console.log("background application model checks passed")
