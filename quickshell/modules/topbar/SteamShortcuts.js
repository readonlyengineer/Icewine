function commands(buffer) {
    const bytes = new Uint8Array(buffer)
    let offset = 0

    // Small shortcut lists only. Move parsing off the UI thread if this grows.
    if (bytes.length > 4 * 1024 * 1024)
        throw new Error("Steam shortcut file exceeds 4 MiB")

    function take(count) {
        if (offset + count > bytes.length)
            throw new Error("Truncated Steam shortcut file")
        const start = offset
        offset += count
        return start
    }

    function string() {
        let encoded = ""
        while (true) {
            const byte = bytes[take(1)]
            if (byte === 0)
                return decodeURIComponent(encoded)
            encoded += "%" + byte.toString(16).padStart(2, "0")
            if (encoded.length > 3 * 65536)
                throw new Error("Oversized Steam shortcut string")
        }
    }

    function object(depth) {
        if (depth > 8)
            throw new Error("Steam shortcut nesting exceeds limit")
        const result = Object.create(null)
        while (true) {
            const type = bytes[take(1)]
            if (type === 8)
                return result
            const key = string().toLowerCase()
            if (Object.prototype.hasOwnProperty.call(result, key))
                throw new Error("Duplicate Steam shortcut field")
            if (type === 0) {
                result[key] = object(depth + 1)
            } else if (type === 1) {
                result[key] = string()
            } else if (type === 2) {
                take(4) // Integer metadata is irrelevant to matching.
                result[key] = null
            } else {
                throw new Error("Unsupported VDF type: " + type)
            }
        }
    }

    const root = object(0)
    if (offset !== bytes.length || !root.shortcuts
            || typeof root.shortcuts !== "object")
        throw new Error("Invalid Steam shortcut structure")

    const result = []
    for (const key of Object.keys(root.shortcuts)) {
        const shortcut = root.shortcuts[key]
        if (!shortcut || typeof shortcut !== "object")
            throw new Error("Invalid Steam shortcut record")
        if (typeof shortcut.exe !== "string")
            continue
        const options = shortcut.launchoptions ?? ""
        if (typeof options !== "string")
            continue
        const executable = words(shortcut.exe)
        const arguments_ = words(options)
        if (executable && executable.length && arguments_)
            result.push(executable.concat(arguments_))
    }
    return result
}

// Whole quoted arguments and ordinary words only. Extend for observed forms;
// leave shell escapes, expansions and compound commands unmatched.
function words(text) {
    if (/[\\$`;&|<>*?()[\]{}~#\r\n]/.test(text))
        return null
    const result = []
    let remaining = text.trim()
    while (remaining) {
        const match = /^(?:"([^"]*)"|'([^']*)'|([^\s"']+))(?=\s|$)/.exec(remaining)
        if (!match)
            return null
        result.push(match[1] ?? match[2] ?? match[3])
        remaining = remaining.slice(match[0].length).replace(/^\s+/, "")
    }
    return result
}

if (typeof module !== "undefined")
    module.exports = { commands }
