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
