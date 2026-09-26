function searchableText(entry) {
    return `${entry.name || ""} ${entry.genericName || ""} ${(entry.keywords || []).join(" ")}`.toLowerCase()
}

function rank(entry, query) {
    const name = String(entry.name || "").toLowerCase()

    if (!query)
        return 0
    if (name === query)
        return 1
    if (name.startsWith(query))
        return 2
    if (name.split(/\s+/).some(word => word.startsWith(query)))
        return 3
    if (name.includes(query))
        return 4
    return searchableText(entry).includes(query) ? 5 : -1
}

function executableName(command) {
    return String(command[0] || "").split("/").pop()
}

function flatpakId(command) {
    if (executableName(command) !== "flatpak" || command[1] !== "run")
        return ""

    // Only recognise unambiguous options; extend for observed command forms.
    for (let i = 2; i < command.length; i++) {
        const argument = command[i]
        if (/^--[^=]+=/.test(argument)
                || ["--user", "--system", "--file-forwarding", "--no-a11y-bus",
                    "--no-documents-portal", "--die-with-parent"].includes(argument))
            continue
        return /^[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z_][A-Za-z0-9_-]*){2,}$/.test(argument)
            ? argument : ""
    }
    return ""
}

function steamManaged(entry, shortcuts) {
    const command = Array.from(entry.command || [])
    const steam = executableName(command) === "steam"
        || flatpakId(command) === "com.valvesoftware.Steam"
    if (steam && command.some(argument =>
            /^steam:\/\/(?:run|rungameid)\/[0-9]+(?:\/.*)?$/.test(argument)))
        return true
    if (steam && command.some((argument, index) =>
            argument === "-applaunch" && /^[0-9]+$/.test(command[index + 1] || "")))
        return true

    if (!command.length)
        return false
    const appId = flatpakId(command)
    return shortcuts.some(shortcut =>
        (appId !== "" && appId === flatpakId(shortcut))
        || (command.length === shortcut.length
            && command.every((argument, index) => argument === shortcut[index])))
}

function applications(entries, rawQuery, excludeSteam = false, shortcuts = []) {
    const query = String(rawQuery || "").trim().toLowerCase()

    return entries
        .filter(entry => !entry.noDisplay)
        .filter(entry => !excludeSteam || !steamManaged(entry, shortcuts))
        .map(entry => ({ entry, score: rank(entry, query) }))
        .filter(result => result.score >= 0)
        .sort((left, right) => left.score - right.score
            || String(left.entry.name).localeCompare(String(right.entry.name)))
        .map(result => result.entry)
}

function launchOptions(entry, home) {
    if (!entry)
        return null

    return {
        command: ["uwsm", "app", "--"]
            .concat(entry.runInTerminal ? ["icewine-terminal-exec"] : [])
            .concat(Array.from(entry.command || [])),
        workingDirectory: entry.workingDirectory || home
    }
}

if (typeof module !== "undefined")
    module.exports = { applications, launchOptions, rank }
