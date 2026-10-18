// Run: node quickshell/tests/card-stacks.js
const assert = require("node:assert/strict")
const Cards = require("../modules/topbar/CardModules.js")

assert.equal(Cards.validate(Cards.defaults), Cards.defaults)
assert.deepEqual(Cards.defaults.flatMap(stack => stack.modules).sort(), [...Cards.modules].sort())
assert.deepEqual(Cards.preferences({notificationToasts: false}), {notificationToasts: false})
assert.deepEqual(Cards.validate([]), [])
const mixed = [{id: "mixed", modules: ["clipboard", "launcher", "ssh", "layout"]}]
assert.equal(Cards.containing(mixed, "ssh"), mixed[0])
assert.equal(Cards.containing(mixed, "audio"), null)
assert.equal(Cards.preferences({cardStacks: mixed}).cardStacks, mixed)
for (const stacks of [null, {}, [null], [[]], [{id: "", modules: ["audio"]}],
    [{id: "A", modules: ["audio"]}], [{id: "audio", modules: []}],
    [{id: "audio", modules: ["unknown"]}], [{id: "audio", modules: ["audio", "audio"]}],
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
const saved = [{id: "saved", modules: ["ssh"]}]
for (const policy of [undefined, null, [], [{id: "policy", modules: ["clipboard"]}], "bad"]) {
    const result = vm.runInNewContext(`(() => {${binding}})()`, {
        widgetPolicy: {cardStacks: policy}, widgetSelections: {cardStacks: saved}, Cards,
        console: {warn() {}}
    })
    assert.equal(result, policy == null ? saved : policy === "bad" ? Cards.defaults : policy)
}
console.log("card stack policy: missing/null inherit, valid override, invalid non-null safe defaults pass")
