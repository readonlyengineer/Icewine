// Run: node quickshell/tests/winter-screen.js
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const Winter = require("../modules/WinterModel.js")

const screen = fs.readFileSync(path.join(__dirname, "../modules/WinterScreen.qml"), "utf8")
const greeter = fs.readFileSync(path.join(__dirname, "../modules/Greeter.qml"), "utf8")
const lock = fs.readFileSync(path.join(__dirname, "../modules/LockScreenSurface.qml"), "utf8")
const session = fs.readFileSync(path.join(__dirname, "../modules/SessionControl.qml"), "utf8")
const greeterEntry = fs.readFileSync(path.join(__dirname, "../greeter.qml"), "utf8")

assert.match(screen, /color: "#000000"/)
assert.match(screen, /WinterModel\.scaleFactor\(width, height\)/)
assert.doesNotMatch(screen, /InputPanel/)
assert.equal((session.match(/InputPanel/g) || []).length, 1)
assert.equal((greeterEntry.match(/InputPanel/g) || []).length, 1)
for (const name of ["submission", "authenticationMessage", "authenticationFailure", "sessionCommand"])
    assert.match(greeter, new RegExp(`WinterModel\\.${name}\\(`))
for (const name of ["Select user", "Select session", "Keyboard", "Reboot", "Shutdown", "Unlock"])
    assert.match(screen, new RegExp(`Accessible\\.name: "${name}"`))

assert.equal(Winter.scaleFactor(5120, 1440), 4 / 3)
assert.equal(Winter.scaleFactor(1920, 1200), 1)
assert.equal(Winter.nextIndex(1, 3), 2)
assert.equal(Winter.nextIndex(2, 3), 0)
assert.equal(Winter.nextIndex(0, 0), 0)
const firstScreen = {}
const secondScreen = {}
assert.equal(Winter.keyboardInset(firstScreen, firstScreen, true, 320), 320)
assert.equal(Winter.keyboardInset(firstScreen, secondScreen, true, 320), 0)
assert.equal(Winter.keyboardInset(firstScreen, firstScreen, false, 320), 0)

assert.deepEqual(Winter.submission(false, true, false, "secret", "peter"), null)
assert.deepEqual(Winter.submission(true, true, false, "", "peter"), null)
assert.deepEqual(Winter.submission(true, true, false, "secret", "peter"),
    { action: "create", response: "secret", user: "peter" })
assert.deepEqual(Winter.submission(true, false, true, "second", "peter"),
    { action: "respond", response: "second" })

assert.deepEqual(Winter.authenticationMessage("secret", "Password:", false, true, false), {
    prompt: "Password:", message: "", failed: false, secretInput: true,
    busy: true, pendingResponse: "", response: "secret"
})
assert.deepEqual(Winter.authenticationMessage("", "Touch sensor", false, true, true), {
    prompt: "Touch sensor", message: "", failed: false, secretInput: false,
    busy: false, pendingResponse: "", response: ""
})
assert.deepEqual(Winter.authenticationFailure("Bad password"), {
    prompt: "Password", message: "Bad password", failed: true, secretInput: true,
    busy: false, pendingResponse: ""
})
assert.deepEqual(Winter.sessionCommand(["uwsm", "start"],
    ["hyprland", "hyprland-uwsm"], 1), ["uwsm", "start", "hyprland-uwsm.desktop"])
assert.equal(Winter.sessionCommand(["uwsm", "start"], [], 0), null)

assert.doesNotMatch(greeter, /console\.(log|warn).*password/i)
assert.match(lock, /controller: controller/)
assert.match(lock, /root\.session\.submit\(\)/)

console.log("winter presentation and authentication adapter checks passed")
