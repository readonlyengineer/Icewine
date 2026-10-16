function empty(label) {
    return { label, state: "", connected: false, self: "", selfName: "This device", peers: [], exits: [{ id: "", name: "None", address: "" }], selected: "" }
}

function decode(text) {
    const status = JSON.parse(text)
    const labels = { NeedsLogin: "Logged out", NeedsMachineAuth: "Awaiting device approval",
        Stopped: "Stopped", Starting: "Starting…", NoState: "Starting…", Running: "Connected" }
    if (!status || !Object.hasOwnProperty.call(labels, status.BackendState))
        throw new Error("Invalid Tailscale status")
    const result = empty(labels[status.BackendState])
    result.state = status.BackendState
    result.self = typeof status.Self?.ID === "string" ? status.Self.ID : ""
    result.selfName = (typeof status.Self?.HostName === "string" && status.Self.HostName.trim())
        || (typeof status.Self?.DNSName === "string" && status.Self.DNSName.trim().replace(/\.$/, ""))
        || result.selfName
    if (status.BackendState !== "Running") return result
    if (!status.Self || typeof status.Self.ID !== "string" || status.Self.ID.length === 0 || typeof status.Self.Online !== "boolean"
            || (status.Peer != null && (typeof status.Peer !== "object" || Array.isArray(status.Peer))))
        throw new Error("Incomplete Tailscale status")
    result.self = status.Self.ID
    result.connected = status.Self.Online
    if (!result.connected) result.label = "Disconnected"
    const devices = []
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
        // Use Tailscale's Mullvad DNS suffix, not geographic metadata on user devices.
        const mullvad = typeof peer.DNSName === "string"
            && peer.DNSName.toLowerCase().replace(/\.$/, "").endsWith(".mullvad.ts.net")
        const location = peer.Location || {}
        const country = typeof location.Country === "string" && location.Country.trim() || "Unknown country"
        const city = typeof location.City === "string" && location.City.trim() || "Unknown city"
        devices.push({ id: peer.ID, name, address, online: peer.Online, expired: peer.Expired === true,
            eligible: peer.ExitNodeOption === true && peer.Online && !peer.Expired && address !== "",
            mullvad, country, city,
            countryCode: typeof location.CountryCode === "string" && location.CountryCode || country,
            cityCode: typeof location.CityCode === "string" && location.CityCode || city,
            priority: Number.isFinite(location.Priority) ? location.Priority : 0 })
    }
    devices.sort((a, b) => Number(b.online) - Number(a.online) || a.name.localeCompare(b.name))
    result.peers = devices.filter(peer => !peer.mullvad)
    result.exits.push(...devices.filter(peer => peer.eligible).map(peer => Object.assign({}, peer, {
        name: peer.mullvad ? `${peer.country} · ${peer.city}` : peer.name })))
    result.selected = status.ExitNodeStatus?.ID || ""
    if (typeof result.selected !== "string") throw new Error("Invalid exit-node status")
    if (result.selected && !result.exits.some(peer => peer.id === result.selected)) {
        const peer = devices.find(peer => peer.id === result.selected)
        const name = peer?.mullvad ? `${peer.country} · ${peer.city}` : peer?.name || result.selected
        result.exits.push(Object.assign({}, peer, { id: result.selected, name: `${name} · unavailable`, address: "" }))
    }
    if (status.ExitNodeStatus && status.ExitNodeStatus.Online !== true)
        result.label += " · exit node offline"
    if (Array.isArray(status.Health) && status.Health.length) result.label += " · needs attention"
    return result
}

function connectionCommand(data) {
    if (data.state === "Stopped") return ["tailscale", "up"]
    if (data.state === "Running" && data.self) return ["tailscale", "down"]
    return null
}

function exitCommand(data, id) {
    if (!data.self || (!data.connected && (id !== "" || !data.selected))) return null
    const peer = data.exits.find(peer => peer.id === id)
    if (!peer || (id !== "" && !peer.address)) return null
    return ["tailscale", "set", `--exit-node=${peer.address}`]
}

function exitMenu(data) {
    const devices = data.exits.filter(peer => peer.id && !peer.mullvad)
    const countries = new Map()
    const selected = data.exits.find(peer => peer.id === data.selected)
    for (const peer of data.exits.filter(peer => peer.mullvad)) {
        if (!countries.has(peer.countryCode))
            countries.set(peer.countryCode, { name: peer.country, cities: new Map() })
        const cities = countries.get(peer.countryCode).cities
        const current = cities.get(peer.cityCode)
        // Prefer an eligible current server, otherwise Tailscale's advertised priority.
        if (!current || (peer.address && !current.address)
                || (Boolean(peer.address) === Boolean(current.address)
                    && (peer.id === data.selected || (current.id !== data.selected && peer.priority > current.priority))))
            cities.set(peer.cityCode, peer)
    }
    return { devices, countries: Array.from(countries.values(), country => ({
        name: country.name,
        cities: Array.from(country.cities.values(), peer => ({
            id: peer.id, name: peer.city, selected: selected?.mullvad === true
                && selected.countryCode === peer.countryCode && selected.cityCode === peer.cityCode
        })).sort((a, b) => a.name.localeCompare(b.name))
    })).sort((a, b) => a.name.localeCompare(b.name)) }
}

if (typeof module !== "undefined") module.exports = { empty, decode, connectionCommand, exitCommand, exitMenu }
