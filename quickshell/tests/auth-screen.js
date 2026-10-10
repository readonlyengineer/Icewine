// Run: node quickshell/tests/auth-screen.js
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const Auth = require("../modules/AuthModel.js")

const screen = fs.readFileSync(path.join(__dirname, "../modules/AuthScreen.qml"), "utf8")
const greeter = fs.readFileSync(path.join(__dirname, "../../sddm/Main.qml"), "utf8")
const lock = fs.readFileSync(path.join(__dirname, "../modules/LockScreenSurface.qml"), "utf8")
const session = fs.readFileSync(path.join(__dirname, "../modules/SessionControl.qml"), "utf8")

assert.doesNotMatch(screen, /InputPanel/)
assert.equal((session.match(/InputPanel/g) || []).length, 1)
assert.equal((greeter.match(/InputPanel/g) || []).length, 1)
assert.doesNotMatch(screen, /import (Quickshell|qs\.)/)
assert.doesNotMatch(greeter, /Quickshell|Greetd|execDetached/)
assert.match(greeter, /palette: Theme\.Palette/)
assert.match(lock, /palette: Theme\.Palette/)
for (const name of ["Select user", "Select session", "Keyboard", "Reboot", "Shutdown", "Unlock"])
    assert.match(screen, new RegExp(`Accessible\\.name: "${name}"`))

assert.equal(Auth.scaleFactor(5120, 1440), 1.25)
assert.equal(Auth.scaleFactor(1920, 1200), 1)
assert.equal(Auth.scaleFactor(800, 600), 0.8)
assert.equal(Auth.scaleFactor(320, 480), 0.8)
assert.equal(Auth.nextIndex(1, 3), 2)
assert.equal(Auth.nextIndex(2, 3), 0)
assert.equal(Auth.nextIndex(0, 0), 0)
const firstScreen = {}
const secondScreen = {}
assert.equal(Auth.keyboardInset(firstScreen, firstScreen, true, 320), 320)
assert.equal(Auth.keyboardInset(firstScreen, secondScreen, true, 320), 0)
assert.equal(Auth.keyboardInset(firstScreen, firstScreen, false, 320), 0)

assert.doesNotMatch(greeter, /console\.(log|warn).*password/i)
assert.match(lock, /controller: controller/)
assert.match(lock, /root\.session\.submit\(\)/)

console.log("auth presentation and authentication adapter checks passed")
