// Run: node quickshell/tests/shell-state.js
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const vm = require("node:vm")
const Cards = require("../modules/topbar/CardModules.js")
const State = require("../modules/ShellState.js")
const Menu = require("../deck/DeckMenu.js")

const topbar = fs.readFileSync(path.join(__dirname, "../modules/Topbar.qml"), "utf8")

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
const engagedAudio = state
send({type: "open", page: "audio", engaged: false, screen: "deck"})
assert.equal(state, engagedAudio, "Returning to the same icon preserves engagement and selection")
send({type: "open", page: "network", engaged: false, screen: "external"})
assert.equal(state.page, "network", "Hover switches away from an engaged widget")
assert.equal(state.engaged, false, "The destination is a normal preview")
send({type: "open", page: "network", engaged: true, screen: "external"})
assert.equal(state.page, "network")
assert.equal(state.screen, "external")
send({type: "dismiss"})
assert.equal(State.barVisible(state, true, false), true, "Closing widget does not close radial")
assert.equal(State.barVisible(state, false, false), false)
send({type: "press"})
send({type: "open", page: "launcher", engaged: true, screen: "deck"})
send({type: "reset"})
assert.deepEqual(state, State.initial())

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
    Quickshell: {screens: [{name: "external"}]},
    Cards, Config: {Settings: {cardStacks: Cards.defaults, windowSwitcher: true}},
    keyboard: null, State, focusWidgetRequested: (...args) => focusRequests.push(args), ui: State.initial(), hoveredScreen: "", sessionLocked: false,
    interactionActive: false, previousToplevel: null, focusGeneration: 0, widgetFocusGeneration: 0,
    clipboardPaste: null, keyboardRequest: null, barModifiersHeld: 0,
    keyboardWait: {attempts: 0, start() {}, stop() {}},
    layoutsEnabled: true, barVisible: false, radial: {dismiss() {}, drainInput() {}}, widgetDismissed() {},
    compositor: {activeWindowAddress: "original", toplevels: [{address: "original"}],
        fullscreenScreens: [], monitorFor: () => ({focused: true}),
        activateWindow: address => focused.push(address), activateToplevel: window => focused.push(window)},
    Qt: {callLater: fn => callbacks.push(fn)}
})
const flush = () => { while (callbacks.length) callbacks.shift()() }
Object.defineProperty(shell, "widgetEngaged", {get: () => shell.ui.engaged})
// Exercise shared opening and the shipped delayed-hover scheduler after actual
// engagement, including a queued keyboard focus request which hover supersedes.
const hoverChanged = topbar.match(/            onHoverPageChanged: \{([\s\S]*?)^            \}/m)[1]
const hoverTriggered = topbar.match(/id: previewOpen[\s\S]*?onTriggered: \{([\s\S]*?)^                \}/m)[1]
let pendingPreview = false, drains = 0
shell.radial.drainInput = () => drains++
const hoverPanel = {hoverPage: "", screen: {name: "external"}}
const hoverContext = {root: shell, panel: hoverPanel, hoverPage: "", previewOpen: {
    stop() { pendingPreview = false }, restart() { pendingPreview = true }
}}
const hover = page => {
    hoverContext.hoverPage = hoverPanel.hoverPage = page
    vm.runInNewContext(hoverChanged, hoverContext)
    assert.equal(pendingPreview, !!page)
    if (pendingPreview) vm.runInNewContext(hoverTriggered, hoverContext)
}
for (const behaviour of Cards.barBehaviours) {
    shell.Config.Settings.barBehaviour = behaviour
    shell.ui = State.initial()
    shell.pressBar()
    shell.barVisible = true
    const latch = shell.ui.latched
    for (const page of ["launcher", "audio", "network", "launcher"]) {
        shell.openWidget(page, true, "external")
        shell.engageWidget()
        const next = page === "audio" ? "network" : "audio"
        focusRequests.length = 0
        const before = drains
        hover(page)
        assert.equal(shell.ui.engaged, true, "Same-icon hover cannot unlock the current card")
        hover(next)
        flush()
        assert.equal(shell.ui.page, next)
        assert.equal(shell.ui.engaged, false)
        assert.equal(drains, before + 1, "Leaving engagement drains held controller input")
        assert.deepEqual(focusRequests, [], "Stale explicit focus cannot activate the old card")
        assert.ok(shell.ui.held)
        assert.equal(shell.ui.latched, latch)
        shell.openWidget(page, true, "deck")
        flush()
        assert.deepEqual(focusRequests, [["deck", page]], "Click immediately switches monitor and keyboard target")
    }
    shell.releaseBar()
    assert.equal(shell.ui.held, null)
    assert.equal(shell.ui.engaged, true, "Opening-key release retains the switched card")
    shell.handoff(true)
    shell.barVisible = false
    hover("network")
    assert.equal(shell.ui.page, "", "A delayed hover cannot reopen capture-suppressed chrome")
    shell.sessionLocked = true
    shell.openWidget("audio", true, "external")
    assert.equal(shell.ui.page, "", "Lock rejects explicit switching")
    shell.sessionLocked = false
}
shell.radial.drainInput = () => {}
shell.ui = State.initial()
shell.barVisible = false
shell.finishInteraction()
flush()
focused.length = 0
focusRequests.length = 0

