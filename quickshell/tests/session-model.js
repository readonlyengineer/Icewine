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

// Execute persistence/acquisition handlers from the QML implementation.
const handlers = ["writeLockHint", "restoreLock", "lockFromLogind", "finishLockHint", "releaseLock"]
    .map(name => source.match(new RegExp("    function " + name + "\\([^)]*\\) \\{[\\s\\S]*?^    \\}", "m"))[0]).join("\n")
const recovery = vm.createContext({
    lockState: { acquired: false }, lockRequested: false,
    lockHint: { running: false, value: false }, logindSessionPath: path, logindSessionId: "2",
    password: "secret", failed: true, console: { warn: () => {} },
    wakeDisplay: () => {}, Quickshell: { execDetached: () => {} }
})
recovery.sessionLock = { get locked() { return recovery.lockState.acquired } }
vm.runInContext(handlers, recovery)
recovery.lockFromLogind()
assert.equal(recovery.lockHint.running, true)
assert.equal(recovery.lockHint.command.at(-1), "true")
assert.equal(recovery.sessionLock.locked, false, "persist intent before acquisition")
recovery.lockHint.running = false
recovery.finishLockHint(0, 0)
assert.equal(recovery.sessionLock.locked, true)
assert.equal(recovery.password, "")
recovery.restoreLock("(<false>,)")
assert.equal(recovery.sessionLock.locked, true, "a false hint cannot release a lock")
recovery.lockHint.running = false
recovery.releaseLock(true)
assert.equal(recovery.lockRequested, false)
assert.equal(recovery.lockHint.command.at(-1), "false")
// A fresh client reacquires a remembered lock, but never from malformed output.
recovery.lockHint.running = false
recovery.restoreLock("(<true>,)")
assert.equal(recovery.lockRequested, true)
assert.equal(recovery.sessionLock.locked, true)
recovery.restoreLock("unexpected")
assert.equal(recovery.sessionLock.locked, true)
// A new request while an unlock hint is pending is serialised before acquisition.
recovery.lockState.acquired = false
recovery.lockRequested = true
recovery.lockHint.value = false
recovery.lockHint.running = false
recovery.finishLockHint(0, 0)
assert.equal(recovery.lockHint.command.at(-1), "true")
assert.match(source, /Scope\s*\{\s*reloadableId: "sessionLockLifecycle"\s*PersistentProperties[\s\S]*?WlSessionLock\s*\{\s*id: sessionLock\s*locked: lockState.acquired/,
    "native reload restores the persistent acquisition target before transferring the lock manager")
const refresh = source.match(/        function refreshIcons\(\): void \{[\s\S]*?^        \}/m)[0].replace(": void", "")
const reloads = []
const refreshContext = vm.createContext({ root: { lockRequested: true, locked: false },
    Quickshell: { reload: hard => reloads.push(hard) } })
vm.runInContext(refresh, refreshContext)
refreshContext.refreshIcons()
refreshContext.root.lockRequested = false
refreshContext.root.locked = true
refreshContext.refreshIcons()
assert.deepEqual(reloads, [], "icon refresh cannot reload a pending or acquired lock")
refreshContext.root.locked = false
refreshContext.refreshIcons()
assert.deepEqual(reloads, [false])
console.log("session model, persistent lock intent and acquisition checks passed")
