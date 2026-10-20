const assert = require("node:assert/strict")
const status = require("../modules/topbar/popouts/StatusModel.js")

assert.equal(status.adjustedVolume(0.98, 120), 1)
assert.equal(status.adjustedVolume(0.02, -120), 0)
assert.equal(status.adjustedVolume(0.4, 0), 0.4)

assert.equal(status.batteryIcon(0.1, false), "")
assert.equal(status.batteryIcon(0.8, false), "")
assert.equal(status.batteryIcon(0.1, true), "󰂄")
assert.equal(status.formatDuration(0), "")
assert.equal(status.formatDuration(90), "2m")
assert.equal(status.formatDuration(8130), "2h 16m")

const buttons = [
    { page: "audio", visible: true, x: 0, y: 0, width: 20, height: 20 },
    { page: "network", visible: true, x: 22, y: 0, width: 20, height: 20 },
    { page: "bluetooth", visible: false, x: 44, y: 0, width: 20, height: 20 }
]
assert.equal(status.pageAt(buttons, 5, 10), "audio")
assert.equal(status.pageAt(buttons, 21, 10), "")
assert.equal(status.pageAt(buttons, 50, 10), "")

const networks = [
    { name: "weak", connected: false, signalStrength: 0.2 },
    { name: "active", connected: true, signalStrength: 0.1 },
    { name: "strong", connected: false, signalStrength: 0.9 }
]
assert.deepEqual(status.wifiNetworks(networks).map(network => network.name),
    ["active", "strong", "weak"])

const devices = [
    { name: "Zulu", connected: false, paired: false },
    { name: "Alpha", connected: false, paired: true },
    { name: "Mouse", connected: true, paired: true }
]
assert.deepEqual(status.bluetoothDevices(devices).map(device => device.name),
    ["Mouse", "Alpha", "Zulu"])

console.log("status model checks passed")

// Input/eligibility parsing is independent of the native controls fixture.
const tailscaleModel = require("../modules/topbar/popouts/TailscaleModel.js")
const peer = (id, extra = {}) => ({ID: id, HostName: id, Online: true,
    TailscaleIPs: ["100.64.0.2"], ExitNodeOption: true, ...extra})
const running = {BackendState: "Running", Self: {ID: "local", Online: true}, Peer: {
    approved: peer("approved"), offline: peer("offline", {Online: false}),
    expired: peer("expired", {Expired: true}), ordinary: peer("ordinary", {ExitNodeOption: false}),
    hidden: peer("hidden", {ShareeNode: true}),
    hostile: peer("hostile", {TailscaleIPs: ["$(touch /tmp/unsafe)"]})}}
const decoded = tailscaleModel.decode(JSON.stringify(running))
const sameName = tailscaleModel.decode(JSON.stringify({...running,
    Self: {...running.Self, HostName: "Laptop"}, Peer: {
        local: peer("local", {HostName: "Laptop"}),
        remote: peer("remote", {HostName: "Laptop"})}}))
assert.deepEqual(sameName.peers.map(peer => peer.id), ["remote"], "Exclude local ID, retain equal remote names")
assert.deepEqual(sameName.exits.map(peer => peer.id), ["", "remote"])
assert.equal(decoded.selfName, "This device")
assert.equal(tailscaleModel.empty("Unavailable").selfName, "This device")
for (const [names, expected] of [
    [{HostName: "  laptop  ", DNSName: "other.tailnet.ts.net."}, "laptop"],
    [{HostName: " ", DNSName: " laptop.tailnet.ts.net. "}, "laptop.tailnet.ts.net"],
    [{HostName: 42, DNSName: "dns.tailnet.ts.net."}, "dns.tailnet.ts.net"],
    [{HostName: null, DNSName: []}, "This device"],
    [{HostName: "", DNSName: "."}, "This device"],
    [{HostName: "<b>laptop</b>"}, "<b>laptop</b>"]
]) {
    const named = tailscaleModel.decode(JSON.stringify({...running, Self: {...running.Self, ...names}}))
    assert.equal(named.selfName, expected)
    assert.equal(named.self, "local", "Display names must not replace stable node identity")
}
assert.equal(tailscaleModel.decode(JSON.stringify({BackendState: "Stopped",
    Self: {HostName: "stopped-laptop"}})).selfName, "stopped-laptop")
assert.deepEqual(decoded.exits.map(peer => peer.id), ["", "approved"])
assert.equal(decoded.peers.some(peer => peer.id === "hidden"), false)
assert.deepEqual(tailscaleModel.exitCommand(decoded, "approved"), ["tailscale", "set", "--exit-node=100.64.0.2"])
assert.deepEqual(tailscaleModel.exitCommand(decoded, ""), ["tailscale", "set", "--exit-node="])
assert.equal(tailscaleModel.exitCommand(decoded, "hostile"), null)
for (const BackendState of ["NeedsLogin", "Stopped"]) {
    const data = tailscaleModel.decode(JSON.stringify({BackendState}))
    assert.equal(data.connected, false)
    assert.equal(tailscaleModel.exitCommand(data, ""), null)
}
const offlineStatus = {...running, Self: {ID: "local", Online: false}}
const offlineSelectedStatus = {...offlineStatus, ExitNodeStatus: {ID: "offline", Online: false}}
const offlineSelected = tailscaleModel.decode(JSON.stringify(offlineSelectedStatus))
assert.equal(offlineSelected.connected, false)
assert.deepEqual(tailscaleModel.exitCommand(offlineSelected, ""), ["tailscale", "set", "--exit-node="])
assert.equal(tailscaleModel.exitCommand(offlineSelected, "approved"), null)
assert.equal(tailscaleModel.exitCommand(tailscaleModel.decode(JSON.stringify(offlineStatus)), ""), null)
assert.equal(tailscaleModel.exitCommand(tailscaleModel.empty("Unavailable"), ""), null)
assert.equal(tailscaleModel.decode(JSON.stringify({...running, Peer: null})).peers.length, 0)
const unavailableExit = tailscaleModel.decode(JSON.stringify({...running,
    ExitNodeStatus: {ID: "offline", Online: false}}))
