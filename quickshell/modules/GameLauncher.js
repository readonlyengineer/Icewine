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

if (typeof module !== "undefined")
    module.exports = { existingSteamWindow, gamescopeWindow, steamLaunchAction, steamServicePid, steamWindow }
