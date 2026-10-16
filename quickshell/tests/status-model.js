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
const bluetoothContext = vm.createContext({BluetoothDeviceState: bluetoothState, pairingDevice: null,
    enabled: true, adapter: {enabled: true}, allDevices: []})
for (const name of ["busy", "available", "activate", "forget"])
    vm.runInContext(bluetooth.match(new RegExp(`    function ${name}\\(device\\) \\{[\\s\\S]*?^    \\}`, "m"))[0], bluetoothContext)
for (const busy of [{pairing: true}, {state: 1}, {state: 2}]) {
    const device = {...busy, paired: true,
        connect() { throw new Error("Busy device connected") },
        disconnect() { throw new Error("Busy device disconnected") },
        pair() { throw new Error("Busy device paired") },
        forget() { throw new Error("Busy device forgotten") }}
    bluetoothContext.allDevices = [device]
    bluetoothContext.activate(device)
    bluetoothContext.forget(device)
}
const actions = []
const idleDevice = {paired: true,
    connect() { actions.push("connect") }, disconnect() { actions.push("disconnect") },
    pair() { actions.push("pair") }, forget() { actions.push("forget") }}
const connectedDevice = {...idleDevice, connected: true}
const unpairedDevice = {...idleDevice, paired: false}
bluetoothContext.allDevices = [idleDevice, connectedDevice, unpairedDevice]
bluetoothContext.activate(idleDevice)
bluetoothContext.activate(connectedDevice)
bluetoothContext.activate(unpairedDevice)
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

