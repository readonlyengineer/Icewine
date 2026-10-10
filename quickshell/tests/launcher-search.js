const assert = require("node:assert/strict")
const search = require("../modules/topbar/LauncherSearch.js")

const apps = [
    { name: "LibreWolf", genericName: "Web Browser", keywords: ["internet"], noDisplay: false },
    { name: "Kitty", genericName: "Terminal", keywords: ["shell"], noDisplay: false },
    { name: "Hidden", genericName: "Terminal", keywords: [], noDisplay: true },
    { name: "Foot Terminal", genericName: "Terminal", keywords: [], noDisplay: false }
]

assert.deepEqual(search.applications(apps, "lib").map(app => app.name), ["LibreWolf"])
assert.deepEqual(search.applications(apps, "term").map(app => app.name), ["Foot Terminal", "Kitty"])
assert.deepEqual(search.applications(apps, "").map(app => app.name), ["Foot Terminal", "Kitty", "LibreWolf"])

const ranked = [
    { name: "Nothing", keywords: ["term"] },
    { name: "Longterm" },
    { name: "Foot Terminal" },
    { name: "Terminal B" },
    { name: "term" },
    { name: "Terminal A" },
    { name: "Unrelated" },
    { name: "term", noDisplay: true }
]
const original = ranked.slice()
assert.deepEqual(search.applications(ranked, " TERM ").map(app => app.name),
    ["term", "Terminal A", "Terminal B", "Foot Terminal", "Longterm", "Nothing"])
assert.deepEqual(ranked, original)
assert.strictEqual(search.applications(ranked, "term")[0], ranked[4])
assert.deepEqual(search.applications(ranked, "missing"), [])
assert.deepEqual(search.applications([], "term"), [])

assert.deepEqual(search.launchOptions({
    command: ["demo", "--flag", "an argument"],
    runInTerminal: true,
    workingDirectory: "/work here"
}, "/home/demo"), {
    command: ["uwsm", "app", "--", "xdg-terminal-exec", "demo", "--flag", "an argument"],
    workingDirectory: "/work here"
})
assert.deepEqual(search.launchOptions({command: ["demo"]}, "/home/demo"), {
    command: ["uwsm", "app", "--", "demo"],
    workingDirectory: "/home/demo"
})

const fs = require("node:fs")
const os = require("node:os")
const path = require("node:path")
const { spawnSync } = require("node:child_process")
const home = fs.mkdtempSync(path.join(os.tmpdir(), "icewine-steam-test-"))
const dataHome = path.join(home, "data")
const shortcutFile = path.join(dataHome, "Steam/userdata/123/config/shortcuts.vdf")
const script = path.resolve(__dirname, "../tools/steam-shortcuts")
function readShortcuts(buffer) {
    if (buffer !== undefined) {
        fs.mkdirSync(path.dirname(shortcutFile), { recursive: true })
        fs.writeFileSync(shortcutFile, buffer)
    }
    return spawnSync(process.env.ICEWINE_TEST_PYTHON || "python3", [script], {
        encoding: "utf8", env: { ...process.env, HOME: home, XDG_DATA_HOME: dataHome }
    })
}
function parse(buffer) {
    const result = readShortcuts(buffer)
    assert.equal(result.status, 0, result.stderr)
    return JSON.parse(result.stdout)
}
assert.deepEqual(JSON.parse(readShortcuts().stdout), [])
const z = text => Buffer.from(text + "\0")
const stringField = (key, value) => Buffer.concat([Buffer.from([1]), z(key), z(value)])
const objectField = (key, ...fields) => Buffer.concat([
    Buffer.from([0]), z(key), ...fields, Buffer.from([8])
])
const shortcutData = Buffer.concat([
    objectField("shortcuts",
        objectField("0", stringField("AppName", "GeForce NOW — café"),
            stringField("Exe", '"/usr/bin/flatpak"'),
            stringField("LaunchOptions", "run --branch=stable com.nvidia.geforcenow"),
            Buffer.concat([Buffer.from([2]), z("appid"), Buffer.from([255, 255, 255, 255])]),
            objectField("tags", stringField("0", "games"))),
        objectField("1", stringField("exe", "prismlauncher")),
        objectField("2", stringField("exe", "librewolf"),
            stringField("LaunchOptions", "https://example.com")),
        objectField("3", stringField("exe", "sh"),
            stringField("LaunchOptions", '-c "echo $HOME"'))),
    Buffer.from([8])
])
const shortcuts = parse(shortcutData)
assert.deepEqual(shortcuts, [
    ["/usr/bin/flatpak", "run", "--branch=stable", "com.nvidia.geforcenow"],
    ["prismlauncher"], ["librewolf", "https://example.com"]
])
// The library accepts an omitted final outer terminator; records remain complete.
assert.deepEqual(parse(shortcutData.subarray(0, shortcutData.length - 1)), shortcuts)
for (const length of [0, 1, 8, Math.floor(shortcutData.length / 2), shortcutData.length - 2])
    assert.notEqual(readShortcuts(shortcutData.subarray(0, length)).status, 0)
