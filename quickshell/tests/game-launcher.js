// Run: node quickshell/tests/game-launcher.js
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const vm = require("node:vm")
const source = fs.readFileSync(path.join(__dirname, "../modules/GameLauncher.qml"), "utf8")
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
const splashModel = source.match(/Variants \{\s*model: ([\s\S]*?)\n\n        FloatingWindow/)[1]
const steamQueries = []
const steamCommands = []
const steamRoot = {
    handheld: true,
    steamEnabled: true,
    gamescopeEnabled: true,
    steamLaunching: false,
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
    Quickshell: {
        screens: [{name: "eDP-1"}, {name: "HDMI-A-1"}],
        execDetached(command) { steamCommands.push(Array.from(command)) }
    },
    steamLaunchTimeout: { restart() { this.running = true }, stop() { this.running = false } },
    steamAutostartRetry: { restarts: 0, restart() { this.restarts++ }, stop() { this.running = false } },
    console,
    JSON
})
for (const name of ["gamescopePlan", "finishSteamLaunch", "reuseSteamWindow", "startSteamProcess",
        "launchSteamGamescope", "probeSteamSession", "resolveSteamRequest", "handoffSteam", "autostartSteamGamescope"])
    vm.runInContext(qmlFunction(name), steamContext)
for (const name of ["gamescopePlan", "finishSteamLaunch", "reuseSteamWindow", "startSteamProcess",
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
assert.deepEqual(Array.from(vm.runInContext(splashModel, steamContext), screen => screen.name), ["eDP-1"])
assert.equal(steamRoot.steamSplashScreen, "eDP-1")
assert.equal(steamCommands.length, 0, "Gamescope waits for the splash's first frame")
assert.equal(JSON.parse(steamRoot.launchSteamGamescope()).pending, true)
steamRoot.startSteamProcess()
steamRoot.startSteamProcess()
assert.equal(steamCommands.length, 1, "The rendered splash starts exactly one session")
assert.deepEqual(steamCommands[0].slice(0, 12),
    ["uwsm", "app", "-t", "service",
        "-u", "icewine-steam-gamescope.service",
        "-p", "ExitType=main", "-p", "KillMode=control-group", "--", "gamescope"],
    "A stable UWSM service prevents duplicates and cleans up children when Gamescope exits")
assert.deepEqual(Array.from(vm.runInContext(splashModel, steamContext), screen => screen.name), ["eDP-1"])
assert.equal(JSON.parse(steamRoot.launchSteamGamescope()).pending, true,
    "The placeholder reserves the launch position until handoff or launch timeout")
assert.equal(steamCommands.length, 1)
steamCompositor.toplevels = [existing]
vm.runInContext(source.match(/onClosed: (.+)/)[1], steamContext)
assert.equal(steamCompositor.activated, undefined, "Hyprland owns conditional focus handoff")
assert.equal(steamRoot.steamLaunching, false, "Closing the placeholder clears launch state")
assert.equal(vm.runInContext(splashModel, steamContext).length, 0)
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

steamRoot.gamescopeEnabled = false
const ordinaryBefore = steamCommands.length
assert.equal(JSON.parse(steamRoot.launchSteamGamescope()).ok, true)
assert.deepEqual(steamCommands[ordinaryBefore], ["uwsm", "app", "--", "icewine-steam"])
assert.equal(vm.runInContext(splashModel, steamContext).length, 0, "Ordinary Steam has no Gamescope splash")
steamRoot.gamescopeEnabled = true

// An outside singleton may reveal its ordinary window only after Gamescope starts.
// Exercise the shared QML completion path with both Flatpak and native identities.
for (const identity of ["com.valvesoftware.Steam", "steam"]) {
    steamRoot.finishSteamLaunch()
    steamRoot.steamGamescopePid = 0
    steamCompositor.toplevels = []
    const before = steamCommands.length
    steamRoot.launchSteamGamescope()
    steamContext.steamSessionProbe.running = false
    steamRoot.resolveSteamRequest("LoadState=not-found\nMainPID=0")
    steamRoot.startSteamProcess()
    assert.equal(steamCommands.length, before + 1)
    const outer = {address: "0xouter", lastIpcObject: {class: identity}}
    steamCompositor.toplevels = [outer]
    steamRoot.handoffSteam()
    assert.equal(steamCompositor.activated, outer.address)
    assert.equal(vm.runInContext(splashModel, steamContext).length, 0, "Outside Steam must dismiss the splash")
    assert.equal(steamRoot.steamLaunching, false)
    assert.equal(steamRoot.steamRequestPending, false)
    assert.equal(steamContext.steamLaunchTimeout.running, false)
    assert.equal(steamRoot.pendingSteamCommand, null)
    assert.equal(steamCommands.length, before + 2, "Reuse only sends feedback; it never stops Steam")
    assert.deepEqual(steamCommands.at(-1), ["notify-send", "--app-name=Icewine", "--app-icon=steam",
        "Steam is already running outside Gamescope",
        "Quit Steam to launch it in Gamescope."])
    steamRoot.handoffSteam()
    assert.equal(steamCommands.length, before + 2, "Completed handoff does not repeat feedback")
    const reused = JSON.parse(steamRoot.launchSteamGamescope())
    assert.equal(reused.reused, true)
    assert.equal(reused.outsideGamescope, true, "Visible reuse must identify the actual session")
    assert.equal(steamCommands.length, before + 3, "Repeated launches only focus and explain reuse")
}
steamCompositor.toplevels = []
steamRoot.steamLaunching = true
steamRoot.pendingSteamCommand = ["must-not-run"]
steamCompositor.toplevels = [{address: "0xearly", wayland: {appId: "steam"}}]
steamRoot.handoffSteam()
steamRoot.startSteamProcess()
assert.equal(steamRoot.pendingSteamCommand, null, "Early outer mapping cancels unstarted launch work")
assert.equal(steamCommands.at(-1)[0], "notify-send")
steamCompositor.toplevels = [existing, {lastIpcObject: {class: "steam"}}]
steamRoot.steamGamescopePid = 481
steamRoot.steamRequestPending = true
const nestedBefore = steamCommands.length
steamRoot.handoffSteam()
assert.equal(steamCompositor.activated, existing.address, "Managed nested session takes precedence")
assert.equal(steamCommands.length, nestedBefore, "Nested reuse has no outside-session warning")

const nestedReuse = JSON.parse(steamRoot.launchSteamGamescope())
assert.equal(steamCompositor.activated, existing.address,
    "Shared entry must prefer the visible managed session over outside Steam")
assert.equal(nestedReuse.reused, true)
assert.equal(nestedReuse.outsideGamescope, false)
assert.equal(steamCommands.length, nestedBefore, "Shared nested reuse must not warn about outside Steam")
steamCompositor.toplevels = []
const beforeStaleProbe = steamQueries.length
assert.equal(JSON.parse(steamRoot.launchSteamGamescope()).pending, true)
assert.equal(steamQueries.length, beforeStaleProbe + 1,
    "A stale PID without its window must not suppress a fresh service probe")
assert.equal(steamRoot.steamGamescopePid, 0)
steamContext.steamSessionProbe.running = false
steamRoot.resolveSteamRequest("LoadState=not-found\nMainPID=0")
assert.equal(steamRoot.steamLaunching, true, "An exited cached session must allow a new launch")
steamRoot.finishSteamLaunch()

// A failed spawn and a late render callback must leave no splash or queued work.
steamRoot.steamSplashScreen = "eDP-1"
steamRoot.steamLaunching = true
steamRoot.pendingSteamCommand = ["fixture-failed-spawn"]
const execDetached = steamContext.Quickshell.execDetached
steamContext.Quickshell.execDetached = () => { throw new Error("fixture spawn failure") }
steamRoot.startSteamProcess()
steamContext.Quickshell.execDetached = execDetached
assert.equal(steamRoot.steamLaunching, false, "Failed spawn must finish the launch")
assert.equal(vm.runInContext(splashModel, steamContext).length, 0)
assert.equal(steamRoot.pendingSteamCommand, null)
assert.equal(steamContext.steamLaunchTimeout.running, false)
const afterFailure = steamCommands.length
steamRoot.startSteamProcess()
assert.equal(steamCommands.length, afterFailure, "Late render callbacks cannot revive a finished launch")

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
