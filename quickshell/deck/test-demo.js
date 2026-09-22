const assert = require("node:assert/strict")
const Menu = require("./DeckMenu.js")

function check(condition, message) {
    assert.ok(condition, message)
}

const initialPages = Menu.buildPages([])
check(initialPages.root.map(x => x.label).join(",") === "Steam,Web,Terminal,Fullscreen,Close,Keyboard",
    "Steam joins the root actions")
const directions = [[0,-1], [1,-1], [1,0], [1,1], [0,1], [-1,1], [-1,0], [-1,-1]]
const reachable = directions.map(([x,y]) => Menu.sector(x, y, initialPages.root.length, 0))
check(new Set(reachable).size === initialPages.root.length,
    "Every root action remains reachable with the eight digital directions")
check(initialPages.root[Menu.sector(0, -1, initialPages.root.length, 0)].label === "Steam", "Steam is up")
check(initialPages["web-0"].map(x => x.label).join(",") === "Home",
    "Home is the only preset web shortcut")
check(initialPages["web-0"][0].url === "", "Home landing page stays up")

const userPages = Menu.buildPages([
    { label: "Example", url: "https://example.com/" },
    { label: "YouTube", url: "https://www.youtube.com/" },
    { label: "Duplicate", url: "https://www.youtube.com/" },
    { label: "Local file", url: "file:///tmp/private" }
])
check(userPages["web-0"].some(x => x.label === "Example"), "Add user bookmarks")
check(userPages["web-0"].filter(x => x.url === "https://www.youtube.com/").length === 1,
    "Deduplicate browser bookmarks")
check(!userPages["web-0"].some(x => x.url === "file:///tmp/private"), "Reject non-web bookmarks")

const iconPages = Menu.buildPages([
    { label: "Cached", url: "https://example.com/", iconSource: "data:image/png;base64,YQ==" },
    { label: "SVG", url: "https://example.org/", iconSource: "data:image/svg+xml;base64,YQ==" },
    { label: "Remote", url: "https://example.net/", iconSource: "https://example.net/favicon.ico" }
])
check(iconPages["web-0"][1].iconSource === "data:image/png;base64,YQ==", "Keep cached PNG icons")
check(iconPages["web-0"][2].iconSource === "data:image/svg+xml;base64,YQ==", "Keep cached SVG icons")
check(iconPages["web-0"][3].iconSource === "", "Reject remote icon requests")
check(userPages["web-0"][1].iconSource === "", "Missing icons retain the glyph")

const manyBookmarks = Array.from({ length: 10 }, (_, index) => ({
    label: `Bookmark ${index}`,
    url: `https://example.com/${index}`
}))
const paged = Menu.buildPages(manyBookmarks)
check(paged["web-0"].length === 8 && paged["web-0"][7].page === "web-1",
    "Reserve the eighth direction for More")
check(Object.values(paged).every(entries => entries.length <= 8), "Never exceed digital directions")
check(Menu.inputRoute(false, false, false, false, true) === "desktop", "Desktop mapping")
check(Menu.inputRoute(true, false, false, false, true) === "game", "Focused game passthrough")
check(Menu.inputRoute(true, true, false, false, true) === "overlay", "Overlay wins over focus")
check(Menu.inputRoute(false, false, true, false, true) === "overlay", "Lock captures input")
check(Menu.inputRoute(false, false, false, true, true) === "overlay", "Hold capture until controller release")
check(Menu.inputRoute(true, false, false, false, false) === "overlay", "Stream loss mutes gamepad")
check(Menu.inputRoute(false, false, false, false, false) === "desktop", "Desktop survives stream loss")

const target = "/org/shadowblip/InputPlumber/devices/target/dbus0"
const line = `${target}: org.shadowblip.Input.DBusDevice.InputEvent ('ui_accept', 1.0)`
check(Menu.parseInput(line, target).pressed, "Parse button press")
check(Menu.parseInput(line, `${target}1`) === null, "Ignore other controller")
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
check(Menu.launchExpression(initialPages["web-0"][0], 1).includes("icewine-browser"),
    "Pin new browser window")
check(Menu.shellQuote("a'b") === "'a'\\''b'", "Shell-quote bookmark URLs")
check(Menu.launchExpression({ action: "bookmark", url: "javascript:alert(1)" }, 1) === null,
    "Reject active bookmark schemes")
check(Menu.launchExpression({ action: "close" }, 1) === null, "Reject non-launch actions")
for (const invalid of [NaN, -1, 0, 1.5])
    check(Menu.launchExpression({ action: "terminal" }, invalid) === null, "Reject invalid workspace")

console.log("Icewine demo: menu, routing, parser, release and launch checks passed.")
