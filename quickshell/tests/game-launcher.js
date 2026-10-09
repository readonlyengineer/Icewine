// Run: node quickshell/tests/game-launcher.js
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const vm = require("node:vm")
const source = fs.readFileSync(path.join(__dirname, "../modules/GameLauncher.qml"), "utf8")
const deckShell = fs.readFileSync(path.join(__dirname, "../Handheld.qml"), "utf8")
const launcher = require("../modules/GameLauncher.js")

function qmlFunction(name, sourceText = source) {
    const source = sourceText
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

const existing = {address: "0x1", wayland: {appId: "gamescope"}, lastIpcObject: {pid: 481}}
assert.equal(launcher.gamescopeWindow([{lastIpcObject: {class: "steam"}}, existing], 481), existing,
    "An existing managed Gamescope session is reused")
for (const identity of ["Steam", "steam", "com.valvesoftware.Steam"])
    assert.equal(launcher.steamWindow([{lastIpcObject: {class: identity}}])?.lastIpcObject.class,
        identity, "An already-running outer Steam window is reused")
assert.equal(launcher.existingSteamWindow([{lastIpcObject: {class: "steam"}}, existing], 481), existing,
    "Managed Gamescope takes precedence over an outer Steam window")
assert.equal(launcher.steamLaunchAction([existing], false, 481).action, "focus",
    "An existing Gamescope window is focused without opening a splash")
assert.equal(launcher.steamLaunchAction([], true).action, "wait",
    "A repeated request cannot start a duplicate session")
assert.equal(launcher.steamLaunchAction([], false).action, "launch",
    "A new session starts only when no window or launch is pending")

assert.equal(launcher.steamLaunchAction([existing], false, 999).action, "wait",
    "Another running managed PID is awaited, not confused with unrelated Gamescope")
assert.equal(launcher.steamLaunchAction([existing], false).action, "launch",
    "Unrelated Gamescope must not prevent Steam starting")
assert.equal(launcher.gamescopeWindow([existing], 0), null)
for (const output of ["", "MainPID=1", "LoadState=loaded\nMainPID=no", "LoadState=error\nMainPID=1"])
    assert.equal(launcher.steamServicePid(output), null)
assert.equal(launcher.steamServicePid("LoadState=not-found\nMainPID=0\n"), 0)
assert.equal(launcher.steamServicePid("MainPID=481\nLoadState=loaded\n"), 481)
const steamQueries = []
const steamCommands = []
const steamRoot = {
    handheld: true,
    steamEnabled: true,
    steamLaunching: false,
    steamSplashVisible: false,
    steamSplashScreen: "",
    pendingSteamCommand: null,
    steamAutostartRetries: 0,
    steamGamescopePid: 0,
    steamRequestPending: false,
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
    steamSessionProbe: {running: false, output: "", exec(command) {
        this.running = true
        steamQueries.push(Array.from(command))
    }},
    Quickshell: { execDetached(command) { steamCommands.push(Array.from(command)) } },
    steamLaunchTimeout: { restart() { this.running = true }, stop() { this.running = false } },
    steamAutostartRetry: { restarts: 0, restart() { this.restarts++ }, stop() { this.running = false } },
    console,
    JSON
})
for (const name of ["gamescopePlan", "finishSteamLaunch", "startSteamProcess",
        "launchSteamGamescope", "probeSteamSession", "resolveSteamRequest", "handoffSteam", "autostartSteamGamescope"])
    vm.runInContext(qmlFunction(name), steamContext)
for (const name of ["gamescopePlan", "finishSteamLaunch", "startSteamProcess",
        "launchSteamGamescope", "probeSteamSession", "resolveSteamRequest", "handoffSteam", "autostartSteamGamescope"])
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
assert.deepEqual(steamQueries[0], ["systemctl", "--user", "show", "icewine-steam-gamescope.service",
    "--property=MainPID", "--property=LoadState"])
assert.equal(steamRoot.steamLaunching, false, "Launch waits for native service identity")
steamContext.steamSessionProbe.running = false
steamRoot.resolveSteamRequest("LoadState=not-found\nMainPID=0")
assert.equal(steamRoot.steamAutostartRetries, 0)
assert.equal(steamRoot.steamLaunching, true)
assert.equal(steamRoot.steamSplashVisible, true)
assert.equal(steamRoot.steamSplashScreen, "eDP-1")
assert.equal(steamCommands.length, 0, "Gamescope waits for the splash's first frame")
assert.equal(JSON.parse(steamRoot.launchSteamGamescope()).pending, true)
steamRoot.startSteamProcess()
assert.equal(steamCommands.length, 1, "The rendered splash starts exactly one session")
assert.deepEqual(steamCommands[0].slice(0, 12),
    ["uwsm", "app", "-t", "service",
        "-u", "icewine-steam-gamescope.service",
        "-p", "ExitType=main", "-p", "KillMode=control-group", "--", "gamescope"],
    "A stable UWSM service prevents duplicates and cleans up children when Gamescope exits")
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
assert.equal(JSON.parse(steamRoot.launchSteamGamescope()).pending, true)
steamContext.steamSessionProbe.running = false
steamRoot.resolveSteamRequest("LoadState=loaded\nMainPID=481")
assert.equal(steamCompositor.activated, existing.address)
assert.equal(steamCommands.length, 1, "Matching Gamescope is focused without another session")
steamRoot.steamLaunching = true
steamRoot.steamGamescopePid = 0
steamRoot.handoffSteam()
assert.equal(steamCommands.length, 1, "Handoff waits for the managed service PID")
steamRoot.steamGamescopePid = 481
steamCompositor.toplevels = [{wayland: null, lastIpcObject: {}}]
steamRoot.handoffSteam()
assert.deepEqual(steamCommands[1], ["hyprctl", "eval",
    'require("icewine.modules.WindowPolicy").handoff_steam(481)'],
    "Hyprland checks readiness even before Quickshell receives window metadata")
