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
const text = JSON.stringify({workspace: 1, identity: "31", effective: "dwindle", default: "scrolling", override: "dwindle"})
assert.equal(Layouts.status(text, 1).effective, "dwindle")
assert.throws(() => Layouts.status(text, 2))
assert.throws(() => Layouts.status("ok", 1))
assert.throws(() => Layouts.status(text.replace("dwindle", "invalid"), 1))

// Exercise the real adapter functions, including a query in flight and focus
// moving before delivery. The command must keep the ID captured by selection.
const adapter = fs.readFileSync(path.join(__dirname, "../adapters/Hyprland.qml"), "utf8")
const context = vm.createContext({Layouts, layoutAvailable: true, layoutPending: false,
    layoutStatus: {workspace: 1, identity: "31"}, layoutProcess: {running: true}, nextLayoutRequest: null, layoutActionError: "", layoutErrorWorkspace: 0, layoutErrorIdentity: ""})
for (const name of ["selectLayout", "flushLayoutRequest"]) {
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
context.stdout.text = JSON.stringify({workspace: 2, identity: "32", effective: "monocle", default: "scrolling", override: ""})
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
console.log("PASS layout adapter: validation, captured focus, queued selection, semantic IPC failure and external state")
