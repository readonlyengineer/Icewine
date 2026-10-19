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

const mask = topbar.slice(topbar.indexOf('WlrLayershell.namespace: "icewine:widgets"')).match(/mask: Region \{\n([\s\S]*?)^            \}/m)[1]
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

// Retired Screenshot requests are rejected; Notifications is the Clipboard entry.
send({type: "open", page: "screenshot", engaged: true, screen: "external"})
assert.equal(state.page, "")
// Execute the actual QML controller methods, with only platform I/O replaced.
send({type: "open", page: "notifications", engaged: true, screen: "external"})
assert.equal(state.page, "notifications")
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
    clipboardPaste: null, keyboardRequest: null, barModifiersHeld: 0,
    keyboardWait: {attempts: 0, start() {}, stop() {}},
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
shell.activateSwitcherWindow(selected)
assert.equal(shell.ui.page, "")
assert.equal(State.barVisible(shell.ui, false, false, "always"), true,
    "Instant window activation handoff must leave Always Show visible")
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
assert.equal(State.barVisible(shell.ui, false, false, "always"), false,
    "The real controller screenshot caller must explicitly suppress Always Show")
flush()
assert.deepEqual(captures, [
    ["icewine", "screenshot", "screen"]
], "Dispatch the selected output-capture utility after dismissing the shell")

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
shell.Quickshell = {execDetached() {}}
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
shell.ui.held = true
shell.pasteClipboard("epoch:7")
assert.equal(shell.clipboardPaste, null, "Held opening modifiers cannot reach paste delivery")
shell.ui.held = false

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
// Switcher intent must not become an independent reason to reveal the bar.
for (const behaviour of Cards.barBehaviours) for (const held of [false, true]) {
    for (const latched of [false, true]) for (const hovered of [false, true]) {
        for (const radial of [false, true]) {
            let mode = Object.assign(State.initial(), {held, latched})
            const visible = State.barVisible(mode, radial, hovered, behaviour)
            mode = State.reduce(mode, {type: "open", page: "switcher", engaged: true, screen: "external"})
            assert.equal(State.barVisible(mode, radial, hovered, behaviour), visible)
            mode = State.reduce(mode, {type: "dismiss"})
            assert.equal(State.barVisible(mode, radial, hovered, behaviour), visible)
            assert.equal(mode.held, held)
            assert.equal(mode.latched, latched)
        }
    }
}
// Run the shipped focus-grab dismissal callback as well as selection.
const clearSwitcher = topbar.match(/onCleared: ([\s\S]*?)^            \}/m)[1]
for (const close of [() => shell.dismissWidget(), () => shell.activateSwitcherWindow(shell.compositor.toplevels[0]),
    () => vm.runInNewContext(clearSwitcher, {root: shell})]) {
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
// Evaluate the shipped bindings, including Bottom popouts and native requests,
// rather than implementing an alternative geometry model inside the test.
const expression = (source, property) => source.match(new RegExp(`^ *${property}: (.+)$`, "m"))[1]
const surfaceSource = topbar.split("id: surface")[1].split("// Consume")[0]
const popoutSource = topbar.split("id: statusPopout")[1]
const edgeSource = topbar.split("id: edge\n")[1].split("HoverHandler")[0]
for (const behaviour of Cards.barBehaviours) for (const location of Cards.barLocations) {
    for (const height of [80, 600, 1440]) for (const visible of [false, true]) {
        const env = {root: {bottomBar: location === "bottom", barVisible: visible, barHeight: 38, barGap: 0, barExtent: 38, sessionLocked: false},
            Config: {Settings: {barBehaviour: behaviour, barLocation: location}},
            panel: {height, width: 1280}, input: {height}, parent: {height}, height: 38, implicitHeight: 500}
        const value = source => vm.runInNewContext(source, env)
        const reservation = value(expression(topbar, "readonly property int reservation"))
        assert.equal(reservation, visible && location !== "above" ? 38 : 0)
        const y = value(expression(surfaceSource, "y"))
        if (visible) assert.equal(y, location === "bottom" ? height - 38 : 0)
        else assert.ok(y <= -38 || y >= height, "Hidden visual leaves the usable screen")
        env.height = value(expression(popoutSource, "height"))
        const popoutY = value(expression(popoutSource, "y"))
        assert.ok(popoutY >= 0 && popoutY + env.height <= height, "Popout remains inside native usable height")
        assert.equal(value(expression(edgeSource, "enabled")), behaviour === "keyboard-mouse")
        env.height = 1
        assert.equal(value(expression(edgeSource, "y")), location === "bottom" ? height - 1 : 0)
        env.root.sessionLocked = true
        assert.equal(value(expression(edgeSource, "enabled")), false, "Lock removes mouse edge input")
    }
}
// Always-visible chrome must not prevent restoring focus after a widget closes.
shell.ui = State.initial()
shell.interactionWanted = false
shell.barVisible = true
shell.compositor.activeWindowAddress = originalPasteWindow.address
shell.beginInteraction()
shell.finishInteraction()
flush()
assert.equal(focused.at(-1), originalPasteWindow.address)
console.log("bar modes: press/release/repeat, toggle, handoff, lock edge, all 12 placements and passive focus pass")

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
    State, Cards, Config: {Settings: {oskAccess: "launcher", barBehaviour: "always", cardStacks: Cards.defaults}},
    focusWidgetRequested() {},
    keyboard: {busy: false, show() { oskCalls.push("show") }, hide() {}}, keyboardRequest: null,
    keyboardWait: {attempts: 0, start() { oskCalls.push("wait") }, stop() {}}, barModifiersHeld: 0,
    sessionLocked: false, radialVisible: false, interactionActive: true,
    previousWindow: "app", previousToplevel: oskTarget, focusGeneration: 0, widgetFocusGeneration: 0,
    ui: State.reduce(State.initial(), {type: "open", page: "launcher", engaged: true, screen: "screen"}),
    hoveredScreen: "screen", clipboardPaste: null,
    radial: {drainInput() {}, dismiss() {}}, widgetDismissed() {},
    compositor: {activeWindowAddress: "app", toplevels: [oskTarget],
        activateToplevel(window) { oskCalls.push(window) }, activateWindow() { throw Error("wrong restoration path") }},
    Qt: {callLater: fn => oskCallbacks.push(fn)}
})
const oskFlush = () => { while (oskCallbacks.length) oskCallbacks.shift()() }
function prepareKeyboard(mode = "launcher") {
    keyboardShell.cancelKeyboardRequest(); oskFlush(); oskCalls.length = 0
    Object.assign(keyboardShell, {sessionLocked: false, radialVisible: false, interactionActive: true,
        previousWindow: "app", previousToplevel: oskTarget, clipboardPaste: null, barModifiersHeld: 0,
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
for (const invalidate of [() => {keyboardShell.previousWindow = ""},
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

// Default keyboard-autohide: press opening chord, click/tap action, release.
for (const mode of ["topbar", "launcher"]) for (const modifierFirst of [false, true]) {
    prepareKeyboard(mode)
    keyboardShell.Config.Settings.barBehaviour = "keyboard"
    keyboardShell.interactionActive = false
    keyboardShell.ui = State.initial()
    keyboardShell.barModifiersHeld = 1
    keyboardShell.pressBar()
    if (mode === "launcher") keyboardShell.openWidget("launcher", true, "screen")
    keyboardShell.showKeyboard(mode)
    assert.equal(keyboardShell.keyboardRequest.window, oskTarget)
    assert.equal(keyboardShell.keyboardRequest.awaitingRelease, true)
    oskFlush()
    assert(!oskCalls.includes("show") && !oskCalls.includes(oskTarget), "Held action neither opens nor restores early")
    if (!modifierFirst) {
        keyboardShell.releaseBar() // grave first; Super still physically down
        oskFlush()
        assert.equal(keyboardShell.ui.held, true)
        assert.equal(keyboardShell.keyboardRequest.awaitingRelease, true)
        assert(!oskCalls.includes("show"))
    }
    keyboardShell.barModifiersHeld = 0
    keyboardShell.releaseBar()
    oskFlush()
    assert.equal(oskCalls.filter(value => value === oskTarget).length, 1)
    keyboardShell.finishKeyboardRequest()
    assert.equal(oskCalls.filter(value => value === "show").length, 1)
    keyboardShell.releaseBar(); oskFlush()
    assert.equal(oskCalls.filter(value => value === "show").length, 1, "Second release cannot reopen")
}
for (const invalidate of [
    () => {keyboardShell.sessionLocked = true},
    () => {keyboardShell.Config.Settings.oskAccess = "none"},
    () => {keyboardShell.compositor.toplevels = [{address: "app"}]},
    () => {keyboardShell.compositor.activeWindowAddress = "other"},
    () => {keyboardShell.focusGeneration++},
    () => {keyboardShell.dismiss()}
]) {
    prepareKeyboard(); keyboardShell.ui.held = true; keyboardShell.barModifiersHeld = 1
    keyboardShell.showKeyboard("launcher"); invalidate()
    keyboardShell.barModifiersHeld = 0; keyboardShell.releaseBar(); oskFlush()
    assert(!oskCalls.includes("show"), "Retained held request still obeys all cancellation gates")
    assert.equal(keyboardShell.keyboardRequest, null)
}
console.log("OSK held shortcut: both actions retain target, both release orders defer until modifier up, stale intent cancels")
