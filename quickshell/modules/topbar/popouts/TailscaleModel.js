function empty(label) {
    return { label, connected: false, self: "", peers: [], exits: [{ id: "", name: "None", address: "" }], selected: "" }
}

function decode(text) {
    const status = JSON.parse(text)
    const labels = { NeedsLogin: "Logged out", NeedsMachineAuth: "Awaiting device approval",
        Stopped: "Stopped", Starting: "Starting…", NoState: "Starting…", Running: "Connected" }
    if (!status || !Object.hasOwnProperty.call(labels, status.BackendState))
        throw new Error("Invalid Tailscale status")
    const result = empty(labels[status.BackendState])
    if (status.BackendState !== "Running") return result
    if (!status.Self || typeof status.Self.ID !== "string" || status.Self.ID.length === 0 || typeof status.Self.Online !== "boolean"
            || (status.Peer != null && (typeof status.Peer !== "object" || Array.isArray(status.Peer))))
        throw new Error("Incomplete Tailscale status")
    result.self = status.Self.ID
    result.connected = status.Self.Online
    if (!result.connected) result.label = "Disconnected"
    for (const peer of Object.values(status.Peer || {})) {
        if (!peer || typeof peer.ID !== "string" || !Array.isArray(peer.TailscaleIPs)
                || typeof peer.Online !== "boolean") throw new Error("Invalid device status")
        if (peer.ShareeNode || peer.ID === result.self) continue
        const address = peer.TailscaleIPs.find(ip => typeof ip === "string"
            && /^100\.(?:\d{1,3}\.){2}\d{1,3}$/.test(ip)
            && ip.split(".").every(part => Number(part) <= 255)
            && Number(ip.split(".")[1]) >= 64 && Number(ip.split(".")[1]) <= 127)
            || peer.TailscaleIPs.find(ip => typeof ip === "string" && /^fd7a:115c:a1e0:[0-9a-f:]+$/i.test(ip)) || ""
        const name = (typeof peer.HostName === "string" && peer.HostName)
            || (typeof peer.DNSName === "string" && peer.DNSName.replace(/\.$/, "")) || address || peer.ID
        result.peers.push({ id: peer.ID, name, address, online: peer.Online, expired: peer.Expired === true,
            eligible: peer.ExitNodeOption === true && peer.Online && !peer.Expired && address !== "" })
    }
    result.peers.sort((a, b) => Number(b.online) - Number(a.online) || a.name.localeCompare(b.name))
    result.exits.push(...result.peers.filter(peer => peer.eligible).map(peer => ({
        id: peer.id, name: `${peer.name} · ${peer.address}`, address: peer.address })))
    result.selected = status.ExitNodeStatus?.ID || ""
    if (typeof result.selected !== "string") throw new Error("Invalid exit-node status")
    if (result.selected && !result.exits.some(peer => peer.id === result.selected)) {
        const peer = result.peers.find(peer => peer.id === result.selected)
        result.exits.push({ id: result.selected, name: `${peer?.name || result.selected} · unavailable`, address: "" })
    }
    if (status.ExitNodeStatus && status.ExitNodeStatus.Online !== true)
        result.label += " · exit node offline"
    if (Array.isArray(status.Health) && status.Health.length) result.label += " · needs attention"
    return result
}

function exitCommand(data, id) {
    if (!data.self || (!data.connected && (id !== "" || !data.selected))) return null
    const peer = data.exits.find(peer => peer.id === id)
    if (!peer || (id !== "" && !peer.address)) return null
    return ["tailscale", "set", `--exit-node=${peer.address}`]
}

if (typeof module !== "undefined") module.exports = { empty, decode, exitCommand }