assert.equal(unavailableExit.selected, "offline")
assert.match(unavailableExit.exits.find(peer => peer.id === "offline").name, /unavailable/)
assert.equal(tailscaleModel.exitCommand(unavailableExit, "offline"), null)
for (const output of ["broken", JSON.stringify({...running, Self: {ID: "", Online: false}}),
    JSON.stringify({...running, Peer: []}), JSON.stringify({...running, Peer: {bad: null}})])
    assert.throws(() => tailscaleModel.decode(output))

const located = (id, country, city, extra = {}) => peer(id, {
    DNSName: `${id}.mullvad.ts.net.`, Location: {Country: country, CountryCode: country,
        City: city, CityCode: city, Priority: 1}, ...extra})
const locations = {...running, Peer: {home: peer("home", {Location: {Country: "Australia", City: "Home"}}),
    au: located("au", "Australia", "Sydney"),
    auBest: located("au-best", "Australia", "Sydney", {Location: {Country: "Australia", CountryCode: "Australia", City: "Sydney", CityCode: "Sydney", Priority: 2}}),
    mel: located("mel", "Australia", "Melbourne"),
    de: located("de", "Germany", "Berlin"),
    missing: located("missing", "", "", {Location: null}),
    spoof: peer("spoof", {DNSName: "host.mullvad.ts.net.example."}),
    offline: located("offline", "Germany", "Berlin", {Online: false})}}
const grouped = tailscaleModel.decode(JSON.stringify(locations))
assert.deepEqual(grouped.peers.map(peer => peer.id), ["home", "spoof"])
const menu = tailscaleModel.exitMenu(grouped)
assert.deepEqual(menu.devices.map(peer => peer.id), ["home", "spoof"])
assert.deepEqual(menu.countries.map(country => country.name), ["Australia", "Germany", "Unknown country"])
assert.deepEqual(menu.countries[0].cities.map(city => [city.name, city.id]), [["Melbourne", "mel"], ["Sydney", "au-best"]])
const selectedCity = tailscaleModel.exitMenu(tailscaleModel.decode(JSON.stringify({...locations,
    ExitNodeStatus: {ID: "au", Online: true}}))).countries[0].cities[1]
assert.equal(selectedCity.id, "au", "Keep the active eligible server within a city")
assert.equal(selectedCity.selected, true)
const offlineCity = tailscaleModel.exitMenu(tailscaleModel.decode(JSON.stringify({...locations,
    ExitNodeStatus: {ID: "offline", Online: false}}))).countries[1].cities[0]
assert.equal(offlineCity.id, "de", "Offer an eligible alternative when the selected city server is offline")
assert.equal(offlineCity.selected, true)
assert.deepEqual(tailscaleModel.exitCommand(grouped, "au-best"), ["tailscale", "set", "--exit-node=100.64.0.2"])

// Native controls own success, confirmation, focus and hide/reopen scenarios.
// Retain deterministic failure/deadline checks without real ten-second waits.
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm")
const tailscale = fs.readFileSync(path.join(__dirname, "../modules/topbar/popouts/Tailscale.qml"), "utf8")
const killed = []
const context = vm.createContext({Model: tailscaleModel, active: true, data: unavailableExit,
    error: "", statusError: false, menuData: {devices: [], countries: []}, request: null, generation: 1, confirming: "", process: {running: false, signal(value) { killed.push(value) }},
    deadline: {restart() {}, stop() {}}, exitPicker: {visible: false},
    Qt: {callLater(fn) { later.push(fn) }}})
const later = []
context.root = context
Object.defineProperty(context, "busy", {get: () => context.request !== null})
for (const name of ["refresh", "selectExit", "toggleConnection", "finish", "syncPicker"])
    vm.runInContext(tailscale.match(new RegExp(`    function ${name}\\([^)]*\\) \\{[\\s\\S]*?^    \\}`, "m"))[0], context)
function respond(code, text, errors = "") {
    context.process.running = false
    context.finish(code, 0, text, errors)
}
const deadlineBody = tailscale.match(/id: deadline[\s\S]*?onTriggered: \{([\s\S]*?)^        \}/m)[1]
context.data = decoded
context.selectExit("approved")
respond(1, "", "access denied")
assert.match(context.error, /Permission denied/)
assert.equal(context.data, decoded, "A rejected mutation keeps confirmed state")
context.refresh()
vm.runInContext(deadlineBody, context)
assert.deepEqual(killed, [9])
const pending = context.request
context.refresh()
assert.equal(context.request, pending, "Timeout keeps the slot until child exit")
respond(0, JSON.stringify(running))
assert.equal(context.data.label, "Unavailable", "Late success cannot revive timed-out data")
context.refresh()
context.process.running = false
vm.runInContext(deadlineBody, context)
assert.equal(context.busy, false, "Failed-to-start has no exit signal")
assert.deepEqual(killed, [9], "No signal is sent without a child")
console.log("status model eligibility and request failure/deadline checks passed")
