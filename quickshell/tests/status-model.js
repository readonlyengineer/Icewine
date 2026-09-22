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
