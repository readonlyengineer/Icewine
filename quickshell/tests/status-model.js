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

// Exercise the shared Bluetooth handlers used by pointer and keyboard callers.
const fs = require("node:fs")
const path = require("node:path")
const vm = require("node:vm")
const bluetooth = fs.readFileSync(path.join(__dirname, "../modules/topbar/popouts/Bluetooth.qml"), "utf8")
const bluetoothState = {Connecting: 1, Disconnecting: 2}
const bluetoothContext = vm.createContext({BluetoothDeviceState: bluetoothState, pairingDevice: null})
for (const name of ["busy", "activate", "forget"])
    vm.runInContext(bluetooth.match(new RegExp(`    function ${name}\\(device\\) \\{[\\s\\S]*?^    \\}`, "m"))[0], bluetoothContext)
for (const busy of [{pairing: true}, {state: 1}, {state: 2}]) {
    const device = {...busy, paired: true,
        connect() { throw new Error("Busy device connected") },
        disconnect() { throw new Error("Busy device disconnected") },
        pair() { throw new Error("Busy device paired") },
        forget() { throw new Error("Busy device forgotten") }}
    bluetoothContext.activate(device)
    bluetoothContext.forget(device)
}
const actions = []
const idleDevice = {paired: true,
    connect() { actions.push("connect") }, disconnect() { actions.push("disconnect") },
    pair() { actions.push("pair") }, forget() { actions.push("forget") }}
bluetoothContext.activate(idleDevice)
bluetoothContext.activate({...idleDevice, connected: true})
bluetoothContext.activate({...idleDevice, paired: false})
bluetoothContext.forget(idleDevice)
assert.deepEqual(actions, ["connect", "disconnect", "pair", "forget"])

// Native JSON and the actual QML request handlers: no daemon or routing queries.
const tailscaleModel = require("../modules/topbar/popouts/TailscaleModel.js")
const peer = (id, extra = {}) => ({ID: id, HostName: id, Online: true,
    TailscaleIPs: ["100.64.0.2"], ExitNodeOption: true, ...extra})
const running = {BackendState: "Running", Self: {ID: "local", Online: true}, Peer: {
    approved: peer("approved"), offline: peer("offline", {Online: false}),
    expired: peer("expired", {Expired: true}), ordinary: peer("ordinary", {ExitNodeOption: false}),
    hidden: peer("hidden", {ShareeNode: true}),
    hostile: peer("hostile", {TailscaleIPs: ["$(touch /tmp/unsafe)"]})}}
const decoded = tailscaleModel.decode(JSON.stringify(running))
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

const tailscale = fs.readFileSync(path.join(__dirname, "../modules/topbar/popouts/Tailscale.qml"), "utf8")
const context = vm.createContext({Model: tailscaleModel, active: true, data: unavailableExit,
    error: "", request: null, generation: 1, confirming: "", process: {running: false},
    deadline: {restart() {}, stop() {}}, exitPicker: {visible: false},
    Qt: {callLater(fn) { later.push(fn) }}})
const later = []
context.root = context
Object.defineProperty(context, "busy", {get: () => context.request !== null})
for (const name of ["refresh", "selectExit", "finish", "syncPicker"])
    vm.runInContext(tailscale.match(new RegExp(`    function ${name}\\([^)]*\\) \\{[\\s\\S]*?^    \\}`, "m"))[0], context)
function respond(code, text, errors = "") {
    context.process.running = false
    context.finish(code, 0, text, errors)
}
context.selectExit("approved")
assert.equal(context.request.id, "approved")
assert.deepEqual(Array.from(context.process.command), ["tailscale", "set", "--exit-node=100.64.0.2"])
context.selectExit("") // Busy request cannot be redirected by another choice.
assert.equal(context.request.id, "approved")
respond(1, "", "access denied")
assert.match(context.error, /Permission denied/)
assert.equal(context.data.selected, "offline")
context.selectExit("approved")
respond(1, "", "unexpected failure")
assert.match(context.error, /request failed/)
assert.equal(context.data.selected, "offline")
context.selectExit("approved")
context.data = {...decoded, exits: [...decoded.exits].reverse()}
respond(0, "")
context.selectExit("")
assert.equal(context.request, null) // Confirmation also serializes choices.
later.shift()()
respond(0, JSON.stringify({...running, ExitNodeStatus: {ID: "approved", Online: true}}))
assert.equal(context.data.selected, "approved")
assert.equal(context.confirming, "")
assert.equal(context.error, "")
context.refresh()
const preserved = context.data
context.generation++
respond(0, JSON.stringify({...running, BackendState: "NeedsLogin"}))
assert.equal(context.data, preserved) // A hidden/reopened page rejects the old read.
later.shift()()
respond(0, "bad JSON")
assert.equal(context.data.label, "Error")
assert.equal(context.data.connected, false)
context.refresh()
respond(127, "", "client absent")
assert.equal(context.data.label, "Unavailable")
context.refresh()
assert.equal(context.busy, true)
const deadlineBody = tailscale.match(/id: deadline[\s\S]*?onTriggered: \{([\s\S]*?)^        \}/m)[1]
vm.runInContext(deadlineBody, context)
assert.equal(context.busy, false)
assert.equal(context.data.label, "Unavailable")
respond(0, JSON.stringify(running)) // A response after the deadline cannot restore stale state.
assert.equal(context.data.label, "Unavailable")
context.data = decoded
context.selectExit("approved")
respond(0, "")
later.shift()()
respond(0, JSON.stringify({...running, Self: {ID: "other-profile", Online: true}}))
assert.match(context.error, /profile changed/)
context.refresh()
respond(0, JSON.stringify(running))
context.selectExit("approved")
respond(0, "")
later.shift()()
respond(0, JSON.stringify(running))
assert.match(context.error, /not confirmed/)
console.log("Tailscale eligibility, offline clear, captured requests and asynchronous failure checks passed")
