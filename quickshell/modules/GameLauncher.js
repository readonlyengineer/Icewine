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

function steamLaunchAction(toplevels, launching) {
    const window = existingSteamWindow(toplevels)
    if (window)
        return { action: "focus", window }
    return { action: launching ? "wait" : "launch", window: null }
}

if (typeof module !== "undefined")
    module.exports = { existingSteamWindow, gamescopeWindow, steamLaunchAction, steamWindow }