const tailscale = fs.readFileSync(path.join(__dirname, "../modules/topbar/popouts/Tailscale.qml"), "utf8")
const killed = []
const context = vm.createContext({Model: tailscaleModel, active: true, data: unavailableExit,
    error: "", request: null, generation: 1, confirming: "", process: {running: false, signal(value) { killed.push(value) }},
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
assert.deepEqual(killed, [9])
assert.equal(context.busy, true, "Keep the slot until the killed process exits")
const timedOutRead = context.request
context.refresh()
assert.equal(context.request, timedOutRead)
respond(0, JSON.stringify(running)) // Even a successful exit after timeout is discarded.
assert.equal(context.busy, false)
assert.equal(context.data.label, "Unavailable")
respond(0, JSON.stringify(running)) // A response after the deadline cannot restore stale state.
assert.equal(context.data.label, "Unavailable")
context.data = decoded
context.selectExit("approved")
respond(0, "")
later.shift()()
respond(0, JSON.stringify({...running, Self: {ID: "other-profile", Online: true, HostName: "New profile"}}))
assert.match(context.error, /profile changed/)
assert.equal(context.data.selfName, "New profile")
context.refresh()
respond(0, JSON.stringify({...running, Self: {...running.Self, HostName: "Renamed device"}}))
assert.equal(context.data.selfName, "Renamed device")
context.selectExit("approved")
respond(0, "")
later.shift()()
respond(0, JSON.stringify(running))
assert.match(context.error, /not confirmed/)
console.log("Tailscale eligibility, offline clear, captured requests and asynchronous failure checks passed")

// Toggle policy uses backend state: an offline Running daemon can still be stopped.
const stopped = {BackendState: "Stopped", Self: {ID: "local", HostName: "Laptop"}}
for (const [value, command] of [[running, ["tailscale", "down"]],
    [offlineStatus, ["tailscale", "down"]], [stopped, ["tailscale", "up"]],
    [{BackendState: "Stopped"}, ["tailscale", "up"]]]) {
    const valueDecoded = tailscaleModel.decode(JSON.stringify(value))
    assert.deepEqual(tailscaleModel.connectionCommand(valueDecoded), command)
}
for (const state of ["NeedsLogin", "NeedsMachineAuth", "Starting", "NoState"])
    assert.equal(tailscaleModel.connectionCommand(tailscaleModel.decode(JSON.stringify({BackendState: state}))), null)
assert.equal(tailscaleModel.connectionCommand(tailscaleModel.empty("Unavailable")), null)

function resetConnection(value = running) {
    context.data = tailscaleModel.decode(JSON.stringify(value))
    context.active = true
    context.error = context.confirming = ""
    context.request = null
    context.process.running = false
    context.exitPicker.visible = false
    later.length = 0
}
function confirmConnection(value) {
    assert.ok(context.confirming)
    later.shift()()
    respond(0, JSON.stringify(value))
    assert.equal(context.confirming, "")
}
resetConnection()
context.toggleConnection()
const disconnect = context.request
assert.deepEqual(Array.from(context.process.command), ["tailscale", "down"])
assert.equal(context.data.connected, true, "Do not optimistically disconnect")
context.toggleConnection()
context.selectExit("approved")
context.refresh()
assert.equal(context.request, disconnect, "All callers serialize with a connection mutation")
respond(0, "")
context.toggleConnection()
assert.equal(context.request, null, "Confirmation serializes a second mutation")
confirmConnection(stopped)
assert.equal(context.error, "")
assert.equal(context.data.self, "local", "Stopped identity is retained when supplied")
context.toggleConnection()
assert.deepEqual(Array.from(context.process.command), ["tailscale", "up"])
respond(0, "")
confirmConnection({...running, ExitNodeStatus: {ID: "approved", Online: true}})
assert.equal(context.data.selected, "approved")
assert.equal(context.error, "")

for (const [code, errors, value, message] of [
    [1, "permission denied", running, /Permission denied/],
    [1, "unknown error", running, /request failed/],
    [0, "", running, /not confirmed/],
    [0, "", {...stopped, Self: {ID: "other", HostName: "Other"}}, /profile changed/],
    [1, "login required", {BackendState: "NeedsLogin"}, /Sign in/],
    [1, "approval required", {BackendState: "NeedsMachineAuth"}, /approval required/]
]) {
    resetConnection()
    context.toggleConnection()
    respond(code, "", errors)
    confirmConnection(value)
    assert.match(context.error, message)
}
resetConnection(stopped)
context.toggleConnection()
vm.runInContext(deadlineBody, context)
assert.equal(context.busy, true)
const timedOutMutation = context.request
context.toggleConnection()
assert.equal(context.request, timedOutMutation)
respond(0, "")
confirmConnection({...running, Self: {...running.Self, Online: false}})
assert.equal(context.data.connected, false)
assert.match(context.error, /timed out/)
context.toggleConnection() // Running/offline can be stopped, never accidentally reconnected.
assert.deepEqual(Array.from(context.process.command), ["tailscale", "down"])
respond(0, "")
confirmConnection(stopped)
assert.equal(context.error, "")

resetConnection()
context.toggleConnection()
context.active = false
context.generation++
respond(0, "")
assert.ok(context.confirming, "Hidden mutation waits for a fresh read on reopening")
assert.equal(later.length, 0)
context.active = true
context.generation++
context.refresh()
respond(0, JSON.stringify(stopped))
assert.equal(context.error, "")
assert.equal(context.confirming, "")
resetConnection()
context.exitPicker.visible = true
context.toggleConnection()
assert.equal(context.request, null)
context.exitPicker.visible = false
context.selectExit("approved")
const exitRequest = context.request
context.toggleConnection()
assert.equal(context.request, exitRequest)
respond(1, "", "failed")
resetConnection()
context.toggleConnection()
respond(127, "", "missing CLI")
later.shift()()
respond(127, "", "missing CLI")
assert.equal(context.data.label, "Unavailable")
assert.equal(context.confirming, "")
assert.equal(tailscaleModel.connectionCommand(context.data), null)
resetConnection()
context.refresh()
context.process.running = false // Failed-to-start has no child to deliver an exit signal.
vm.runInContext(deadlineBody, context)
assert.equal(context.busy, false)
assert.equal(context.data.label, "Unavailable")
assert.deepEqual(killed, [9, 9], "Missing CLI must not signal a nonexistent process")
console.log("Tailscale connection commands, confirmation, recovery, profile and lifecycle checks passed")
