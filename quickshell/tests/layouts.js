const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const vm = require("node:vm")
const Layouts = require("../modules/topbar/Layouts.js")
for (const id of [1, -1337]) {
    const request = Layouts.request(id, "31", "master")
    assert.match(request[2], new RegExp(`select\\(${id},"31","master"\\)`))
}
for (const [id, layout] of [[1.5,"master"], [1,"invalid"]])
    assert.throws(() => Layouts.request(id, "31", layout))
const text = JSON.stringify({workspace: 1, identity: "31", effective: "dwindle", default: "scrolling", override: "dwindle", autofullscreen: false})
assert.equal(Layouts.status(text, 1).effective, "dwindle")
assert.throws(() => Layouts.status(text, 2))
assert.throws(() => Layouts.status("ok", 1))
assert.throws(() => Layouts.status(text.replace("dwindle", "invalid"), 1))

// Exercise the real adapter functions, including a query in flight and focus
// moving before delivery. The command must keep the ID captured by selection.
const adapter = fs.readFileSync(path.join(__dirname, "../adapters/Hyprland.qml"), "utf8")
const context = vm.createContext({Layouts, layoutActive: true, layoutRefreshPending: false, layoutAvailable: true, layoutPending: false,
    layoutStatus: {workspace: 1, identity: "31"}, layoutProcess: {running: true}, nextLayoutRequest: null, layoutActionError: "", layoutErrorWorkspace: 0, layoutErrorIdentity: ""})
for (const name of ["selectLayout", "selectAutofullscreen", "requestLayoutChange", "flushLayoutRequest"]) {
    const start = adapter.indexOf(`    function ${name}(`)
    const end = adapter.indexOf("\n    }", start) + 6
    vm.runInContext(adapter.slice(start, end), context)
}
vm.runInContext('selectLayout("master")', context)
context.layoutStatus = {workspace: 2, identity: "32", effective: "master"}
context.layoutProcess.running = false
vm.runInContext('flushLayoutRequest()', context)
assert.match(context.layoutProcess.command[2], /select\(1,"31","master"\)/)

// Execute the real completion handler: semantic IPC failure has exit status 0.
const start = adapter.indexOf("        onExited: (exitCode, exitStatus) => {", adapter.indexOf("property Process layoutProcess"))
const end = adapter.indexOf("\n        }", start) + 10
const handler = adapter.slice(start, end).replace("onExited:", "")
const errorBinding = adapter.match(/readonly property string layoutError: ([\s\S]*?)\n    property string layoutUnavailable/)[1]
Object.defineProperty(context, "layoutError", { get: () => vm.runInContext(errorBinding, context) })
context.adapter = context
context.Qt = {callLater: fn => { context.later = fn }}
context.action = true
context.workspace = 1
context.identity = "31"
context.layoutWorkspaceId = 2
context.stdout = {text: "error: workspace removed"}
context.stderr = {text: ""}
vm.runInContext(`(${handler})(0, 0)`, context)
assert.equal(context.layoutActionError, "error: workspace removed")
assert.equal(context.layoutError, "", "A workspace1 action error must not be attributed to focused workspace2")
assert.equal(context.layoutStatus.workspace, 2, "Failed action must not invent layout success")
context.action = false
context.stdout.text = text
vm.runInContext(`(${handler})(0, 0)`, context)
assert.equal(context.layoutStatus.effective, "master", "Stale success must not overwrite current focus")
context.stdout.text = "error: old workspace unavailable"
vm.runInContext(`(${handler})(0, 0)`, context)
assert.equal(context.layoutStatus.workspace, 2)
assert.equal(context.layoutStatus.effective, "master", "Stale failure must not clear newer workspace2/master status")
assert.equal(context.layoutUnavailable ?? "", "")
assert.equal(context.layoutError, "")
context.workspace = 2
context.stdout.text = "error: unavailable"
vm.runInContext(`(${handler})(0, 0)`, context)
assert.equal(context.layoutStatus, null)
assert.match(context.layoutUnavailable, /Error/)
context.stdout.text = JSON.stringify({workspace: 2, identity: "32", effective: "monocle", default: "scrolling", override: "", autofullscreen: true})
vm.runInContext(`(${handler})(0, 0)`, context)
assert.equal(context.layoutStatus.effective, "monocle", "External changes must use actual compositor state")
assert.equal(context.layoutUnavailable, "")
// Matching errors remain visible, and ID reuse must not inherit an old error.
context.layoutWorkspaceId = 1
context.layoutStatus = {workspace: 1, identity: "31", effective: "scrolling"}
assert.equal(context.layoutError, "error: workspace removed")
context.layoutStatus = {workspace: 1, identity: "6e6577", effective: "master"}
assert.equal(context.layoutError, "")
for (const identity of ["3", "xx"])
    assert.throws(() => Layouts.request(1, identity, "master"))
assert.throws(() => Layouts.status(text.replace('"31"', '"x"'), 1))
// The same queue captures workspace identity for boolean preference changes.
context.layoutProcess.running = true
context.layoutPending = false
vm.runInContext('selectAutofullscreen(false)', context)
context.layoutStatus = {workspace: 3, identity: "33"}
context.layoutProcess.running = false
vm.runInContext('flushLayoutRequest()', context)
assert.match(context.layoutProcess.command[2], /select_autofullscreen\(1,"6e6577",false\)/)
assert.throws(() => Layouts.status(text.replace('"autofullscreen":false', '"autofullscreen":"false"'), 1))
assert.throws(() => Layouts.request(1, "31", null))
// Event-driven refreshes execute the real adapter functions and handlers.
const refreshContext = vm.createContext({Layouts, layoutActive: false, layoutWorkspaceId: 1,
    layoutStatus: null, layoutUnavailable: "", layoutRefreshPending: false,
    layoutProcess: {running: false}, nextLayoutRequest: null, layoutPending: false})