steamRoot.steamRequestPending = true
steamRoot.resolveSteamRequest("unavailable")
assert.equal(steamRoot.steamRequestPending, false)
assert.equal(steamCommands.length, 2, "Unavailable service identity cannot start a speculative session")
steamCompositor.toplevels = []
assert.equal(JSON.parse(steamRoot.launchSteamGamescope()).pending, true)
steamContext.steamSessionProbe.running = false
steamRoot.resolveSteamRequest("LoadState=loaded\nMainPID=481")
assert.equal(steamRoot.steamRequestPending, true, "Existing service lost the pending focus request")
assert.equal(steamRoot.steamLaunching, false, "Existing service must not get another splash/session")
assert.equal(steamContext.steamLaunchTimeout.running, true, "Pending focus must have a bounded lifetime")
assert.equal(JSON.parse(steamRoot.launchSteamGamescope()).pending, true)
steamCompositor.toplevels = [{wayland: {appId: "gamescope"}, lastIpcObject: {pid: 999}}]
steamRoot.handoffSteam()
assert.equal(steamRoot.steamRequestPending, true, "Unrelated mapping consumed the pending request")
steamCompositor.toplevels.push(existing)
steamRoot.handoffSteam()
assert.equal(steamRoot.steamRequestPending, false)
assert.equal(steamCompositor.activated, existing.address, "Late matching window was not focused")
assert.equal(steamCommands.length, 2, "Late mapping started a duplicate session")
steamCompositor.toplevels = []
steamRoot.launchSteamGamescope()
steamContext.steamSessionProbe.running = false
steamRoot.resolveSteamRequest("LoadState=loaded\nMainPID=481")
steamRoot.resolveSteamRequest("LoadState=loaded\nMainPID=0")
assert.equal(steamRoot.steamRequestPending, false, "Exited service left a pending focus request")
assert.equal(steamCommands.length, 2, "Exited service caused an unrequested replacement launch")
steamRoot.launchSteamGamescope()
steamContext.steamSessionProbe.running = false
steamRoot.resolveSteamRequest("LoadState=loaded\nMainPID=481")
steamRoot.finishSteamLaunch()
assert.equal(steamRoot.steamRequestPending, false, "Expired focus request stayed pending")
assert.equal(steamContext.steamLaunchTimeout.running, false)
steamCompositor.activated = undefined
steamCompositor.toplevels = [existing]
steamRoot.handoffSteam()
assert.equal(steamCompositor.activated, undefined, "Expired request focused a later window")
steamRoot.steamLaunching = true
steamRoot.pendingSteamCommand = ["must-not-run"]
steamRoot.finishSteamLaunch()
assert.equal(steamRoot.steamLaunching, false)
assert.equal(steamRoot.pendingSteamCommand, null, "Timeout cleanup drops stale launch work")

const startupTimer = source.match(/Timer \{\s*\/\/ Ponytail: bounded startup polling[\s\S]*?\n    \}/)[0]
const timerRunning = startupTimer.match(/running: ([\s\S]*?)\n        onTriggered:/)[1]
vm.runInContext(qmlFunction("tick", startupTimer.replace("onTriggered:", "function tick()")), steamContext)
steamRoot.steamLaunching = true
steamRoot.steamGamescopePid = 481
steamCompositor.toplevels = []
assert.equal(vm.runInContext(timerRunning, steamContext), true,
    "Startup retries continue after MainPID appears and before a window maps")
const beforeRetry = steamCommands.length
steamContext.tick()
steamContext.tick()
assert.equal(steamCommands.length, beforeRetry + 2, "Startup retries the compositor handoff")
assert.deepEqual(steamCommands.at(-1), ["hyprctl", "eval",
    'require("icewine.modules.WindowPolicy").handoff_steam(481)'])
steamRoot.finishSteamLaunch()
assert.equal(vm.runInContext(timerRunning, steamContext), false,
    "Closing the splash or timing out stops startup retries")

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

steamRoot.steamEnabled = false
assert.equal(JSON.parse(steamContext.launchSteamGamescope()).ok, false,
    "Disabled Steam must reject launches before querying or focusing a session")
const shortcutsSource = fs.readFileSync(path.join(__dirname, "../modules/topbar/SteamShortcuts.qml"), "utf8")
const shortcutsContext = vm.createContext({root: {steamEnabled: false}, reader: {running: false}})
vm.runInContext(qmlFunction("refresh", shortcutsSource), shortcutsContext)
shortcutsContext.refresh()
assert.equal(shortcutsContext.reader.running, false, "Disabled Steam must not discover shortcuts")
shortcutsContext.root.steamEnabled = true
shortcutsContext.refresh()
assert.equal(shortcutsContext.reader.running, true)
