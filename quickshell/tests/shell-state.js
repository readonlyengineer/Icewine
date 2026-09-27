// Run: node quickshell/tests/shell-state.js
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const vm = require("node:vm")
const State = require("../modules/ShellState.js")
const Menu = require("../deck/DeckMenu.js")

// Guard the scene's input boundary as well as the controller below. Qt's real
// mouse/touch delivery is checked separately in an isolated Wayland session.
const topbar = fs.readFileSync(path.join(__dirname, "../modules/Topbar.qml"), "utf8")
const barBackground = topbar.split("id: surface")[1]?.split("Row {")[0] ?? ""
assert.match(barBackground, /MouseArea\s*\{\s*anchors\.fill: parent\s*acceptedButtons: Qt\.AllButtons/,
    "Bar background must catch clicks beneath its controls, before outside-dismiss")
assert.match(barBackground, /onWheel: event => event\.accepted = true/,
    "Bar background must consume scrolling rather than passing it underneath")

let state = State.initial()
const send = event => { state = State.reduce(state, event) }
assert.equal(State.barVisible(state, false, false), false)
send({type: "press"})
assert.equal(State.barVisible(state, false, false), true)
send({type: "release"})
assert.equal(State.barVisible(state, false, false), false)
assert.equal(State.barVisible(state, false, true), true, "Hover sustains a revealed bar")
assert.equal(State.barVisible(state, true, false), true, "Radial reveals the bar")
send({type: "open", page: "audio", engaged: false, screen: "deck"})
send({type: "engage"}) // Touch, drag or scroll, not just a completed click.
send({type: "release"})
assert.equal(State.barVisible(state, false, false), true, "Widget survives both hold releases")
assert.equal(state.engaged, true)
send({type: "open", page: "network", engaged: false, screen: "external"})
assert.equal(state.page, "audio", "Hover cannot replace an engaged widget")
send({type: "open", page: "network", engaged: true, screen: "external"})
assert.equal(state.page, "network")
assert.equal(state.screen, "external")
send({type: "dismiss"})
assert.equal(State.barVisible(state, true, false), true, "Closing widget does not close radial")
assert.equal(State.barVisible(state, false, false), false)
send({type: "open", page: "unknown", engaged: true, screen: "deck"})
assert.equal(state.page, "")
send({type: "press"})
send({type: "open", page: "launcher", engaged: true, screen: "deck"})
send({type: "reset"})
assert.deepEqual(state, State.initial())

send({type: "open", page: "performance", engaged: true, screen: "external"})
assert.equal(state.page, "performance")
assert.equal(state.screen, "external")
assert.equal(State.barVisible(state, false, false), true)
send({type: "dismiss"})
assert.equal(State.barVisible(state, false, false), false)

// Execute the actual QML controller methods, with only platform I/O replaced.
send({type: "open", page: "screenshot", engaged: true, screen: "external"})
assert.equal(state.page, "screenshot")
assert.equal(state.engaged, true)
assert.equal(state.screen, "external")
send({type: "dismiss"})
assert.equal(State.barVisible(state, false, false), false)

function controller(file, properties) {
    const context = vm.createContext(properties)
    context.root = context
    const source = fs.readFileSync(path.join(__dirname, file), "utf8")
    for (const match of source.matchAll(/^    function \w+\([^\n]*\) \{[\s\S]*?^    \}/gm))
        vm.runInContext(match[0], context)
    return context
}

const callbacks = [], focused = []
const shell = controller("../modules/Topbar.qml", {
    State, ui: State.initial(), hoveredScreen: "", sessionLocked: false,
    interactionActive: false, previousWindow: "", focusGeneration: 0,
    barVisible: false, radial: {dismiss() {}, drainInput() {}}, widgetDismissed() {},
    compositor: {activeWindowAddress: "original", activateWindow: address => focused.push(address)},
    Qt: {callLater: fn => callbacks.push(fn)}
})
const flush = () => { while (callbacks.length) callbacks.shift()() }
shell.beginInteraction()
shell.finishInteraction()
flush()
assert.deepEqual(focused, ["original"], "Ordinary dismissal restores the previous window")
focused.length = 0
shell.beginInteraction()
shell.finishInteraction()
shell.beginInteraction()
flush()
assert.equal(focused.length, 0, "Old restoration cannot interrupt a new interaction")
shell.handoff()
shell.finishInteraction()
flush()
assert.equal(focused.length, 0, "Launch/navigation handoff cancels restoration")
let raises = 0
shell.player = {canRaise: true, raise: () => raises++}
shell.beginInteraction()
shell.raiseMedia()
shell.finishInteraction()
flush()
assert.equal(raises, 1)
assert.equal(focused.length, 0, "Media activation is not undone by focus restoration")
shell.player = {canRaise: false, raise: () => assert.fail("Unsupported Raise")}
shell.raiseMedia()
flush()
assert.equal(raises, 1)

const target = "/org/shadowblip/InputPlumber/devices/target/dbus0"
const deck = controller("../deck/DeckOverlay.qml", {
    Menu, opened: true, draining: false, held: {}, acceptArmed: false,
    captured: true, entries: [{action: "screenshot"}], selected: 0,
    workspace: 1, pendingEntry: null, eventTarget: target,
    sessionLocked: false, shell, inputError: "",
    Quickshell: {execDetached() {}},
    drainWarning: {restart() {}, stop() {}},
    Qt: {callLater: fn => callbacks.push(fn)}
})
const input = (action, pressed) => deck.receive(
    `${target}: org.shadowblip.Input.DBusDevice.InputEvent ('${action}', ${pressed ? "1.0" : "0.0"})`)
input("ui_right", true)
deck.dismiss()
assert.equal(deck.opened, false, "Radial disappears immediately with stick held")
assert.equal(deck.draining, true)
assert.equal(Menu.inputRoute(true, false, false, deck.draining, true), "overlay")
input("ui_right", false)
assert.equal(deck.draining, false, "Hidden radial still processes releases")
assert.equal(Menu.inputRoute(true, true, false, deck.draining, true), "overlay", "Engaged widget keeps capture")
input("ui_left", true)
deck.drainInput() // Last widget closes after the radial has gone.
assert.equal(deck.draining, true)
input("ui_left", false)
assert.equal(deck.draining, false)

shell.ui = State.reduce(shell.ui, {type: "open", page: "network", engaged: true, screen: "deck"})
deck.activate({action: "keyboard"}, 1)
assert.equal(shell.ui.page, "network", "OSK opens without dismissing its target widget")

let choices = 0
deck.choose = () => choices++
input("ui_accept", true) // Held before the radial opens.
deck.opened = true
input("ui_accept", false)
assert.equal(choices, 0, "Opening-key release cannot select an action")
input("ui_accept", true)
input("ui_accept", false)
assert.equal(choices, 1)
deck.captured = false
input("ui_accept", true)
deck.captured = true
input("ui_accept", false)
assert.equal(choices, 1, "Press before capture confirmation cannot select an action")

const captures = []
deck.Quickshell.execDetached = command => captures.push(Array.from(command))
deck.activate({action: "screenshot"}, 0)
assert.equal(captures.length, 0, "Dismiss the shell before capture")
flush()
assert.deepEqual(captures, [
    ["icewine-screenshot", "monitor", "eDP-1", "0", "1", "1"]
], "Capture the built-in panel immediately to both destinations")

let launches = 0
deck.activate = () => launches++
deck.requestClose({action: "screenshot"})
deck.opened = true // Reopening cancels the deferred action.
flush()
assert.equal(launches, 0)
deck.requestClose({action: "screenshot"})
deck.sessionLocked = true
flush()
assert.equal(launches, 0, "Lock cancels deferred launches")
console.log("shell state: visibility, touch engagement, release drain, stale actions and focus handoffs pass")
