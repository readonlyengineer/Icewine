function windows(toplevels) {
    return Array.from(toplevels || []).map(window => {
        const ipc = window.lastIpcObject || {}
        return {
            title: String(ipc.title || window.wayland?.title || ipc.class || "Window"),
            subtitle: String(window.wayland?.appId || ipc.class || ""),
            stableId: String(ipc.stableId || "")
        }
    }).filter(window => window.stableId.length > 0)
}

if (typeof module !== "undefined")
    module.exports = { windows }