refreshContext.adapter = refreshContext
const deferred = []
refreshContext.Qt = {callLater: fn => deferred.push(fn)}
for (const name of ["refreshLayout", "requestLayoutChange", "flushLayoutRequest"]) {
    const start = adapter.indexOf(`    function ${name}(`)
    const end = adapter.indexOf("\n    }", start) + 6
    vm.runInContext(adapter.slice(start, end), refreshContext)
}
const activeChanged = adapter.match(/    onLayoutActiveChanged: (\{[\s\S]*?\n    \})/)[1]
const workspaceChanged = adapter.match(/    onLayoutWorkspaceIdChanged: (.*)/)[1]
function show(active) {
    refreshContext.layoutActive = active
    vm.runInContext(activeChanged, refreshContext)
}
function focus(workspace) {
    refreshContext.layoutWorkspaceId = workspace
    vm.runInContext(workspaceChanged, refreshContext)
}
function complete(state, action = false) {
    refreshContext.workspace = refreshContext.layoutProcess.workspace
    refreshContext.action = action
    refreshContext.stdout = {text: typeof state === "string" ? state : JSON.stringify(state)}
    refreshContext.stderr = {text: ""}
    refreshContext.layoutProcess.running = false
    vm.runInContext(`(${handler})(0, 0)`, refreshContext)
}
function drain() {
    while (deferred.length) deferred.shift()()
}
const state = {workspace: 1, identity: "31", effective: "master", default: "scrolling", override: "", autofullscreen: false}
vm.runInContext("refreshLayout()", refreshContext)
focus(2)
assert.equal(refreshContext.layoutProcess.running, false, "Disabled startup and workspace changes must not query")
assert.doesNotMatch(adapter, /layoutPoll|interval: 750/, "No recurring layout status timer")
show(true)
assert.equal(refreshContext.layoutProcess.workspace, 2, "First open queries current workspace")
focus(3)
focus(1)
assert.equal(refreshContext.layoutProcess.workspace, 2, "Workspace changes coalesce behind an in-flight query")
complete({...state, workspace: 2, identity: "32"})
assert.equal(refreshContext.layoutStatus, null, "Stale response is rejected")
drain()
assert.equal(refreshContext.layoutProcess.workspace, 1)
complete(state)
assert.equal(refreshContext.layoutStatus.effective, "master")
// Opening again during an old same-workspace query must not accept its result.
vm.runInContext("refreshLayout()", refreshContext)
show(false)
show(true)
complete({...state, effective: "dwindle"})
assert.equal(refreshContext.layoutStatus, null)
drain()
complete(state)
assert.equal(refreshContext.layoutStatus.effective, "master")
// An action completion queues a query, but closing before callLater suppresses it.
complete("ok", true)
show(false)
drain()
assert.equal(refreshContext.layoutProcess.running, false)
assert.equal(refreshContext.layoutStatus, null)
// Hidden query completion cannot publish state or restart queries, even on error.
show(true)
show(false)
complete("error: unavailable")
drain()
assert.equal(refreshContext.layoutUnavailable, "")
assert.equal(refreshContext.layoutProcess.running, false)
// Successful local mutation refreshes current workspace while open.
show(true)
complete(state)
complete("ok", true)
drain()
assert.equal(refreshContext.layoutProcess.running, true)
assert.equal(refreshContext.layoutProcess.workspace, 1)
complete(state)
// Activity follows the selected, settled card on the owning monitor, even when
// it was reached through stack navigation while ui.page still names Launcher.
const topbar = fs.readFileSync(path.join(__dirname, "../modules/Topbar.qml"), "utf8")
const activity = topbar.match(/readonly property bool layoutActive: ([\s\S]*?)\n    readonly property int barHeight/)[1]
for (const layoutsEnabled of [false, true]) for (const sessionLocked of [false, true])
    for (const widgetHere of [false, true]) for (const layoutActive of [false, true]) {
        const panels = {instances: [{widgetHere: false, layoutActive: true}, {widgetHere, layoutActive}]}
        const actual = vm.runInNewContext(activity, {layoutsEnabled, sessionLocked, panels})
        assert.equal(actual, layoutsEnabled && !sessionLocked && widgetHere && layoutActive)
    }
for (const shell of ["Desktop", "Handheld"]) {
    const source = fs.readFileSync(path.join(__dirname, `../${shell}.qml`), "utf8")
    const binding = source.match(/layoutActive: (.*)/)[1]
    for (const active of [false, true])
        assert.equal(vm.runInNewContext(binding, {topbar: {layoutActive: active}}), active)
    if (shell === "Handheld") assert.match(source, /layoutsEnabled: false/)
}
console.log("PASS layout refresh: first open, coalesced focus, reopen, hidden completion, mutation and disabled handheld")
console.log("PASS layout adapter: validation, captured focus, queued selection, semantic IPC failure and external state")
