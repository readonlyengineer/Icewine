const assert = require("node:assert/strict")
const battery = require("../modules/BatteryAlertModel.js")
const policy = { warnings: [20, 10, 5], sleep: 3 }
let state = battery.initial()
let requests = 0

function update(percentage, discharging = true, present = true, enabled = true) {
    const result = battery.update(state, { percentage, discharging, present }, policy, enabled)
    state = result.state
    return result
}

function dispatch(percentage, discharging = true) {
    const result = battery.confirmSleep(state,
        { percentage, discharging, present: true }, policy, true)
    state = result.state
    if (result.dispatch) ++requests // Mock the existing session.requestSleep action.
    return result.dispatch
}

assert.equal(update(21).alert, null)
assert.equal(update(20).alert, 20)
assert.equal(update(20).alert, null)
assert.equal(update(10).alert, 10)
assert.equal(update(5).alert, 5)
assert.equal(update(3).startSleep, true)
assert.equal(update(3).startSleep, false)
assert.equal(dispatch(3), true)
assert.equal(dispatch(3), false)
assert.equal(update(3).startSleep, false, "resume at 3% cannot loop suspend")
assert.equal(requests, 1)

assert.equal(update(6, false).alert, null)
assert.equal(update(3).startSleep, true, "charging recovery rearms sleep")
assert.equal(dispatch(4), false, "current recovered reading cancels sleep")
assert.equal(update(3).startSleep, true)
assert.equal(update(3, false).cancelSleep, true)
assert.equal(dispatch(3), false, "charging before dispatch cancels sleep")
assert.equal(update(3).startSleep, true)
assert.equal(dispatch(3, false), false, "final state check rejects charging")
assert.equal(requests, 1)

state = battery.initial()
const startup = update(2)
assert.equal(startup.alert, 5, "startup below all thresholds reports highest urgency")
assert.equal(startup.startSleep, true)
assert.equal(update(2).alert, null)
assert.equal(update(2, false).cancelSleep, true)
assert.equal(update(2, true, false).alert, null)
assert.equal(update(Number.NaN).startSleep, false)
assert.equal(update(101).alert, null)
assert.equal(update(-1).alert, null)
assert.equal(update(2, true, true, false).startSleep, false)
assert.equal(update(2).startSleep, true, "invalid and disabled samples do not consume action")
assert.equal(dispatch(Number.NaN), false)

state = battery.initial()
assert.equal(update(9).alert, 10)
assert.equal(update(8).alert, null)
assert.equal(update(5).alert, 5)
assert.equal(update(8, false).alert, null)
assert.equal(update(5).alert, 5, "danger rearms after three-point recovery")
assert.equal(update(13, false).alert, null)
assert.equal(update(10).alert, 10, "critical rearms after charging")
assert.equal(update(23, false).alert, null)
assert.equal(update(20).alert, 20, "low rearms after recovery")

assert.equal(battery.validPolicy({ warnings: [25, 12, 6], sleep: 2 }), true)
const custom = { warnings: [25, 12, 6], sleep: 2 }
let customState = battery.initial()
const customWarning = battery.update(customState,
    { percentage: 24, discharging: true, present: true }, custom, true)
assert.equal(customWarning.alert, 25, "editable policy overrides default warning")
customState = customWarning.state
assert.equal(battery.update(customState,
    { percentage: 3, discharging: true, present: true }, custom, true).startSleep,
false, "editable sleep threshold controls dispatch")
assert.equal(battery.validPolicy({ warnings: [20, 5, 10], sleep: 3 }), false)
assert.equal(battery.update(battery.initial(),
    { percentage: 1, discharging: true, present: true },
    { warnings: [20, 5, 10], sleep: 3 }, true).startSleep, false)

console.log("battery alert checks passed")
