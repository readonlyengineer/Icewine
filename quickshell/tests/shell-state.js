// Run: node quickshell/tests/shell-state.js
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const vm = require("node:vm")
const Cards = require("../modules/topbar/CardModules.js")
// Execute the QML script with its real registry import supplied to Node's VM.
const State = vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../modules/ShellState.js"), "utf8")
    .replace(/^\.import "topbar\/CardModules\.js" as Cards\n/, "") + "\nmodule.exports",
    {Cards, module: {exports: {}}})
const Menu = require("../deck/DeckMenu.js")

// Guard the scene's input boundary as well as the controller below. Qt's real
// mouse/touch delivery is checked separately in an isolated Wayland session.
const topbar = fs.readFileSync(path.join(__dirname, "../modules/Topbar.qml"), "utf8")
const barBackground = topbar.split("id: surface")[1]?.split("Row {")[0] ?? ""
assert.match(barBackground, /MouseArea\s*\{\s*anchors\.fill: parent\s*acceptedButtons: Qt\.AllButtons/,
    "Bar background must catch clicks beneath its controls, before outside-dismiss")
assert.match(barBackground, /onWheel: event => event\.accepted = true/,
    "Bar background must consume scrolling rather than passing it underneath")

const mask = topbar.match(/mask: Region \{([\s\S]*?)^            \}/m)[1]
assert.match(mask, /statusPopout\.shown \? statusPopout : null/, "Shared host supplies its input region")
assert.doesNotMatch(mask, /\blauncher\b/, "Removed launcher cannot leave a dangling input-region binding")

const clipboardLock = topbar.match(/^        locked: ([^\n]+)$/m)[1]
for (const [locked, stacks, expected] of [[false, Cards.defaults, false], [true, Cards.defaults, true], [false, [], true]])
    assert.equal(vm.runInNewContext(clipboardLock, {root: {sessionLocked: locked}, Cards,
        Config: {Settings: {cardStacks: stacks}}}), expected, "Clipboard collection stops when locked or disabled")

// Media-key IPC uses the panel's selection and respects player capabilities.
const media = vm.createContext({Mpris: {players: {values: []}}, root: {}})
const selection = topbar.match(/readonly property var player: ([\s\S]*?)\n\n/)[1]
for (const [action, capability, method] of [
    ["mediaNext", "canGoNext", "next"],
    ["mediaPrevious", "canGoPrevious", "previous"],
    ["mediaToggle", "canTogglePlaying", "togglePlaying"]
]) {
    const body = topbar.match(new RegExp(`function ${action}\\(\\): void \\{([^\\n]+)\\}`))[1]
    const invoke = () => {
        media.root.player = vm.runInContext(selection, media)
        vm.runInContext(body, media)
    }
    const calls = []
    const paused = {isPlaying: false, [capability]: true, [method]: () => calls.push("paused")}
    const playing = {isPlaying: true, [capability]: true, [method]: () => calls.push("playing")}
    media.Mpris.players.values = [paused, playing]
    invoke()
    playing[capability] = false
    invoke() // Do not redirect an unsupported action to a different player.
    media.Mpris.players.values = [paused]
    invoke()
    media.Mpris.players.values = []
    invoke()
    assert.deepEqual(calls, ["playing", "paused"], action)
}

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

send({type: "open", page: "switcher", engaged: true, screen: "deck"})
for (const page of ["launcher", "audio", "network", "layout"]) {
    send({type: "open", page, engaged: false, screen: "deck"})
    assert.equal(state.page, page, "Hover replaces the window overview")
    send({type: "open", page: "switcher", engaged: true, screen: "deck"})
}
send({type: "dismiss"})

function controller(file, properties) {
    const context = vm.createContext(properties)
    context.root = context
    const source = fs.readFileSync(path.join(__dirname, file), "utf8")
    for (const match of source.matchAll(/^    function \w+\([^\n]*\) \{[\s\S]*?^    \}/gm))
        vm.runInContext(match[0], context)
    return context
}

const callbacks = [], focused = [], focusRequests = []
const shell = controller("../modules/Topbar.qml", {
    Cards, Config: {Settings: {cardStacks: Cards.defaults, windowSwitcher: true}},
    keyboard: null, State, focusWidgetRequested: (...args) => focusRequests.push(args), ui: State.initial(), hoveredScreen: "", sessionLocked: false,
    interactionActive: false, previousWindow: "", previousToplevel: null, focusGeneration: 0, widgetFocusGeneration: 0,
    clipboardPaste: null,
    layoutsEnabled: true, barVisible: false, radial: {dismiss() {}, drainInput() {}}, widgetDismissed() {},
    compositor: {activeWindowAddress: "original", toplevels: [{address: "original"}],
        activateWindow: address => focused.push(address), activateToplevel: window => focused.push(window)},
    Qt: {callLater: fn => callbacks.push(fn)}
})
const flush = () => { while (callbacks.length) callbacks.shift()() }
for (const page of Cards.modules) {
    shell.Config.Settings.cardStacks = [{id: "standalone", modules: [page]}]
    for (const engaged of [false, true]) {
        shell.dismissWidget()
        focusRequests.length = 0
        shell.openWidget(page, engaged, "external")
        flush()
        assert.equal(shell.ui.page, page, `${page}: real controller admits every registered standalone card`)
        assert.equal(shell.ui.engaged, engaged)
        assert.deepEqual(focusRequests, engaged ? [["external", page]] : [])
    }
}
shell.Config.Settings.cardStacks = Cards.defaults
shell.dismissWidget()
flush()
focusRequests.length = 0
for (let repeat = 0; repeat < 2; ++repeat) {
    shell.openWidget("launcher", true, "external")
    flush()
}
assert.deepEqual(focusRequests, [["external", "launcher"], ["external", "launcher"]],
    "Every explicit launcher request carries opening intent, even while already open")
for (const method of ["releaseBar", "pressBar", "engageWidget"]) {
    focusRequests.length = 0
    shell.openWidget("launcher", true, "external")
    shell[method]()
    flush()
    assert.deepEqual(focusRequests, [["external", "launcher"]],
        `${method} must preserve the pending explicit launcher request`)
}
for (const method of ["dismissWidget", "dismiss"]) {
    focusRequests.length = 0
    shell.openWidget("launcher", true, "external")
    shell[method]()
    flush()
    assert.deepEqual(focusRequests, [], `${method} cancels pending widget focus`)
    shell.openWidget("launcher", true, "external")
    shell[method]()
    shell.openWidget("launcher", true, "external")
    flush()
    assert.deepEqual(focusRequests, [["external", "launcher"]],
        "Reopening the same target cannot revive its dismissed request")
}
shell.dismissWidget()
shell.Config.Settings.cardStacks = []
shell.openWidget("launcher", true, "external")
assert.equal(shell.ui.page, "", "Disabled modules cannot be entered through the shared boundary")
shell.Config.Settings.cardStacks = [{id: "mixed", modules: ["clipboard", "audio"]}]
shell.openWidget("audio", true, "external")
assert.equal(shell.ui.page, "audio", "Direct module entry resolves configured membership")
shell.Config.Settings.cardStacks = Cards.defaults
shell.dismissWidget()
flush()
focusRequests.length = 0
shell.openWidget("launcher", true, "external")
shell.sessionLocked = true
flush()
assert.deepEqual(focusRequests, [], "Lock suppresses queued widget focus")
shell.sessionLocked = false
shell.dismissWidget()
shell.openWidget("launcher", true, "external")
shell.openWidget("launcher", true, "deck")
flush()
assert.deepEqual(focusRequests, [["deck", "launcher"]], "A newer monitor target supersedes old focus")
focusRequests.length = 0
shell.openWidget("launcher", true, "external")
shell.openWidget("audio", true, "deck")
flush()
assert.deepEqual(focusRequests, [["deck", "audio"]], "A superseded request cannot reset another widget")
shell.dismissWidget()
flush()
shell.openWidget("launcher", false, "external")
flush()
assert.equal(focusRequests.length, 1, "Hover does not request keyboard focus")
shell.dismissWidget()
flush()
const panelFocus = topbar.match(/            function focusWidget\(openingPage\) \{[\s\S]*?^            \}/m)[0]
const routes = []
const panel = vm.createContext({widgetHere: true, root: {widgetEngaged: true},
    switcher: {item: null}, statusPopout: {
        openPage: page => routes.push(page), focusInitial: () => routes.push("restore")}})
vm.runInContext(panelFocus, panel)
panel.focusWidget("launcher")
panel.focusWidget("")
panel.focusWidget("layout")
assert.deepEqual(routes, ["launcher", "restore", "restore", "layout", "restore"],
    "Every module uses the shared entry and ordinary restoration preserves selection")
panel.widgetHere = false
panel.focusWidget("layout")
assert.equal(routes.length, 5, "Another monitor cannot take Layout focus")
shell.layoutsEnabled = false
shell.openWidget("layout", true, "external")
flush()
assert.equal(shell.ui.page, "", "Disabled layout entry is rejected at the shared boundary")
shell.layoutsEnabled = true
shell.openWidget("layout", true, "external")
shell.openWidget("launcher", true, "deck")
flush()
assert.deepEqual(focusRequests.at(-1), ["deck", "launcher"], "Launcher supersedes pending Layout entry across monitors")
shell.dismissWidget()
flush()
shell.beginInteraction()
shell.finishInteraction()
flush()
assert.deepEqual(focused, ["original"], "Ordinary dismissal restores the previous window")
focused.length = 0
shell.beginInteraction()
shell.finishInteraction()
shell.compositor.toplevels = [{address: "original"}]
flush()
assert.equal(focused.length, 0, "Closed original object cannot restore a replacement with the same address")
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

// Exercise the activation callback through the real shared handoff methods.
const selected = shell.compositor.toplevels[0]
shell.ui = State.reduce(shell.ui, {type: "open", page: "switcher", engaged: true, screen: "external"})
shell.beginInteraction()
shell.activateSwitcherWindow(selected)
assert.equal(shell.ui.page, "")
assert.equal(focused.length, 0, "Activation waits until after handoff")
flush()
assert.deepEqual(focused, [selected])
shell.finishInteraction()
flush()
focused.length = 0
shell.activateSwitcherWindow(selected)
shell.sessionLocked = true
flush()
assert.equal(focused.length, 0, "Lock cancels deferred activation")
shell.sessionLocked = false
shell.activateSwitcherWindow(selected)
shell.beginInteraction()
flush()
assert.equal(focused.length, 0, "A new interaction cancels deferred activation")
shell.handoff()
shell.finishInteraction()
flush()

let keyboardToggles = 0
shell.keyboard = {hide() {}, toggle() { keyboardToggles++ }}
shell.beginInteraction(); shell.toggleKeyboard(); flush()
assert.equal(keyboardToggles, 1, "Keyboard entry restores prior focus before opening")
shell.beginInteraction(); shell.toggleKeyboard(); shell.beginInteraction(); flush()
assert.equal(keyboardToggles, 1, "Superseded keyboard entry cannot reopen")
shell.handoff(); shell.finishInteraction(); flush(); shell.keyboard = null

const target = "/org/shadowblip/InputPlumber/devices/target/dbus0"
const deck = controller("../deck/DeckOverlay.qml", {
    keyboard: null, keyboardVisible: false, keyboardReady: false, Menu, opened: true, draining: false, held: {}, acceptArmed: false,
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

// The same receiver routes captured OSK events to the grid, never radial actions.
const keyboardEvents = []
deck.keyboard = {controller: event => keyboardEvents.push(event), hide() {}}
deck.keyboardVisible = true; deck.keyboardReady = false
deck.opened = false; deck.captured = true; deck.held = {}
input("ui_accept", true); input("ui_accept", false)
assert.equal(keyboardEvents.length, 0, "opening controls must reach neutral first")
assert.equal(deck.keyboardReady, true)
input("ui_right", true); input("ui_right", false)
assert.deepEqual(keyboardEvents.map(event=>event.action), ["ui_right","ui_right"])
assert.equal(choices, 1, "OSK selection cannot choose a radial action")
input("ui_accept", true)
deck.drainInput()
assert.equal(deck.draining, true, "hide retains capture until activation releases")
deck.keyboardVisible = false
input("ui_accept", false)
assert.equal(deck.draining, false)
deck.keyboard = null

const captures = []
deck.Quickshell.execDetached = command => captures.push(Array.from(command))
deck.activate({action: "screenshot"}, 0)
assert.equal(captures.length, 0, "Dismiss the shell before capture")
flush()
assert.deepEqual(captures, [
    ["flameshot", "screen", "--edit"]
], "Open the native monitor editor after dismissing the shell")

// Exercise real page/host functions with page state unavailable at deferred launch.
for (const [mode, delayCapture, expected] of [
    ["monitor", false, ["flameshot", "screen", "--edit"]],
    ["monitor", true, ["flameshot", "screen", "--edit", "--delay", "3000"]],
    ["region", false, ["flameshot", "gui"]],
    ["region", true, ["flameshot", "gui", "--delay", "3000"]]
]) {
    const events = [], pending = []
    const host = controller("../modules/topbar/StatusPopout.qml", {
        instantHandoffRequested: () => events.push("dismiss"),
        Qt: {callLater: callback => pending.push(callback)},
        Quickshell: {execDetached: command => events.push(Array.from(command))}
    })
    const page = controller("../modules/topbar/popouts/Screenshot.qml", {
        delay: {checked: delayCapture}, captureRequested: command => host.capture(command)
    })
    page.capture(mode)
    page.root = page.delay = null
    assert.deepEqual(events, ["dismiss"], "Hide the popout before launching capture")
    while (pending.length) pending.shift()()
    assert.deepEqual(events, ["dismiss", expected])
}

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

// Clipboard uses the existing retained-window handoff; platform I/O is mocked.
shell.clipboardHistory = {selection: ["text/plain;charset=utf-8", "a".repeat(64)], error: "",
    request(action, id) { assert.equal(action, "load"); this.entry = id; return ++this.serial }, serial: 0}
shell.pasteWait = {attempts: 0, start() {this.running = true}, stop() {this.running = false}}
shell.pasteDelivery = {running: false}
shell.Quickshell = {execDetached() {}}
const originalPasteWindow = {address: "paste-target", lastIpcObject: {stableId: "1abc"}}
shell.compositor.toplevels = [originalPasteWindow]
shell.compositor.activeWindowAddress = originalPasteWindow.address
const preparePaste = (page = "screenshot") => {
    shell.clipboardPaste = null
    shell.sessionLocked = false
    shell.interactionActive = false
    shell.openWidget(page, true, "external")
    flush()
    shell.pasteClipboard("epoch:7")
    assert.equal(shell.clipboardPaste.phase, "loading")
    return shell.clipboardPaste.request
}
let pasteRequest = preparePaste()
assert.equal(shell.pasteDelivery.running, false, "No paste before clipboard load confirmation")
shell.clipboardLoaded(pasteRequest)
assert.equal(shell.ui.page, "", "Paste releases the panel through ordinary handoff")
flush()
assert.equal(focused.at(-1), originalPasteWindow)
shell.deliverClipboardPaste()
assert.equal(shell.pasteDelivery.running, true)
assert.deepEqual(Array.from(shell.pasteDelivery.command), ["icewine-clipboard", "paste", "1abc", ...shell.clipboardHistory.selection])
shell.pasteDelivery.running = false
shell.deliverClipboardPaste()
assert.equal(shell.pasteDelivery.running, false, "A duplicate completion/timer cannot paste twice")
shell.clipboardLoaded(pasteRequest)
assert.equal(shell.pasteDelivery.running, false)
for (const [page, modules] of [["audio", ["audio", "clipboard"]], ["clipboard", ["clipboard"]]]) {
    shell.Config.Settings.cardStacks = [{id: "regrouped", modules}]
    pasteRequest = preparePaste(page)
    shell.clipboardLoaded(pasteRequest + 1)
    assert.equal(shell.clipboardPaste.phase, "loading", "Unmatched completion cannot hand off a regrouped clipboard")
    shell.clipboardLoaded(pasteRequest)
    assert.equal(shell.ui.page, "", `${page}: clipboard membership permits ordinary focus handoff`)
    flush()
    assert.equal(focused.at(-1), originalPasteWindow)
    shell.deliverClipboardPaste()
    assert.equal(shell.pasteDelivery.running, true)
    assert.deepEqual(Array.from(shell.pasteDelivery.command), ["icewine-clipboard", "paste", "1abc", ...shell.clipboardHistory.selection])
    shell.pasteDelivery.running = false
    shell.deliverClipboardPaste()
    assert.equal(shell.pasteDelivery.running, false, "Regrouped clipboard delivers once")
}
for (const stacks of [[{id: "audio", modules: ["audio"]}], Cards.defaults]) {
    shell.Config.Settings.cardStacks = [{id: "mixed", modules: ["audio", "clipboard"]}]
    pasteRequest = preparePaste("audio")
    shell.Config.Settings.cardStacks = stacks
    shell.clipboardLoaded(pasteRequest)
    flush()
    assert.equal(shell.clipboardPaste, null, "Removing or moving clipboard from the current stack cancels paste")
    assert.equal(shell.pasteDelivery.running, false)
}
shell.Config.Settings.cardStacks = Cards.defaults
for (const invalidate of [
    () => {shell.sessionLocked = true},
    () => {shell.focusGeneration++},
    () => {shell.compositor.toplevels = [{address: "paste-target", lastIpcObject: {stableId: "1abc"}}]},
    () => {shell.widgetFocusGeneration++}
]) {
    shell.compositor.toplevels = [originalPasteWindow]
    pasteRequest = preparePaste()
    invalidate()
    shell.clipboardLoaded(pasteRequest)
    flush()
    assert.equal(shell.clipboardPaste, null, "Stale/locked/replaced target must cancel before input")
    assert.equal(shell.pasteDelivery.running, false)
}
shell.compositor.toplevels = [originalPasteWindow]
pasteRequest = preparePaste()
shell.openWidget("audio", true, "external")
shell.clipboardLoaded(pasteRequest)
flush()
assert.equal(shell.clipboardPaste, null, "Changing widgets cancels pending paste")
console.log("clipboard focus: confirmed load, retained live target, handoff, single delivery and cancellation pass")
shell.clipboardPaste = null
shell.ui.held = true
shell.pasteClipboard("epoch:7")
assert.equal(shell.clipboardPaste, null, "Held opening modifiers cannot reach paste delivery")
shell.ui.held = false
