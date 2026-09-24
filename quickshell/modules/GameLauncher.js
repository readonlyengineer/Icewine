function gamescopeWindow(toplevels) {
    return Array.from(toplevels || []).find(window => String(
        window.wayland?.appId ?? window.lastIpcObject?.class ?? "") === "gamescope")
}

function steamWindow(toplevels) {
    return Array.from(toplevels || []).find(window => {
        const identity = String(window.wayland?.appId
            ?? window.lastIpcObject?.class ?? "").toLowerCase()
        return identity === "steam" || identity === "com.valvesoftware.steam"
    })
}

function existingSteamWindow(toplevels) {
    return gamescopeWindow(toplevels) ?? steamWindow(toplevels)
}

if (typeof module !== "undefined")
    module.exports = { existingSteamWindow, gamescopeWindow, steamWindow }
