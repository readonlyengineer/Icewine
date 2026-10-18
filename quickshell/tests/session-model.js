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
    beginLock: () => events.push("lock"),
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

// Execute the production lifecycle, substituting only native/helper boundaries.
const handlers = ["writeLockHint", "restoreLock", "beginLock", "finishLockHint", "releaseLock",
    "requestLock", "handleLogind"]
    .map(name => source.match(new RegExp("    function " + name + "\\([^)]*\\) \\{[\\s\\S]*?^    \\}", "m"))[0]).join("\n")
function client(sessionPath = path) {
    const state = vm.createContext({
        SessionModel: Session, lockState: { acquired: false }, lockRequested: false,
        keyboardController: null, lockHint: { running: false, value: false },
        logindSessionPath: sessionPath, logindSessionId: "2", password: "fixture response",
        failed: true, notices: [], warnings: [], wakes: 0,
        console: { warn: message => state.warnings.push(message) },
        wakeDisplay: () => state.wakes++,
        Quickshell: { execDetached: args => state.notices.push(args) }
    })
    // Ownership/target and compositor secure acknowledgement are different stages.
    state.sessionLock = { get locked() { return state.lockState.acquired }, secure: false }
    vm.runInContext(handlers, state)
    return state
}
function completeHint(state, exitCode = 0, exitStatus = 0) {
    assert.equal(state.lockHint.running, true)
    state.lockHint.running = false
    state.finishLockHint(exitCode, exitStatus)
}
for (const request of [state => state.requestLock(), state => state.beginLock(),
        state => state.handleLogind(signal("Session.Lock ()")),
        state => state.handleLogind(signal("Manager.PrepareForSleep (true,)", "/org/freedesktop/login1"))]) {
    const state = client()
    request(state)
    assert.equal(state.lockRequested, true)
    assert.equal(state.lockHint.running, true)
    assert.equal(state.lockHint.command.at(-1), "true")
    assert.equal(state.password, "")
    assert.equal(state.failed, false)
    assert.equal(state.sessionLock.locked, false, "retain crash-recovery ordering while the write stalls")
    const command = state.lockHint.command
    state.password = "in-progress response"
    state.beginLock()
    assert.equal(state.lockHint.command, command, "repeated requests do not restart the pending helper")
    assert.equal(state.password, "in-progress response", "repeated intent does not erase input")
    state.restoreLock("(<false>,)")
    state.restoreLock("malformed")
    assert.equal(state.lockState.acquired, false, "unconfirmed restoration cannot bypass persistence")
    state.releaseLock(true)
    assert.equal(state.lockRequested, true, "no native lock has yet been acquired to release")
    completeHint(state)
    assert.equal(state.lockState.acquired, true)
    assert.equal(state.sessionLock.secure, false, "target does not invent compositor acknowledgement")
    state.handleLogind(signal("Session.Unlock ()"))
    state.restoreLock("(<false>,)")
    state.restoreLock("malformed")
    assert.equal(state.lockState.acquired, true, "external results never release a lock")
    state.handleLogind(signal("Manager.PrepareForSleep (false,)", "/org/freedesktop/login1"))
    assert.equal(state.wakes, 1)
}
// Existing native ownership does not prevent establishing the persistent intent
// needed to invalidate privacy guards on release (native unlock has no notifier).
const nativeOnly = client()
nativeOnly.lockState.acquired = true
nativeOnly.beginLock()
assert.equal(nativeOnly.lockRequested, true)
assert.equal(nativeOnly.lockState.acquired, true)
nativeOnly.releaseLock(true)
assert.equal(nativeOnly.lockRequested, false)
assert.equal(nativeOnly.lockState.acquired, false)
// Failed helper completion preserves the existing fail-closed attempt and warning.
for (const [code, status] of [[1, 0], [0, 1]]) {
    const state = client()
    state.beginLock()
    completeHint(state, code, status)
    assert.equal(state.lockState.acquired, true)
    assert.equal(state.warnings.length, 1, "failed persistence must disclose recovery limitation")
}
const unavailable = client("")
unavailable.requestLock()
assert.equal(unavailable.lockState.acquired, true, "unresolved logind retains immediate native attempt")
assert.equal(unavailable.lockHint.running, false)
assert.deepEqual(Array.from(unavailable.notices[0]), ["loginctl", "lock-session", "2"])
// Crash recovery uses an existing true hint and clears stale response state via the shared entry.
const recovery = client()
recovery.restoreLock("(<true>,)")
assert.equal(recovery.lockRequested, true)
assert.equal(recovery.lockState.acquired, true, "confirmed persisted intent needs no rewrite wait")
assert.equal(recovery.password, "")
assert.equal(recovery.failed, false)
// Authentication can finish before the redundant recovery write finishes.
recovery.releaseLock(true)
assert.equal(recovery.lockRequested, false)
assert.equal(recovery.lockState.acquired, false)
completeHint(recovery)
assert.equal(recovery.lockState.acquired, false, "late true write must not reacquire after authenticated release")
assert.equal(recovery.lockHint.command.at(-1), "false")
// New intent during the false write waits for its own true write, including failure.
recovery.beginLock()
assert.equal(recovery.lockRequested, true)
assert.equal(recovery.lockState.acquired, false)
completeHint(recovery)
assert.equal(recovery.lockHint.command.at(-1), "true")
assert.equal(recovery.lockState.acquired, false, "old unlock completion cannot acquire a newer request")
completeHint(recovery, 1)
assert.equal(recovery.lockState.acquired, true)
for (const output of ["", "(<false>,)", "(<true>,) extra", "true", "unexpected"]) {
    const fresh = client()
    fresh.restoreLock(output)
    assert.equal(fresh.lockRequested, false, "malformed or false recovery cannot invent a request")
    assert.equal(fresh.lockState.acquired, false)
}
// A delayed true recovery read can conservatively relock; it never authorises release.
recovery.releaseLock(true)
recovery.restoreLock("(<true>,)")
assert.equal(recovery.lockState.acquired, true)
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
// Run the production request/PAM handlers: prompting must not start PAM or
// weaken busy input guards, and only success releases the lock.
const submit = source.match(/    function submit\(\) \{[\s\S]*?^    \}/m)[0]
const toggle = source.match(/    function toggleKeyboard\(host\) \{[\s\S]*?^    \}/m)[0]
const message = source.match(/        onPamMessage: \{([\s\S]*?)^        \}/m)[1]
const completed = source.match(/        onCompleted: result => \{([\s\S]*?)^        \}/m)[1]
const auth = vm.createContext({
    authenticationRequired: true, password: "", authenticating: false,
    externalKeyboardBusy: false, failed: false, keyboardEnabled: false,
    keyboardHost: null, keyboardController: null, starts: 0, releases: 0,
    responses: [], responseRequired: false, PamResult: { Success: 0 },
    pam: { start: () => auth.starts++ },
    releaseLock: () => auth.releases++,
    respond: value => auth.responses.push(value),
    Qt: { inputMethod: { show() {}, hide() {} } }
})
auth.root = auth
vm.runInContext(submit + "\n" + toggle + "\nfunction message() {" + message
    + "}\nfunction complete(result) {" + completed + "}", auth)
