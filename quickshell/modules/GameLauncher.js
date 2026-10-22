function gamescopeWindow(toplevels, pid) {
    if (!Number.isSafeInteger(pid) || pid <= 0)
        return null
    return Array.from(toplevels || []).find(window => String(
        window.wayland?.appId ?? window.lastIpcObject?.class ?? "") === "gamescope"
        && Number(window.lastIpcObject?.pid) === pid)
}

function steamWindow(toplevels) {
    return Array.from(toplevels || []).find(window => {
        const identity = String(window.wayland?.appId
            ?? window.lastIpcObject?.class ?? "").toLowerCase()
        return identity === "steam" || identity === "com.valvesoftware.steam"
    })
}

function existingSteamWindow(toplevels, pid) {
    return gamescopeWindow(toplevels, pid) ?? steamWindow(toplevels)
}

function steamLaunchAction(toplevels, launching, pid = 0) {
    const window = existingSteamWindow(toplevels, pid)
    if (window)
        return { action: "focus", window }
    return { action: launching || pid > 0 ? "wait" : "launch", window: null }
}

function steamServicePid(output) {
    const fields = {}
    for (const line of String(output).trim().split("\n")) {
        const pair = line.split("=")
        if (pair.length === 2)
            fields[pair[0]] = pair[1]
    }
    if (!/^(loaded|not-found)$/.test(fields.LoadState || "") || !/^\d+$/.test(fields.MainPID || ""))
        return null
    const pid = Number(fields.MainPID)
    return Number.isSafeInteger(pid) ? pid : null
}

// GFN needs top-level CTA HDR metadata; some panels advertise it in DisplayID 2.0.
// Preserve the original extensions and timings, copying only actual metadata.
function gfnEdid(hex) {
    if (typeof hex !== "string" || !/^(?:[0-9a-f]{256}){1,256}$/i.test(hex))
        throw new Error("Invalid EDID length or encoding")
    var edid = hex.match(/../g).map(byte => parseInt(byte, 16))
    if (hex.slice(0, 16).toLowerCase() !== "00ffffffffffff00"
            || edid.length !== (edid[126] + 1) * 128)
        throw new Error("Invalid EDID header or extension count")
    var embedded = {}, standard = {}
    function blocks(data, metadata) {
        for (var pos = 0; pos < data.length;) {
            if (data.slice(pos).every(byte => byte === 0)) break
            var end = pos + 1 + (data[pos] & 31)
            if (!data[pos] || end > data.length) throw new Error("Malformed CTA block")
            var block = data.slice(pos, end)
            if (block[0] >> 5 === 7 && [5, 6].includes(block[1])) {
                if (block.length < 4 || block.length > (block[1] === 5 ? 4 : 7)
                        || metadata[block[1]])
                    throw new Error("Malformed or ambiguous HDR metadata")
                metadata[block[1]] = block
            }
            pos = end
        }
    }
    for (var offset = 0; offset < edid.length; offset += 128) {
        var extension = edid.slice(offset, offset + 128)
        if (extension.reduce((sum, byte) => sum + byte, 0) % 256)
            throw new Error("Invalid EDID checksum")
        if (!offset) continue
        if (extension[0] === 2) {
            if (extension[2] !== 0 && (extension[2] < 4 || extension[2] > 127))
                throw new Error("Invalid CTA length")
            if (extension[2]) blocks(extension.slice(4, extension[2]), standard)
        }
        if (extension[0] !== 0x70 || extension[1] !== 0x20) continue
        var end = 5 + extension[2]
        if (end > 126) throw new Error("Invalid DisplayID length")
        for (var pos = 5; pos < end;) {
            if (extension.slice(pos, end).every(byte => byte === 0)) break
            if (pos + 3 > end) throw new Error("Truncated DisplayID header")
            var stop = pos + 3 + extension[pos + 2]
            if (stop > end) throw new Error("Truncated DisplayID block")
            if (extension[pos] === 0x81) {
                if (extension[pos + 1] !== 0) throw new Error("Unsupported embedded CTA revision")
                blocks(extension.slice(pos + 3, stop), embedded)
            }
            pos = stop
        }
    }
    if (standard[6] && (standard[6][2] & 4)) return hex.toLowerCase()
    if (standard[6] || !embedded[5] || !embedded[6] || !(embedded[6][2] & 4)
            || edid[126] === 255)
        throw new Error("No unambiguous PQ HDR metadata")
    var payload = embedded[5].concat(embedded[6])
    var cta = [2, 3, 4 + payload.length, 0].concat(payload)
    while (cta.length < 128) cta.push(0)
    cta[127] = -cta.reduce((sum, byte) => sum + byte, 0) & 255
    edid[126]++
    edid[127] = -edid.slice(0, 127).reduce((sum, byte) => sum + byte, 0) & 255
    return edid.slice(0, 128).concat(cta, edid.slice(128))
        .map(byte => byte.toString(16).padStart(2, "0")).join("")
}

if (typeof module !== "undefined")
    module.exports = { gfnEdid, existingSteamWindow, gamescopeWindow, steamLaunchAction, steamServicePid, steamWindow }
