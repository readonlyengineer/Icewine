// Run: node quickshell/tests/metrics.js
const assert = require("node:assert/strict")
const m = require("../modules/topbar/Metrics.js")

const line = (name, rx, tx) => `${name}: ${rx} 0 0 0 0 0 0 0 ${tx} 0 0 0 0 0 0 0`
const counters = m.network([line("lo", 900, 900), line("wlan0", 100, 50),
    line("eth0", 400, 30), line("tailscale0", 100, 50)].join("\n"), ["wlan0", "eth0"])
assert.deepEqual(counters, { wlan0: [100, 50], eth0: [400, 30] })
assert.deepEqual(m.networkRate(counters, { wlan0: [50, 20], eth0: [100, 10] }, 2), [175, 25])
assert.deepEqual(m.networkRate(counters, null, 1), [null, null])
assert.deepEqual(m.networkRate(counters, counters, 60), [null, null])
assert.deepEqual(m.networkRate(counters, { wlan0: [200, 100] }, 1), [0, 0])
assert.deepEqual(m.networkRate({}, counters, 1), [0, 0])
assert.deepEqual(m.network("wlan0: invalid", ["wlan0"]), {})

assert.deepEqual(m.cpu("cpu  10 20 30 40 5 6 7 8 100 100\ncpu0 1 2 3 4"), { total: 126, idle: 45 })
assert.equal(m.cpuUsage({ total: 200, idle: 120 }, { total: 100, idle: 40 }), 20)
assert.equal(m.cpuUsage({ total: 100, idle: 50 }, { total: 200, idle: 80 }), null)
assert.equal(m.cpu("broken"), null)
assert.equal(m.memoryUsage("MemTotal: 1000 kB\nMemAvailable: 250 kB\n"), 75)
assert.equal(m.memoryUsage("MemTotal: 0 kB\nMemAvailable: 0 kB"), null)
assert.equal(m.memoryUsage("MemTotal: 100 kB"), null)
assert.equal(m.sensor("45000\n", true), 45)
assert.equal(m.sensor("", false), null)
assert.equal(m.sensor("101", false), null)

let history = []
for (let time = 1000; time <= 180000; time += 1000) history = m.append(history, time, [time])
assert.equal(history.length, 120)
assert.equal(history[0].time, 61000)
assert.deepEqual(m.append(history, 400000, [null]), [{ time: 400000, values: [null] }])
assert.deepEqual(m.append(history, 1, [0]), [{ time: 1, values: [0] }])
assert.equal(m.format(null, "%"), "Unavailable")
assert.equal(m.format(2048, "B/s"), "2.0 KiB/s")
console.log("metrics checks passed")
