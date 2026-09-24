function network(text, interfaces) {
    const counters = Object.create(null)
    for (const line of text.split("\n")) {
        const fields = line.trim().split(/[:\s]+/)
        if (!interfaces.includes(fields[0]) || fields.length < 17) continue
        const rx = Number(fields[1]), tx = Number(fields[9])
        if (Number.isFinite(rx) && Number.isFinite(tx) && rx >= 0 && tx >= 0)
            counters[fields[0]] = [rx, tx]
    }
    return counters
}

function networkRate(current, previous, seconds) {
    const names = Object.keys(current)
    if (!previous || seconds <= 0 || seconds > 3 || names.length === 0
            || names.some(name => !Object.prototype.hasOwnProperty.call(previous, name)))
        return [null, null]
    const rate = [0, 0]
    for (const name of names) {
        for (let i = 0; i < 2; ++i) {
            const delta = current[name][i] - previous[name][i]
            if (delta < 0) return [null, null]
            rate[i] += delta / seconds
        }
    }
    return rate
}

function cpu(text) {
    const line = text.split("\n").find(line => /^cpu\s/.test(line))
    if (!line) return null
    // Guest times are already included in user/nice.
    const fields = line.trim().split(/\s+/).slice(1, 9).map(Number)
    if (fields.length < 4 || fields.some(n => !Number.isFinite(n) || n < 0)) return null
    return { total: fields.reduce((a, b) => a + b, 0), idle: fields[3] + (fields[4] || 0) }
}

function cpuUsage(current, previous) {
    if (!current || !previous) return null
    const total = current.total - previous.total, idle = current.idle - previous.idle
    return total > 0 && idle >= 0 && idle <= total ? 100 * (total - idle) / total : null
}

function memoryUsage(text) {
    const total = /^MemTotal:\s+(\d+)\s+kB$/m.exec(text)
    const available = /^MemAvailable:\s+(\d+)\s+kB$/m.exec(text)
    if (!total || !available || +total[1] <= 0 || +available[1] > +total[1]) return null
    return 100 * (1 - Number(available[1]) / Number(total[1]))
}

function memory(text) {
    const total = /^MemTotal:\s+(\d+)\s+kB$/m.exec(text)
    const available = /^MemAvailable:\s+(\d+)\s+kB$/m.exec(text)
    if (!total || !available || +total[1] <= 0 || +available[1] > +total[1]) return null
    return {
        usage: 100 * (1 - Number(available[1]) / Number(total[1])),
        usedGiB: (Number(total[1]) - Number(available[1])) / 1048576,
        totalGiB: Number(total[1]) / 1048576
    }
}

function sensorDefinitions(text) {
    const candidates = text.trim().split("\n").map(line => line.split("\t"))
        .filter(fields => fields.length === 6
            && /^(usage|temperature)$/.test(fields[0])
            && ((fields[0] === "temperature" && fields[2] === "cpu"
                    && /^\/sys\/class\/hwmon\/hwmon\d+\/temp\d+_input$/.test(fields[1]))
                || (fields[0] === "usage" && fields[2] === "gpu"
                    && /^\/sys\/class\/drm\/card\d+\/device\/gpu_busy_percent$/.test(fields[1]))
                || (fields[0] === "temperature" && fields[2] === "gpu"
                    && /^\/sys\/class\/drm\/card\d+\/device\/hwmon\/hwmon\d+\/temp\d+_input$/.test(fields[1])))
            && fields.slice(3).every(field => field.length > 0))
        .map(fields => ({
            kind: fields[0], path: fields[1], role: fields[2], device: fields[3],
            chip: fields[4], sourceLabel: fields[5]
        }))

    const selected = []
    const cpu = candidates.filter(candidate => candidate.kind === "temperature"
        && candidate.role === "cpu").map(candidate => {
            const chip = candidate.chip.toLowerCase(), label = candidate.sourceLabel.toLowerCase()
            const priority = chip === "coretemp" && /^package id \d+$/.test(label) ? 0
                : /^(k10temp|zenpower)$/.test(chip) && label === "tctl" ? 0
                    : /^(k10temp|zenpower)$/.test(chip) && label === "tdie" ? 1 : -1
            return Object.assign({}, candidate, { priority,
                label: label.startsWith("package") ? "Package" : "Control" })
        }).filter(candidate => candidate.priority >= 0)
        .sort((a, b) => a.priority - b.priority || a.path.localeCompare(b.path))[0]
    if (cpu) selected.push(cpu)

    for (const device of [...new Set(candidates.filter(candidate => candidate.role === "gpu")
            .map(candidate => candidate.device))].sort()) {
        const deviceCandidates = candidates.filter(candidate => candidate.role === "gpu"
            && candidate.device === device)
        const usage = deviceCandidates.find(candidate => candidate.kind === "usage")
        if (usage) selected.push(Object.assign({}, usage, { label: "Usage" }))
        const temperature = deviceCandidates.filter(candidate => candidate.kind === "temperature")
            .map(candidate => {
                const label = candidate.sourceLabel.toLowerCase()
                return Object.assign({}, candidate, {
                    priority: label === "edge" ? 0 : label === "gpu" ? 1
                        : label === "core" ? 2 : -1,
                    label: label === "edge" ? "Edge" : label === "core" ? "Core" : "GPU" })
            }).filter(candidate => candidate.priority >= 0)
            .sort((a, b) => a.priority - b.priority || a.path.localeCompare(b.path))[0]
        if (temperature) selected.push(temperature)
    }
    return selected.map(candidate => ({
        kind: candidate.kind, path: candidate.path, role: candidate.role,
        device: candidate.device, title: candidate.role === "cpu" ? "CPU" : `GPU ${candidate.device}`,
        label: candidate.label
    }))
}

function gpuGroups(sensors) {
    return [...new Set(sensors.filter(sensor => sensor.role === "gpu")
            .map(sensor => sensor.device))].map(device => ({
        device,
        title: sensors.find(sensor => sensor.device === device).title,
        usage: sensors.find(sensor => sensor.device === device && sensor.kind === "gpu") ?? null,
        temperature: sensors.find(sensor => sensor.device === device
            && sensor.kind === "temperature") ?? null
    }))
}

function sensor(text, temperature) {
    if (!/^-?\d+\s*$/.test(text)) return null
    const value = Number(text) / (temperature ? 1000 : 1)
    return value >= (temperature ? -273.15 : 0) && value <= (temperature ? 200 : 100) ? value : null
}

function append(history, time, values) {
    return history.filter(point => point.time > time - 120000 && point.time < time)
        .concat([{ time, values }]).slice(-121)
}

function format(value, unit) {
    if (value === null || value === undefined || !Number.isFinite(value)) return "Unavailable"
    if (unit !== "B/s") return `${Math.round(value)}${unit}`
    const units = ["B/s", "KiB/s", "MiB/s", "GiB/s"]
    let index = 0
    while (value >= 1024 && index < units.length - 1) { value /= 1024; ++index }
    return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

if (typeof module !== "undefined")
    module.exports = { network, networkRate, cpu, cpuUsage, memoryUsage, memory,
        sensorDefinitions, gpuGroups, sensor, append, format }
