// Run: node quickshell/tests/metrics.js
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const vm = require("node:vm")
const m = require("../modules/topbar/Metrics.js")

const line = (name, rx, tx) => `${name}: ${rx} 0 0 0 0 0 0 0 ${tx} 0 0 0 0 0 0 0`
const counters = m.network([line("lo", 900, 900), line("wlan0", 100, 50),
    line("eth0", 400, 30), line("tailscale0", 100, 50)].join("\n"), ["wlan0", "eth0"])
assert.deepEqual({ ...counters }, { wlan0: [100, 50], eth0: [400, 30] })
assert.deepEqual(m.networkRate(counters, { wlan0: [50, 20], eth0: [100, 10] }, 2), [175, 25])
assert.deepEqual(m.networkRate(counters, null, 1), [null, null])
assert.deepEqual(m.networkRate(counters, counters, 60), [null, null])
assert.deepEqual(m.networkRate(counters, { wlan0: [200, 100], eth0: [400, 30] }, 1), [null, null])
assert.deepEqual(m.networkRate(counters, { wlan0: [100, 50] }, 1), [null, null])
assert.deepEqual(m.networkRate({}, counters, 1), [null, null])
assert.deepEqual(m.networkRate(counters, counters, 1), [0, 0])
assert.equal(Object.keys(m.network("wlan0: invalid", ["wlan0"])).length, 0)
for (const name of ["__proto__", "constructor", "toString"]) {
    const initial = m.network(line(name, 100, 50), [name])
    const next = m.network(line(name, 200, 90), [name])
    assert.deepEqual(Object.keys(initial), [name])
    assert.deepEqual(m.networkRate(initial, {}, 1), [null, null])
    assert.deepEqual(m.networkRate(next, initial, 2), [50, 20])
}

assert.deepEqual(m.cpu("cpu  10 20 30 40 5 6 7 8 100 100\ncpu0 1 2 3 4"), { total: 126, idle: 45 })
assert.equal(m.cpuUsage({ total: 200, idle: 120 }, { total: 100, idle: 40 }), 20)
assert.equal(m.cpuUsage({ total: 100, idle: 50 }, { total: 200, idle: 80 }), null)
assert.equal(m.cpu("broken"), null)
assert.equal(m.memory("MemTotal: 0 kB\nMemAvailable: 0 kB"), null)
assert.deepEqual(m.memory("MemTotal: 2097152 kB\nMemAvailable: 524288 kB\n"),
    { usage: 75, usedGiB: 1.5, totalGiB: 2 })
assert.equal(m.memory("MemTotal: 100 kB"), null)

const definitions = m.sensorDefinitions([
    "temperature\t/sys/class/hwmon/hwmon0/temp1_input\tcpu\tcpu\tacpitz\ttemp1",
    "temperature\t/sys/class/hwmon/hwmon1/temp2_input\tcpu\tcpu\tcoretemp\tCore 0",
    "temperature\t/sys/class/hwmon/hwmon1/temp1_input\tcpu\tcpu\tcoretemp\tPackage id 0",
    "usage\t/sys/class/drm/card0/device/gpu_busy_percent\tgpu\t0000:03:00.0\tdrm\tUsage",
    "temperature\t/sys/class/drm/card0/device/hwmon/hwmon2/temp2_input\tgpu\t0000:03:00.0\tamdgpu\tjunction",
    "temperature\t/sys/class/drm/card0/device/hwmon/hwmon2/temp1_input\tgpu\t0000:03:00.0\tamdgpu\tedge",
    "temperature\t/sys/class/drm/card1/device/hwmon/hwmon3/temp1_input\tgpu\t0000:04:00.0\tnouveau\tGPU",
    "temperature\t/sys/class/hwmon/hwmon4/temp1_input\tgpu\tbad\tamdgpu\tedge",
    "usage\t/sys/class/drm/card2/device/gpu_busy_percent\tgpu\t0000:05:00.0\tdrm\tUsage",
    "broken"
].join("\n"))
assert.deepEqual(definitions, [
    { kind: "temperature", path: "/sys/class/hwmon/hwmon1/temp1_input", role: "cpu",
        device: "cpu", title: "CPU", label: "Package" },
    { kind: "usage", path: "/sys/class/drm/card0/device/gpu_busy_percent", role: "gpu",
        device: "0000:03:00.0", title: "GPU 0000:03:00.0", label: "Usage" },
    { kind: "temperature", path: "/sys/class/drm/card0/device/hwmon/hwmon2/temp1_input",
        role: "gpu", device: "0000:03:00.0", title: "GPU 0000:03:00.0", label: "Edge" },
    { kind: "temperature", path: "/sys/class/drm/card1/device/hwmon/hwmon3/temp1_input",
        role: "gpu", device: "0000:04:00.0", title: "GPU 0000:04:00.0", label: "GPU" },
    { kind: "usage", path: "/sys/class/drm/card2/device/gpu_busy_percent", role: "gpu",
        device: "0000:05:00.0", title: "GPU 0000:05:00.0", label: "Usage" }
])
// Exercise the real delegate bindings and sampler method, without a second
// implementation of the definition-to-sampler contract.
const systemMetrics = fs.readFileSync(path.join(__dirname, "../modules/topbar/SystemMetrics.qml"), "utf8")
const delegate = systemMetrics.match(/delegate: MetricSampler \{[\s\S]*?^        \}/m)[0]
const samplerSource = fs.readFileSync(path.join(__dirname, "../modules/topbar/MetricSampler.qml"), "utf8")
const record = samplerSource.match(/    function record\(text\) \{[\s\S]*?^    \}/m)[0]
const samplers = definitions.map(modelData => {
    const sampler = vm.createContext({ modelData, Metrics: m, history: [], current: null,
        previous: null, previousTime: 0, busy: false })
    for (const property of ["kind", "path", "title", "role", "device", "label"]) {
        const binding = delegate.match(new RegExp(`^            (?:readonly property string )?${property}: (.+)$`, "m"))[1]
        sampler[property] = vm.runInContext(binding, sampler)
        assert.equal(sampler[property], modelData[property])
    }
    vm.runInContext(record, sampler)
    return sampler
})
for (const sampler of samplers) sampler.record(sampler.kind === "usage" ? "42\n" : "45000\n")
assert.equal(samplers[1].current, 42)
assert.equal(samplers[2].current, 45)
assert.equal(samplers[1].history[0].values[0], 42)
assert.equal(samplers[2].history[0].values[0], 45)
assert.deepEqual(m.gpuGroups(samplers), [
    { device: "0000:03:00.0", title: "GPU 0000:03:00.0",
        usage: samplers[1], temperature: samplers[2] },
    { device: "0000:04:00.0", title: "GPU 0000:04:00.0",
        usage: null, temperature: samplers[3] },
    { device: "0000:05:00.0", title: "GPU 0000:05:00.0",
        usage: samplers[4], temperature: null }
])
samplers[1].record("101")
const unavailable = m.gpuGroups(samplers)
assert.equal(unavailable[0].usage, samplers[1])
assert.equal(unavailable[0].usage.current, null)
assert.equal(unavailable[0].usage.history.at(-1).values[0], null)
assert.equal(unavailable[0].temperature.current, 45)
assert.equal(unavailable[1].usage, null)
assert.equal(unavailable[1].temperature.current, 45)
assert.equal(unavailable[2].usage.current, 42)
assert.equal(unavailable[2].temperature, null)
assert.equal(m.sensor("45000\n", true), 45)
assert.equal(m.sensor("-5000\n", true), -5)
assert.equal(m.sensor("-300000\n", true), null)
assert.equal(m.sensor("-1\n", false), null)
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