// Evaluate actual focus/grab requests: cards and bar share the existing grab;
// radial-only input keeps its prior exclusive policy. Native delivery is separate.
const focusBinding = topbar.match(/^            WlrLayershell.keyboardFocus: ([\s\S]*?)\n\n/m)[1]
const grabBinding = topbar.match(/HyprlandFocusGrab \{[\s\S]*?active: ([^\n]+)/)[1]
for (const engaged of [false, true])
for (const radial of [false, true]) for (const locked of [false, true]) for (const here of [false, true]) {
    const env = {root: {widgetEngaged: engaged, radialVisible: radial, sessionLocked: locked},
        panel: {widgetHere: here}, screen: {name: "external"}, keyboardScreen: here ? "external" : "deck",
        WlrKeyboardFocus: {Exclusive: 1, None: 0}}
    assert.equal(vm.runInNewContext(grabBinding, env), here && engaged && !locked)
    assert.equal(vm.runInNewContext(focusBinding, env), radial && !engaged && here && !locked ? 1 : 0)
}
console.log("card switching: interaction, delayed hover, click, held release, focus/grab targeting and suppression pass")
shell.Config.Settings.cardStacks = Cards.defaults
shell.dismissWidget()
shell.openWidget("unknown", true, "external")
assert.equal(shell.ui.page, "", "Unknown public input is rejected before reaching the reducer")
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
assert.equal(State.barVisible(shell.ui, false, false, "always"), true,
    "Ordinary media completion must leave Always Show visible")
assert.equal(focused.length, 0, "Media activation is not undone by focus restoration")
shell.player = {canRaise: false, raise: () => assert.fail("Unsupported Raise")}
shell.raiseMedia()
flush()
assert.equal(raises, 1)

// Exercise the activation callback through the real shared handoff methods.
const selected = shell.compositor.toplevels[0]
shell.ui = State.reduce(shell.ui, {type: "open", page: "switcher", engaged: true, screen: "external"})
shell.beginInteraction()
shell.activateToplevel(selected)
assert.equal(shell.ui.page, "")
assert.equal(State.barVisible(shell.ui, false, false, "always"), true,
    "Instant window activation handoff must leave Always Show visible")
assert.equal(focused.length, 0, "Activation waits until after handoff")
flush()
assert.deepEqual(focused, [selected])
shell.finishInteraction()
flush()
focused.length = 0
shell.activateToplevel(selected)
shell.sessionLocked = true
flush()
assert.equal(focused.length, 0, "Lock cancels deferred activation")
shell.sessionLocked = false
shell.activateToplevel(selected)
shell.beginInteraction()
flush()
assert.equal(focused.length, 0, "A new interaction cancels deferred activation")
shell.handoff()
shell.finishInteraction()
flush()

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

// Capture-only handoff suppresses held/latched/hovered/always bars without animation.
for (const behaviour of ["keyboard", "keyboard-mouse", "toggle", "always"]) {
    shell.ui = Object.assign(State.initial(), {held: {screen: "external", toggle: false}, latched: true, page: "audio", engaged: true})
    shell.hoveredScreen = "external"
    shell.instantHandoff(true)
    assert.equal(shell.instantBarHide, true)
    assert.equal(shell.hoveredScreen, "")
    assert.equal(shell.ui.page, "")
    assert.equal(State.barVisible(shell.ui, false, true, behaviour), false)
    assert.equal(State.reduce(shell.ui, {type: "release"}).suppressed, true)
    flush()
    assert.equal(shell.instantBarHide, false)
}
assert.match(fs.readFileSync(path.join(__dirname, "../modules/Topbar.qml"), "utf8"),
    /function capture\(\): void \{ root\.instantHandoff\(true\) \}/)
const captures = []
deck.Quickshell.execDetached = command => captures.push(Array.from(command))
deck.activate({action: "screenshot"}, 0)
assert.equal(captures.length, 0, "Dismiss the shell before capture")
assert.equal(shell.instantBarHide, true, "Controller capture must bypass close animations")
assert.equal(State.barVisible(shell.ui, false, false, "always"), false,
    "The real controller screenshot caller must explicitly suppress Always Show")
flush()
assert.deepEqual(captures, [
    ["icewine", "screenshot"]
], "Dispatch Gradia FULL capture after dismissing the shell")

const controllerActions = []
deck.compositor = {dispatch: command => controllerActions.push(command),
    toggleFullscreen: () => controllerActions.push("fullscreen")}
for (const action of ["close", "fullscreen"]) {
    deck.activate({action}, 0)
    assert.equal(State.barVisible(shell.ui, false, false, "always"), true,
        `${action}: ordinary controller completion resumes Always Show`)
}
assert.equal(controllerActions.length, 2)
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
shell.Quickshell = {screens: [{name: "external"}], execDetached() {}}
const originalPasteWindow = {address: "paste-target", lastIpcObject: {stableId: "1abc"}}
shell.compositor.toplevels = [originalPasteWindow]
shell.compositor.activeWindowAddress = originalPasteWindow.address
const preparePaste = (page = "notifications") => {
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
assert.equal(State.barVisible(shell.ui, false, false, "always"), true,
    "Confirmed clipboard handoff must leave passive Always Show chrome visible")
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
shell.ui = State.reduce(shell.ui, {type: "press", screen: "external"})
shell.pasteClipboard("epoch:7")
assert.equal(shell.clipboardPaste, null, "Held opening modifiers cannot reach paste delivery")
shell.ui = State.reduce(shell.ui, {type: "release"})

// All visibility modes share engagement/radial/handoff lifetime rules.
for (const behaviour of Cards.barBehaviours) {
    let mode = State.initial()
    assert.equal(State.barVisible(mode, false, false, behaviour), behaviour === "always")
    mode = State.reduce(mode, {type: "press", behaviour})
    assert.equal(State.barVisible(mode, false, false, behaviour), true)
    assert.equal(State.reduce(mode, {type: "press", behaviour}), mode, "Repeat press does not toggle twice")
    mode = State.reduce(mode, {type: "release"})
    assert.equal(State.barVisible(mode, false, false, behaviour), ["toggle", "always"].includes(behaviour))
    if (behaviour === "toggle") {
        mode = State.reduce(mode, {type: "press", behaviour})
        assert.equal(State.barVisible(mode, false, false, behaviour), false, "Toggle hides on second press before release")
        mode = State.reduce(mode, {type: "release"})
    }
    mode = State.reduce(mode, {type: "open", page: "audio", engaged: true, screen: "external"})
    assert.equal(State.barVisible(mode, false, false, behaviour), true)
    mode = State.reduce(mode, {type: "hide"})
    assert.equal(State.barVisible(mode, false, true, behaviour), false, "Explicit handoff defeats hover and Always Show")
    assert.equal(State.barVisible(mode, true, false, behaviour), true, "Controller can reopen after handoff")
    mode = State.reduce(mode, {type: "resume"})
    assert.equal(State.barVisible(mode, false, true, behaviour), true)
}
// Fullscreen normalises every configured press to the same temporary owner.
for (const behaviour of Cards.barBehaviours) {
    const held = State.reduce(Object.assign(State.initial(), {latched: true}), {
        type: "press", behaviour, fullscreen: true, screen: "external"})
    assert.equal(State.barVisible(held, false, false, behaviour), true)
    const released = State.reduce(held, {type: "release"})
    assert.equal(State.barVisible(released, false, false, behaviour), behaviour === "always")
}
const fullscreenChanged = topbar.match(/function onFullscreenScreensChanged\(\) \{([\s\S]*?)^        \}/m)[1]
for (const screens of [["external"], ["deck"]]) {
    shell.ui = State.reduce(State.initial(), {type: "press", behaviour: "toggle", screen: "external"})
    shell.compositor.fullscreenScreens = screens
    vm.runInNewContext(fullscreenChanged, {root: shell, State})
    shell.ui = State.reduce(shell.ui, {type: "open", page: "audio", engaged: true, screen: "deck"})
    shell.releaseBar()
    shell.dismissWidget()
    assert.equal(State.barVisible(shell.ui, false, false, "toggle"), !screens.includes("external"),
        "Fullscreen changes only its held output; widget state copies do not lose that conversion")
}
shell.compositor.fullscreenScreens = []
// Switcher adds no bar owner; preserve each independent reason once.
for (const [mode, radial, hovered, behaviour] of [
    [State.initial(), false, false, "keyboard"],
    [State.reduce(State.initial(), {type: "press"}), false, false, "keyboard"],
    [State.reduce(State.initial(), {type: "press", behaviour: "toggle"}), false, false, "toggle"],
    [State.initial(), true, false, "keyboard"],
    [State.initial(), false, true, "keyboard-mouse"],
    [State.initial(), false, false, "always"]
]) {
    const visible = State.barVisible(mode, radial, hovered, behaviour)
    const opened = State.reduce(mode, {type: "open", page: "switcher", engaged: true, screen: "external"})
    assert.equal(State.barVisible(opened, radial, hovered, behaviour), visible)
    assert.deepEqual(State.reduce(opened, {type: "dismiss"}), mode)
}
// Run the shipped focus-grab dismissal callback as well as selection.
const clearSwitcher = topbar.match(/onCleared: ([\s\S]*?)^            \}/m)[1]
for (const page of ["launcher", "audio", "switcher"]) {
    shell.openWidget(page, true, "external")
    vm.runInNewContext(clearSwitcher, {root: shell, panel: {widgetHere: false}})
    assert.equal(shell.ui.page, page, "An old monitor's cleared grab cannot dismiss the new target")
    vm.runInNewContext(clearSwitcher, {root: shell, panel: {widgetHere: true}})
    assert.equal(shell.ui.page, "", "Compositor grab dismissal closes every engaged widget")
    assert.equal(shell.previousToplevel, null, "External focus wins over retained app restoration")
    flush()
}
for (const close of [() => shell.dismissWidget(), () => shell.activateToplevel(shell.compositor.toplevels[0]),
    () => vm.runInNewContext(clearSwitcher, {root: shell, panel: {widgetHere: true}})]) {
    shell.Config.Settings.barBehaviour = "toggle"
    shell.ui = State.reduce(State.initial(), {type: "press", behaviour: "toggle"})
    shell.ui = State.reduce(shell.ui, {type: "release"})
    shell.openWidget("switcher", true, "external")
    close()
    assert.equal(shell.ui.page, "")
    assert.equal(shell.ui.latched, true, "Switcher exit preserves independent toggle latch")
    assert.equal(State.barVisible(shell.ui, false, false, "toggle"), true)
    flush()
    shell.handoff()
    shell.finishInteraction()
    flush()
}
console.log("switcher visibility preserves independent hold, toggle, hover, radial and Always Show reasons")
// Always-visible chrome must not prevent restoring focus after a widget closes.
shell.ui = State.initial()
shell.interactionWanted = false
shell.barVisible = true
shell.compositor.activeWindowAddress = originalPasteWindow.address
shell.beginInteraction()
shell.finishInteraction()
flush()
assert.equal(focused.at(-1), originalPasteWindow.address)
console.log("bar modes and original-target focus lifetime pass; native fixture owns geometry/grab checks")

// Execute the actual launcher caller and shared handoff, with only platform
// launch/focus delivery substituted. No later focus/navigation event resumes it.
shell.clipboardPaste = null
focused.length = 0
shell.openWidget("launcher", true, "external")
flush()
const launched = []
const launcher = controller("../modules/topbar/LauncherCard.qml", {
    active: true, LauncherSearch: require("../modules/topbar/LauncherSearch.js"),
    handoffRequested: () => shell.handoff(),
    Quickshell: {env: () => "/fixture", execDetached: options => launched.push(options)}
})
launcher.launch({command: ["fixture-app"]})
shell.finishInteraction()
flush()
assert.equal(launched.length, 1)
assert.equal(shell.ui.page, "")
assert.equal(State.barVisible(shell.ui, false, false, "always"), true,
    "Real launcher completion restores Always Show without any later event")
assert.equal(focused.length, 0, "Launcher handoff still cancels stale focus restoration")
shell.dismiss()
assert.equal(State.barVisible(shell.ui, false, false, "always"), false,
    "Explicit hide remains suppressed independently of ordinary handoffs")
console.log("ordinary launcher/media/clipboard/window/controller handoffs preserve Always Show; capture/explicit hide still suppress")

// Execute actual Topbar handoff and delivery readiness with a mocked compositor.
const oskCallbacks = [], oskCalls = [], oskTarget = {address: "app"}
const keyboardShell = controller("../modules/Topbar.qml", {
    Quickshell: {screens: [{name: "screen"}]},
    State, Cards, Config: {Settings: {oskAccess: "launcher", barBehaviour: "always", cardStacks: Cards.defaults}},
    focusWidgetRequested() {},
    keyboard: {busy: false, show() { oskCalls.push("show") }, hide() {}}, keyboardRequest: null,
    keyboardWait: {attempts: 0, start() { oskCalls.push("wait") }, stop() {}}, barModifiersHeld: 0,
    sessionLocked: false, radialVisible: false, interactionActive: true,
    previousToplevel: oskTarget, focusGeneration: 0, widgetFocusGeneration: 0,
    ui: State.reduce(State.initial(), {type: "open", page: "launcher", engaged: true, screen: "screen"}),
    hoveredScreen: "screen", clipboardPaste: null,
    radial: {drainInput() {}, dismiss() {}}, widgetDismissed() {},
    compositor: {activeWindowAddress: "app", toplevels: [oskTarget],
        fullscreenScreens: [], monitorFor: () => ({focused: true}),
        activateToplevel(window) { oskCalls.push(window) }, activateWindow() { throw Error("wrong restoration path") }},
    Qt: {callLater: fn => oskCallbacks.push(fn)}
})
const oskFlush = () => { while (oskCallbacks.length) oskCallbacks.shift()() }
function prepareKeyboard(mode = "launcher") {
    keyboardShell.cancelKeyboardRequest(); oskFlush(); oskCalls.length = 0
    Object.assign(keyboardShell, {sessionLocked: false, radialVisible: false, interactionActive: true,
        previousToplevel: oskTarget, clipboardPaste: null, barModifiersHeld: 0,
        ui: State.reduce(State.initial(), {type: "open", page: "launcher", engaged: true, screen: "screen"})})
    keyboardShell.Config.Settings.oskAccess = mode
    keyboardShell.keyboard.busy = false
    Object.assign(keyboardShell.compositor, {activeWindowAddress: "app", toplevels: [oskTarget]})
}
for (const mode of ["launcher", "topbar"]) {
    prepareKeyboard(mode)
    keyboardShell.showKeyboard(mode)
    assert.equal(keyboardShell.ui.page, "")
    assert.equal(keyboardShell.ui.suppressed, false, "Ordinary handoff preserves Always Show")
    assert.equal(oskCalls.length, 0, "No keyboard before the deferred handoff callback")
    oskFlush()
    assert.equal(oskCalls[0], oskTarget, "Restore exact live object, never address replacement")
    assert(!oskCalls.includes("show"))
    keyboardShell.finishKeyboardRequest()
    assert.equal(oskCalls.at(-1), "show")
    assert.equal(keyboardShell.keyboardRequest, null)
}
for (const invalidate of [
    () => { keyboardShell.sessionLocked = true },
    () => { keyboardShell.Config.Settings.oskAccess = "none" },
    () => { keyboardShell.compositor.toplevels = [{address: "app"}] },
    () => { keyboardShell.compositor.activeWindowAddress = "other" },
    () => { keyboardShell.beginInteraction() },
    () => { keyboardShell.handoff(true) }
]) {
    for (const afterRestore of [false, true]) {
        prepareKeyboard(); keyboardShell.showKeyboard("launcher")
        if (afterRestore) oskFlush()
        invalidate(); oskFlush(); keyboardShell.finishKeyboardRequest()
        assert(!oskCalls.includes("show"), "Lock/mode/identity/focus/new interaction cancels pending open")
        assert.equal(keyboardShell.keyboardRequest, null)
    }
}
for (const mode of ["none", "topbar"]) {
    prepareKeyboard(mode); keyboardShell.showKeyboard("launcher"); oskFlush()
    assert.equal(keyboardShell.keyboardRequest, null)
}
for (const invalidate of [() => {keyboardShell.previousToplevel = null},
    () => {keyboardShell.keyboard.busy = true}]) {
    prepareKeyboard(); invalidate(); keyboardShell.showKeyboard("launcher"); oskFlush()
    assert.equal(keyboardShell.keyboardRequest, null)
}
prepareKeyboard(); keyboardShell.showKeyboard("launcher"); keyboardShell.showKeyboard("launcher"); oskFlush()
assert.equal(oskCalls.filter(value => value === oskTarget).length, 1, "Superseded callback cannot restore or cancel the new request")
keyboardShell.compositor.activeWindowAddress = ""
for (let attempt = 0; attempt < 31; ++attempt) keyboardShell.finishKeyboardRequest()
assert.equal(keyboardShell.keyboardRequest, null, "A target which never regains focus expires without opening")
assert(!oskCalls.includes("show"))
console.log("OSK focus: exact retained target, both desktop entries, Always Show, supersession and bounded cancellation pass")

// Execute the actual passive modifier handler used by remapped opening chords.
const openingModifier = topbar.match(/name: "topbarOpeningModifier"[\s\S]*?onReleased: \{([\s\S]*?)^        \}/m)[1]
prepareKeyboard()
keyboardShell.Config.Settings.barBehaviour = "keyboard"
keyboardShell.ui = State.initial()
keyboardShell.pressBar()
keyboardShell.barModifiersHeld = 2
vm.runInNewContext(openingModifier, {root: keyboardShell})
assert.equal(keyboardShell.barModifiersHeld, 1)
assert.ok(keyboardShell.ui.held, "Unrelated modifier release must not end the taskbar hold")
keyboardShell.showKeyboard("launcher")
assert.equal(keyboardShell.keyboardRequest.awaitingRelease, true)
vm.runInNewContext(openingModifier, {root: keyboardShell})
oskFlush()
keyboardShell.finishKeyboardRequest()
assert.equal(oskCalls.filter(value => value === "show").length, 1, "Remapped opening modifier drains before keyboard handoff")
vm.runInNewContext(openingModifier, {root: keyboardShell})
assert.equal(keyboardShell.barModifiersHeld, 0, "Late releases after reload cannot underflow")
console.log("remapped modifiers: passive release preserves hold and drains keyboard handoff once")
