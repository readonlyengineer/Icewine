// Run: node quickshell/tests/game-launcher.js
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const vm = require("node:vm")
const source = fs.readFileSync(path.join(__dirname, "../modules/GameLauncher.qml"), "utf8")
const method = source.match(/        function launchCommand\(commandJson: string\): string \{[\s\S]*?^        \}/m)[0]
const launches = []
const context = vm.createContext({root: {launchGamescope(argv, steam) {
    launches.push({argv: Array.from(argv), steam})
    return JSON.stringify({ok: true})
}}})
vm.runInContext(method.replace("commandJson: string", "commandJson").replace("): string", ")"), context)
for (const value of ["not json", "null", "{}", "[]", '[""]', '["app", 1]', '["app", "\\u0000"]']) {
    assert.equal(JSON.parse(context.launchCommand(value)).ok, false)
}
assert.equal(launches.length, 0, "Malformed commands must not launch")
assert.equal(JSON.parse(context.launchCommand(JSON.stringify(["app", "a b", "$(touch /tmp/no)"]))).ok, true)
assert.deepEqual(launches, [{argv: ["app", "a b", "$(touch /tmp/no)"], steam: false}],
    "Commands pass as argument arrays, without shell expansion")
assert.match(source, /root\.gamescopePlan\(\["icewine-steam"\], true\)/,
    "Steam selection belongs to the downstream command wrapper")
