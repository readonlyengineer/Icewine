function adjustedVolume(volume, delta) {
    return Math.max(0, Math.min(1, volume + (delta > 0 ? 0.05 : delta < 0 ? -0.05 : 0)))
}

function wifiIcon(strength) {
    return strength > 0.72 ? "󰤨" : strength > 0.48 ? "󰤥"
        : strength > 0.24 ? "󰤢" : "󰤟"
}

function batteryIcon(percentage, charging) {
    return charging ? "󰂄" : percentage < 0.2 ? ""
        : percentage < 0.4 ? "" : percentage < 0.6 ? ""
        : percentage < 0.8 ? "" : ""
}

function formatDuration(seconds) {
    if (!Number.isFinite(seconds) || seconds <= 0)
        return ""

    const totalMinutes = Math.max(1, Math.round(seconds / 60))
    const hours = Math.floor(totalMinutes / 60)
    const minutes = totalMinutes % 60
    return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`
}

function pageAt(items, x, y) {
    for (const item of items)
        if (item.visible && x >= item.x && x < item.x + item.width
                && y >= item.y && y < item.y + item.height)
            return item.page || ""
    return ""
}

function wifiNetworks(values, limit = 8) {
    return [...values].sort((a, b) =>
        (b.connected - a.connected) || (b.signalStrength - a.signalStrength)).slice(0, limit)
}

function bluetoothDevices(values, limit = 8) {
    return [...values].sort((a, b) =>
        (b.connected - a.connected) || (b.paired - a.paired)
            || String(a.name).localeCompare(String(b.name))).slice(0, limit)
}

if (typeof module !== "undefined")
    module.exports = {
        adjustedVolume,
        batteryIcon,
        bluetoothDevices,
        formatDuration,
        pageAt,
        wifiIcon,
        wifiNetworks
    }
