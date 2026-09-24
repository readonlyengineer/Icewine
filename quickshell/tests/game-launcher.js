// Run: node quickshell/tests/game-launcher.js
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const vm = require("node:vm")
const source = fs.readFileSync(path.join(__dirname, "../modules/GameLauncher.qml"), "utf8")
const launcher = require("../modules/GameLauncher.js")
const startup = require("../startup/StartupSplash.js")
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
assert.match(source, /root\.gamescopePlan\(\["icewine-steam-session"\], true\)/,
    "Handheld Steam selection belongs to the session wrapper")
assert.match(source, /root\.launchGamescope\(\["icewine-steam-session"\], true\)/,
    "Desktop Steam selection belongs to the session wrapper")

const existing = {address: "0x1", wayland: {appId: "gamescope"}}
assert.equal(launcher.gamescopeWindow([{lastIpcObject: {class: "steam"}}, existing]), existing,
    "An existing managed Gamescope session is reused")
for (const identity of ["Steam", "steam", "com.valvesoftware.Steam"])
    assert.equal(launcher.steamWindow([{lastIpcObject: {class: identity}}])?.lastIpcObject.class,
        identity, "An already-running outer Steam window is reused")
assert.equal(launcher.existingSteamWindow([{lastIpcObject: {class: "steam"}}, existing]), existing,
    "Managed Gamescope takes precedence over an outer Steam window")
assert.equal(startup.steamUiReady("GAMESCOPE_FOCUSED_APP_GFX(CARDINAL) = 769"), true,
    "The splash closes for Gamescope's committed graphical Steam UI")
for (const line of ["GAMESCOPE_FOCUSED_APP_GFX: not found.",
        "GAMESCOPE_FOCUSED_APP_GFX(CARDINAL) = 0", "GAMESCOPE_FOCUSED_APP(CARDINAL) = 769", "= 1769"])
    assert.equal(startup.steamUiReady(line), false,
        "Other focus state keeps startup feedback visible")
