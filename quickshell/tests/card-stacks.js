// Run: node quickshell/tests/card-stacks.js
const assert = require("node:assert/strict")
const Cards = require("../modules/topbar/CardModules.js")

assert.equal(Cards.modules.length, 13)
assert.equal(Cards.modules.includes("screenshot"), false)
assert.deepEqual(Cards.containing(Cards.defaults, "clipboard"),
    {id: "notifications", modules: ["notifications", "clipboard"]})
assert.equal(Cards.validate(Cards.defaults), Cards.defaults)
assert.deepEqual(Cards.defaults.flatMap(stack => stack.modules).sort(), [...Cards.modules].sort())
assert.deepEqual(Cards.preferences({notificationToasts: false}), {notificationToasts: false})
assert.deepEqual(Cards.validate([]), [])
const mixed = [{id: "mixed", modules: ["clipboard", "launcher", "ssh", "layout"]}]
assert.equal(Cards.containing(mixed, "ssh"), mixed[0])
assert.equal(Cards.containing(mixed, "audio"), null)
assert.equal(Cards.preferences({cardStacks: mixed}).cardStacks, mixed)
// Stack IDs are user-owned names, distinct from retired module IDs.
assert.deepEqual(Cards.validate([{id: "screenshot", modules: ["clipboard"]}]),
    [{id: "screenshot", modules: ["clipboard"]}])
for (const stacks of [null, {}, [null], [[]], [{id: "", modules: ["audio"]}],
    [{id: "A", modules: ["audio"]}], [{id: "audio", modules: []}],
    [{id: "audio", modules: ["unknown"]}], [{id: "old", modules: ["screenshot", "clipboard"]}], [{id: "audio", modules: ["audio", "audio"]}],
    [{id: "a", modules: ["audio"]}, {id: "b", modules: ["audio"]}],
    [{id: "a", modules: ["audio"]}, {id: "a", modules: ["ssh"]}],
    [{id: "a", modules: ["audio"], enabled: true}]])
    assert.throws(() => Cards.validate(stacks))
for (const preferences of [null, [], {typo: true}, {windowSwitcher: 1}, {cardStacks: [{id: "a", modules: []}]}])
    assert.throws(() => Cards.preferences(preferences))
console.log("card stacks: defaults, full registry, mixed membership, disablement and invalid/stale configuration pass")

// Evaluate the real Settings binding; policy null follows existing ownership semantics.
const fs = require("node:fs"), vm = require("node:vm"), path = require("node:path")
const settings = fs.readFileSync(path.join(__dirname, "../config/Settings.qml"), "utf8")
const binding = settings.match(/readonly property var cardStacks: \{([\s\S]*?)^    \}/m)[1]
const host = fs.readFileSync(path.join(__dirname, "../modules/topbar/StatusPopout.qml"), "utf8")
assert.doesNotMatch(host, /Popouts\.Screenshot|function (?:capture|openCapturePage)\(/)
assert.equal(fs.existsSync(path.join(__dirname, "../modules/topbar/popouts/Screenshot.qml")), false)
const topbar = fs.readFileSync(path.join(__dirname, "../modules/Topbar.qml"), "utf8")
assert.doesNotMatch(topbar, /function screenshot\(/)
const manager = fs.readFileSync(path.join(__dirname, "../../manager/src/main.rs"), "utf8")
assert.deepEqual(JSON.parse("[" + manager.match(/const CARD_MODULES:[^=]+=\s*&?\s*\[([\s\S]*?)\];/)[1] + "]"), Cards.modules)
const saved = [{id: "saved", modules: ["ssh"]}]
for (const policy of [undefined, null, [], [{id: "policy", modules: ["clipboard"]}], "bad", [{id: "old", modules: ["screenshot"]}]]) {
    const result = vm.runInNewContext(`(() => {${binding}})()`, {
        widgetPolicy: {cardStacks: policy}, widgetSelections: {cardStacks: saved}, Cards,
        console: {warn() {}}
    })
    assert.equal(result, policy == null ? saved : policy === "bad" || policy?.[0]?.modules?.includes("screenshot") ? Cards.defaults : policy)
}
console.log("card stack policy: missing/null inherit, valid override, invalid non-null safe defaults pass")

for (const width of [50, 80, 99, 100]) assert.equal(Cards.preferences({barWidth: width}).barWidth, width)
for (const width of [49, 101, 80.5, true, "80", null, [], {}])
    assert.throws(() => Cards.preferences({barWidth: width}))
for (const style of Cards.barStyles) assert.equal(Cards.preferences({barStyle: style}).barStyle, style)
for (const style of ["Floating", "", true, 80, null]) assert.throws(() => Cards.preferences({barStyle: style}))

for (const access of Cards.oskAccessModes)
    assert.equal(Cards.preferences({oskAccess: access}).oskAccess, access)
for (const access of ["Launcher", "", false, 0, null, [], {}])
    assert.throws(() => Cards.preferences({oskAccess: access}))
const choice = settings.match(/    function barChoice\([^\n]*\) \{[\s\S]*?^    \}/m)[0]
for (const policy of [undefined, null, "none", "launcher", "topbar", "invalid", true]) {
    const context = vm.createContext({widgetPolicy: {oskAccess: policy}, widgetSelections: {oskAccess: "topbar"}})
    vm.runInContext(choice, context)
    assert.equal(context.barChoice("oskAccess", Cards.oskAccessModes, "none"),
        policy == null ? "topbar" : Cards.oskAccessModes.includes(policy) ? policy : "none")
}
console.log("OSK settings: exact enum, policy ownership and safe invalid-policy default pass")
