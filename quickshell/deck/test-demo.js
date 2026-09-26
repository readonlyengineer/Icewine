const assert = require("node:assert/strict")
const Menu = require("./DeckMenu.js")

function check(condition, message) {
    assert.ok(condition, message)
}

const rootEntries = Menu.rootEntries
check(rootEntries.map(x => x.label).join(",") === "Steam,Launcher,Terminal,Fullscreen,Close,Keyboard",
    "Root actions stay available")
const directions = [[0,-1], [1,-1], [1,0], [1,1], [0,1], [-1,1], [-1,0], [-1,-1]]
const reachable = directions.map(([x,y]) => Menu.sector(x, y, rootEntries.length, 0))
check(new Set(reachable).size === rootEntries.length,
    "Every root action remains reachable with the eight digital directions")
check(rootEntries[Menu.sector(0, -1, rootEntries.length, 0)].label === "Steam", "Steam is up")
const applications = count => Array.from({length: count}, (_, index) => ({name: "App " + index}))
const filtered = Menu.buildPages([
    { id: "steam" }, { id: "com.valvesoftware.Steam.desktop" }, { id: "kitty" },
    ...applications(8)
])
assert.deepEqual(filtered["launcher-0"].map(entry => entry.application), applications(8),
    "Dedicated shortcuts are excluded before pagination")
check(!filtered["launcher-1"], "Excluded shortcuts do not create an extra page")
check(rootEntries.some(entry => entry.action === "steam")
    && rootEntries.some(entry => entry.action === "terminal"), "Parent shortcuts remain")
for (const count of [0, 8]) {
    const pages = Menu.buildPages(applications(count))
    check(pages["launcher-0"].length === count, count + " applications need no More")
}
const nine = Menu.buildPages(applications(9))
check(nine["launcher-0"].length === 8 && nine["launcher-0"][7].page === "launcher-1",
    "Nine applications reserve the eighth direction for More")
check(nine["launcher-1"].length === 2, "Final page has no redundant More")
const many = Menu.buildPages(applications(23))
const reached = Object.keys(many).filter(key => key !== "root").flatMap(key =>
    many[key].filter(entry => entry.action === "application").map(entry => entry.application))
check(reached.length === 23 && new Set(reached).size === 23,
    "Multiple pages omit and duplicate no applications")
check(Object.values(many).every(entries => entries.length <= 8), "Pages fit the digital directions")
check(Menu.sector(1, 0, 0, 0) === 0, "Empty pages preserve selection")
check(Menu.inputRoute(false, false, false, false, true) === "desktop", "Desktop mapping")
check(Menu.inputRoute(true, false, false, false, true) === "game", "Focused game passthrough")
check(Menu.inputRoute(true, true, false, false, true) === "overlay", "Overlay wins over focus")
check(Menu.inputRoute(false, false, true, false, true) === "overlay", "Lock captures input")
check(Menu.inputRoute(false, false, false, true, true) === "overlay", "Hold capture until controller release")
check(Menu.inputRoute(true, false, false, false, false) === "overlay", "Stream loss mutes gamepad")
check(Menu.inputRoute(false, false, false, false, false) === "desktop", "Desktop survives stream loss")

const target = "/org/shadowblip/InputPlumber/devices/target/dbus0"
const line = target + ": org.shadowblip.Input.DBusDevice.InputEvent ('ui_accept', 1.0)"
check(Menu.parseInput(line, target).pressed, "Parse button press")
check(Menu.parseInput(line, target + "1") === null, "Ignore other controller")
check(Menu.parseInput(line.replace("1.0", "NaN"), target) === null, "Reject bad values")
check(Menu.parseInput(line.replace("InputEvent", "TouchEvent"), target) === null, "Ignore other signals")
check(Menu.parseInput(line, "") === null, "Require a discovered target")
check(Menu.sector(0, -1, 3, 2) === 0, "Aim up")
check(Menu.sector(1, 1, 3, 0) === 1, "Aim lower right")
check(Menu.sector(-1, 1, 3, 0) === 2, "Aim lower left")
check(Menu.sector(0, 0, 3, 2) === 2, "Neutral preserves selection")

const held = {}
const event = pressed => Menu.controllerEvent(held, { action: "ui_accept", pressed }, 3, 0).command
check(event(false) === "", "Ignore release from a game")
check(event(true) === "", "Do not activate on press")
check(event(true) === "", "Do not repeat while held")
check(event(false) === "accept", "Activate on release")
check(event(false) === "", "Do not activate twice")
check(Menu.controllerEvent(held, { action: "ui_back", pressed: true }, 3, 0).command === "",
    "Back has no radial action")
check(Menu.controllerEvent(held, { action: "ui_back", pressed: false }, 3, 0).command === "",
    "Back release has no radial action")
Menu.controllerEvent(held, { action: "ui_right", pressed: true }, 3, 0)
check(!Menu.neutral(held), "Keep interception until stick release")
Menu.controllerEvent(held, { action: "ui_right", pressed: false }, 3, 0)
check(Menu.neutral(held), "Release barrier clears")

check(Menu.launchExpression({ action: "terminal" }, 2).includes('workspace = "2"'),
    "Pin terminal to opening workspace")
check(Menu.launchExpression({ action: "terminal" }, 2).startsWith("hl.dsp.exec_cmd("),
    "Build a native Hyprland dispatcher")
check(Menu.launchExpression({ action: "terminal" }, 2).includes("uwsm app -- icewine-terminal"),
    "Launch Kitty from the terminal action")
check(Menu.launchExpression({ action: "steam" }, 2).includes("focus_or_start_gamescope()"),
    "Steam uses the same focus-or-launch action as Guide and the topbar")
const appExpression = Menu.launchExpression({ action: "application" }, 3, {
    command: ["uwsm", "app", "--", "icewine-terminal-exec", "demo", "an argument"],
    workingDirectory: "/tmp/a directory"
})
check(appExpression.includes("cd -- '/tmp/a directory'"), "Preserve application working directory")
check(appExpression.includes("'icewine-terminal-exec' 'demo' 'an argument'"),
    "Preserve terminal wrapper and arguments")
check(appExpression.includes('workspace = "3"'), "Pin applications to the opening workspace")
check(Menu.shellQuote("a'b") === "'a'\\''b'", "Shell-quote command values")
check(Menu.launchExpression({ action: "close" }, 1) === null, "Reject non-launch actions")
for (const invalid of [NaN, -1, 0, 1.5])
    check(Menu.launchExpression({ action: "terminal" }, invalid) === null, "Reject invalid workspace")

console.log("Icewine demo: menu, routing, parser, release and launch checks passed.")
