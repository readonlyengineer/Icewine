const assert = require("node:assert/strict")
const Session = require("../modules/SessionModel.js")
const path = "/org/freedesktop/login1/session/_32"
const signal = (suffix, session = path) => session + ": org.freedesktop.login1." + suffix

assert.equal(Session.sessionPath("(objectpath '" + path + "',)\n"), path)
for (const output of ["", "error", "('/org/freedesktop/login1/session/_32',)", "(objectpath '/other/path',)"])
    assert.equal(Session.sessionPath(output), "")

assert.equal(Session.logindEvent(signal("Session.Lock ()"), path), "lock")
assert.equal(Session.logindEvent(signal("Session.Unlock ()"), path), "unlock")
for (const session of ["", "/org/freedesktop/login1/session/other", path + "0"]) {
    assert.equal(Session.logindEvent(signal("Session.Unlock ()", session), path), "")
    assert.equal(Session.logindEvent(signal("Session.Lock ()", session), path), "")
}
assert.equal(Session.logindEvent(signal("Session.Unlock ()"), ""), "")
assert.equal(Session.logindEvent("org.freedesktop.login1.Session.Unlock ()", path), "")
assert.equal(Session.logindEvent(signal("Manager.PrepareForSleep (true,)", "/org/freedesktop/login1")), "sleep")
assert.equal(Session.logindEvent(signal("Manager.PrepareForSleep (false,)", "/org/freedesktop/login1")), "resume")
assert.equal(Session.logindEvent(signal("Manager.PrepareForSleep (true,)"), path), "")
assert.equal(Session.logindEvent("unrelated signal", path), "")

// Exercise the real QML handler: an external unlock signal must not bypass PAM.
const fs = require("node:fs")
const vm = require("node:vm")
const source = fs.readFileSync(require("node:path").join(__dirname, "../modules/SessionControl.qml"), "utf8")
const requestSleep = source.match(/    function requestSleep\(\) \{[\s\S]*?^    \}/m)[0]
const reportSleepFailure = source.match(/    function reportSleepFailure\(exitCode, exitStatus, message\) \{[\s\S]*?^    \}/m)[0]
const sleepRequests = vm.createContext({ sleep: { running: false },
    Quickshell: { execDetached: args => sleepRequests.notices.push(args) },
    console: { warn: message => sleepRequests.warnings.push(message) },
    notices: [], warnings: [] })
vm.runInContext(requestSleep + "\n" + reportSleepFailure, sleepRequests)
assert.equal(sleepRequests.requestSleep(), true)
assert.equal(sleepRequests.requestSleep(), false, "a pending Suspend must not be duplicated")
sleepRequests.reportSleepFailure(0, 0, "")
assert.equal(sleepRequests.notices.length, 0)
sleepRequests.reportSleepFailure(1, 0, "Suspend is unsupported")
assert.equal(sleepRequests.notices.length, 1)
assert.equal(sleepRequests.notices[0][3], "critical")
assert.equal(sleepRequests.notices[0].at(-1), "Suspend is unsupported")
assert.equal(sleepRequests.warnings.length, 1)
const handler = source.match(/    function handleLogind\(line\) \{[\s\S]*?^    \}/m)[0]
const events = []
const context = vm.createContext({
    SessionModel: Session, logindSessionPath: path,
    lockFromLogind: () => events.push("lock"),
    wakeDisplay: () => events.push("wake"),
    releaseLock: () => events.push("unlock")
})
vm.runInContext(handler, context)
context.handleLogind(signal("Session.Unlock ()"))
assert.deepEqual(events, [], "logind unlock must not release the session lock")
context.handleLogind(signal("Session.Lock ()"))
context.handleLogind(signal("Manager.PrepareForSleep (true,)", "/org/freedesktop/login1"))
context.handleLogind(signal("Manager.PrepareForSleep (false,)", "/org/freedesktop/login1"))
assert.deepEqual(events, ["lock", "lock", "wake"])

console.log("session model and lock control checks passed")
