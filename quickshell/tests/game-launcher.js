// Run: node quickshell/tests/game-launcher.js
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const vm = require("node:vm")
const source = fs.readFileSync(path.join(__dirname, "../modules/GameLauncher.qml"), "utf8")
const deckShell = fs.readFileSync(path.join(__dirname, "../deck/shell.qml"), "utf8")
const launcher = require("../modules/GameLauncher.js")

function qmlFunction(name) {
    const start = source.indexOf(`    function ${name}(`)
    assert.notEqual(start, -1, `Missing QML function ${name}`)
    const brace = source.indexOf("{", start)
    let depth = 0
    for (let end = brace; end < source.length; end++) {
        if (source[end] === "{") depth++
        if (source[end] === "}" && --depth === 0)
            return source.slice(start, end + 1).replace(/: string(?=\s*\{|\s*[,)])/g, "")
    }
    throw new Error(`Unterminated QML function ${name}`)
}

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
    "Steam launches directly after the host splash starts")

const existing = {address: "0x1", wayland: {appId: "gamescope"}}
assert.equal(launcher.gamescopeWindow([{lastIpcObject: {class: "steam"}}, existing]), existing,
    "An existing managed Gamescope session is reused")
for (const identity of ["Steam", "steam", "com.valvesoftware.Steam"])
    assert.equal(launcher.steamWindow([{lastIpcObject: {class: identity}}])?.lastIpcObject.class,
        identity, "An already-running outer Steam window is reused")
assert.equal(launcher.existingSteamWindow([{lastIpcObject: {class: "steam"}}, existing]), existing,
    "Managed Gamescope takes precedence over an outer Steam window")
assert.equal(launcher.steamLaunchAction([existing], false).action, "focus",
    "An existing Gamescope window is focused without opening a splash")
assert.equal(launcher.steamLaunchAction([], true).action, "wait",
    "A repeated request cannot start a duplicate session")
assert.equal(launcher.steamLaunchAction([], false).action, "launch",
    "A new session starts only when no window or launch is pending")

const steamCommands = []
const steamRoot = {
    handheld: true,
    steamLaunching: false,
    steamSplashVisible: false,
    steamSplashScreen: "",
    pendingSteamCommand: null,
    steamAutostartRetries: 0,
    focusedMonitor() { return null }
}
const steamCompositor = {
    toplevels: [],
    activateWindow(address) { this.activated = address }
}
const steamContext = vm.createContext({
    root: steamRoot,
    compositor: steamCompositor,
    Launcher: launcher,
    Quickshell: { execDetached(command) { steamCommands.push(Array.from(command)) } },
    steamLaunchTimeout: { restart() { this.running = true }, stop() { this.running = false } },
    steamAutostartRetry: { restarts: 0, restart() { this.restarts++ }, stop() { this.running = false } },
    console,
    JSON
})
for (const name of ["gamescopePlan", "finishSteamLaunch", "startSteamProcess",
        "launchSteamGamescope", "autostartSteamGamescope"])
    vm.runInContext(qmlFunction(name), steamContext)
for (const name of ["gamescopePlan", "finishSteamLaunch", "startSteamProcess",
        "launchSteamGamescope", "autostartSteamGamescope"])
    steamRoot[name] = steamContext[name].bind(steamRoot)

steamRoot.autostartSteamGamescope()
assert.equal(steamRoot.steamAutostartRetries, 1)
assert.equal(steamContext.steamAutostartRetry.restarts, 1,
    "Handheld autostart waits when monitor geometry is not ready")
steamRoot.focusedMonitor = () => ({
    name: "eDP-1", width: 1280, height: 800, refreshHz: 60, hdr: false, vrr: true
})
const plan = steamRoot.gamescopePlan(["icewine-steam"], true)
assert.deepEqual(Array.from(plan.arguments).slice(0, 7),
    ["gamescope", "--backend", "wayland", "--default-touch-mode", "1", "-W", "1280"],
    "Handheld launch flags remain in the shared monitor-aware plan")
steamRoot.autostartSteamGamescope()
assert.equal(steamRoot.steamAutostartRetries, 0)
assert.equal(steamRoot.steamLaunching, true)
assert.equal(steamRoot.steamSplashVisible, true)
assert.equal(steamRoot.steamSplashScreen, "eDP-1")
assert.equal(steamCommands.length, 0, "Gamescope waits for the splash's first frame")
assert.equal(JSON.parse(steamRoot.launchSteamGamescope()).pending, true)
steamRoot.startSteamProcess()
assert.equal(steamCommands.length, 1, "The rendered splash starts exactly one session")
assert.deepEqual(steamCommands[0].slice(0, 6),
    ["uwsm", "app", "-u", "icewine-steam-gamescope.scope", "--", "gamescope"],
    "A stable collected UWSM scope rejects a duplicate after the QML timeout")
assert.equal(steamRoot.steamSplashVisible, true)
assert.equal(JSON.parse(steamRoot.launchSteamGamescope()).pending, true,
    "The placeholder reserves the launch position until handoff or launch timeout")
assert.equal(steamCommands.length, 1)
steamCompositor.toplevels = [existing]
vm.runInContext(source.match(/onClosed: (.+)/)[1], steamContext)
assert.equal(steamCompositor.activated, undefined, "Hyprland owns conditional focus handoff")
assert.equal(steamRoot.steamLaunching, false, "Closing the placeholder clears launch state")
assert.equal(steamRoot.steamSplashVisible, false)
assert.equal(steamContext.steamLaunchTimeout.running, false)
assert.equal(JSON.parse(steamRoot.launchSteamGamescope()).reused, true)
assert.equal(steamCommands.length, 1, "Existing Gamescope is focused without another session")
steamRoot.steamLaunching = true
steamRoot.pendingSteamCommand = ["must-not-run"]
steamRoot.finishSteamLaunch()
assert.equal(steamRoot.steamLaunching, false)
assert.equal(steamRoot.pendingSteamCommand, null, "Timeout cleanup drops stale launch work")

assert.equal((deckShell.match(/gameLauncher\.autostartSteamGamescope\(\)/g) || []).length, 1,
    "Handheld autostart runs once from the Topbar first-frame hook")

assert.match(source, /FloatingWindow\s*\{/,
    "The placeholder is a managed window, below shell overlays")
assert.match(source, /title: "Icewine Steam launch"/,
    "The placeholder identity matches the compositor's placement policy")
assert.doesNotMatch(source, /PanelWindow|WlrLayershell|steamSplashTimeout|checkSteamLaunch/,
    "No overlay, early reservation expiry or second window-readiness watcher remains")
assert.match(source, /RenderReady[\s\S]*onReady: root\.startSteamProcess\(\)/,
    "The host splash renders before Gamescope starts")
assert.doesNotMatch(source, /GAMESCOPE_FOCUSED_APP_GFX|icewine-steam-session/,
    "Steam readiness no longer waits for an inner X11 property")