for (const data of [
    Buffer.concat([shortcutData, Buffer.from([0])]),
    Buffer.from([99, 0, 8]), Buffer.alloc(4 * 1024 * 1024 + 1),
    Buffer.concat([objectField("shortcuts", stringField("0", "bad record")), Buffer.from([8])]),
    Buffer.concat([objectField("shortcuts", objectField("0", stringField("exe", "one"),
        stringField("Exe", "two"))), Buffer.from([8])]),
    Buffer.concat([objectField("shortcuts", objectField("0", stringField("exe", "x".repeat(65537)))), Buffer.from([8])])
]) assert.notEqual(readShortcuts(data).status, 0)
let nested = stringField("exe", "irrelevant")
for (let depth = 0; depth < 9; depth++) nested = objectField("nested", nested)
assert.notEqual(readShortcuts(Buffer.concat([objectField("shortcuts", nested), Buffer.from([8])])).status, 0)
// Standard quoting is parsed as argv, never passed to a shell. Unsafe forms stay unmatched.
assert.deepEqual(parse(Buffer.concat([objectField("shortcuts",
    objectField("0", stringField("exe", '"/a path/café app"'), stringField("LaunchOptions", "--name 'two words'")),
    objectField("1", stringField("exe", "touch"), stringField("LaunchOptions", "$HOME/never-created")),
    objectField("2", stringField("exe", 'bad"quote')),
    objectField("3", stringField("exe", "sh"), stringField("LaunchOptions", "-c 'echo unsafe; false'"))
), Buffer.from([8])])), [["/a path/café app", "--name", "two words"]])
// Both native roots are collected; Steam aliases may provide duplicates harmlessly.
const otherFile = path.join(home, ".steam/steam/userdata/456/config/shortcuts.vdf")
fs.mkdirSync(path.dirname(otherFile), { recursive: true })
fs.writeFileSync(otherFile, shortcutData)
assert.deepEqual(parse(shortcutData), shortcuts.concat(shortcuts))
fs.rmSync(home, { recursive: true })

const entries = [
    { name: "Game", command: ["steam", "steam://rungameid/123"] },
    { name: "Other game", command: ["/bin/steam", "-applaunch", "456"] },
    { name: "Steam", command: ["hyprctl", "eval", "open_gamescope()"] },
    { name: "GFN", command: ["flatpak", "run", "com.nvidia.geforcenow"] },
    { name: "Prism", command: ["prismlauncher"] },
    { name: "Browser", command: ["librewolf"] }
]
const names = (enabled, commands) => search.applications(entries, "", enabled, commands)
    .map(entry => entry.name)
assert.deepEqual(names(false, shortcuts),
    ["Browser", "Game", "GFN", "Other game", "Prism", "Steam"])
assert.deepEqual(names(true, shortcuts), ["Browser", "Steam"])
assert.deepEqual(names(true, []), ["Browser", "GFN", "Prism", "Steam"])
assert.equal(search.applications([{ command: ["flatpak", "run", "--unknown",
    "com.nvidia.geforcenow"] }], "", true, shortcuts).length, 1)
assert.equal(search.applications([{ command: [] }], "", true, shortcuts).length, 1)

console.log("launcher search and Steam shortcut checks passed")
