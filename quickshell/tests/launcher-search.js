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
    command: ["uwsm", "app", "--", "icewine-terminal-exec", "demo", "--flag", "an argument"],
    workingDirectory: "/work here"
})
assert.deepEqual(search.launchOptions({command: ["demo"]}, "/home/demo"), {
    command: ["uwsm", "app", "--", "demo"],
    workingDirectory: "/home/demo"
})

const steamReader = require("../modules/topbar/SteamShortcuts.js")
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
const parse = buffer => steamReader.commands(Uint8Array.from(buffer).buffer)
const shortcuts = parse(shortcutData)
assert.deepEqual(shortcuts, [
    ["/usr/bin/flatpak", "run", "--branch=stable", "com.nvidia.geforcenow"],
    ["prismlauncher"], ["librewolf", "https://example.com"]
])
for (let length = 0; length < shortcutData.length; length++)
    assert.throws(() => parse(shortcutData.subarray(0, length)))
assert.throws(() => parse(Buffer.concat([shortcutData, Buffer.from([0])])))
assert.throws(() => parse(Buffer.from([99, 0, 8])))
assert.throws(() => parse(Buffer.alloc(4 * 1024 * 1024 + 1)))
assert.throws(() => parse(Buffer.concat([
    objectField("shortcuts", stringField("0", "bad record")), Buffer.from([8])
])))

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