const host = {}
auth.toggleKeyboard(host)
assert.equal(auth.keyboardEnabled, true, "OSK opens before PAM starts")
auth.submit()
assert.equal(auth.starts, 0, "empty response cannot start PAM")
auth.password = "fixture-secret"
auth.submit()
assert.equal(auth.starts, 1)
auth.submit()
auth.toggleKeyboard(host)
assert.equal(auth.starts, 1, "busy submit cannot start concurrent PAM")
assert.equal(auth.keyboardEnabled, true, "busy shared toggle cannot alter keyboard")
auth.message()
assert.equal(auth.responses.length, 0, "informational PAM message needs no response")
auth.responseRequired = true
auth.message()
assert.deepEqual(Array.from(auth.responses), ["fixture-secret"])
auth.complete(1)
assert.equal(auth.password, "")
assert.equal(auth.authenticating, false)
assert.equal(auth.failed, true)
assert.equal(auth.releases, 0, "failure retains lock")
auth.externalKeyboardBusy = true
auth.toggleKeyboard(host)
assert.equal(auth.keyboardEnabled, true, "external chord also blocks shared toggle")
auth.externalKeyboardBusy = false
auth.toggleKeyboard(host)
assert.equal(auth.keyboardEnabled, false, "retry can close OSK")
auth.password = "retry-secret"
auth.submit()
auth.complete(0)
assert.equal(auth.password, "")
assert.equal(auth.authenticating, false)
assert.equal(auth.releases, 1, "PAM success releases lock")
console.log("session model, persistent lock intent and acquisition checks passed")
