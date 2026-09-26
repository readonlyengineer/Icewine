// InputPlumber 0.78 supplies eight digital directions rather than raw XY.
var rootEntries = [
    { label: "Steam", icon: "", action: "steam" },
    { label: "Launcher", icon: "󰀻", page: "launcher-0" },
    { label: "Terminal", icon: "", action: "terminal" },
    { label: "Fullscreen", icon: "󰊓", action: "fullscreen" },
    { label: "Close", icon: "󰅖", action: "close" },
    { label: "Keyboard", icon: "󰌌", action: "keyboard" }
]

function buildPages(applications) {
    applications = applications.filter(application =>
        !["steam", "com.valvesoftware.Steam", "kitty"].includes(String(application.id || "").replace(/\.desktop$/, "")))
    var pages = { root: rootEntries }
    var offset = 0
    var page = 0

    do {
        var remaining = applications.length - offset
        var count = remaining > 8 ? 7 : 8
        var entries = applications.slice(offset, offset + count).map(function(application) {
            return { label: application.name, icon: "󰀻", action: "application",
                application: application }
        })
        offset += count
        if (offset < applications.length)
            entries.push({ label: "More", icon: "󰇘", page: "launcher-" + (page + 1) })
        pages["launcher-" + page] = entries
        page++
    } while (offset < applications.length)

    return pages
}

function inputRoute(gamescopeFocused, shellEngaged, sessionLocked, draining, streamReady) {
    if (sessionLocked || shellEngaged || draining || (gamescopeFocused && !streamReady))
        return "overlay"
    return gamescopeFocused ? "game" : "desktop"
}

function parseInput(line, target) {
    if (!target || line.indexOf(target + ": ") !== 0)
        return null
    var match = line.slice(target.length + 2).match(
        /^org\.shadowblip\.Input\.DBusDevice\.InputEvent \('(ui_[a-z0-9_]+)', (0(?:\.0+)?|1(?:\.0+)?)\)$/)
    return match ? { action: match[1], pressed: Number(match[2]) === 1 } : null
}

function sector(x, y, count, previous) {
    if (count <= 0 || (x === 0 && y === 0))
        return previous
    var angle = (Math.atan2(y, x) + Math.PI / 2 + 2 * Math.PI) % (2 * Math.PI)
    return Math.floor(angle * count / (2 * Math.PI) + 0.5) % count
}

function controllerEvent(held, event, count, previous) {
    var wasPressed = held[event.action] === true
    if (event.pressed)
        held[event.action] = true
    else
        delete held[event.action]

    var selected = previous
    if (/^ui_(up|down|left|right)$/.test(event.action) && event.pressed) {
        selected = sector(Number(!!held.ui_right) - Number(!!held.ui_left),
                          Number(!!held.ui_down) - Number(!!held.ui_up), count, previous)
    }
    // Act on release, and ignore releases whose press happened before capture.
    return {
        selected: selected,
        command: !event.pressed && wasPressed && event.action === "ui_accept" ? "accept" : ""
    }
}

function neutral(held) {
    return Object.keys(held).length === 0
}

function shellQuote(value) {
    return "'" + String(value).replace(/'/g, "'\\''") + "'"
}

function launchExpression(entry, workspace, applicationOptions) {
    if (!entry || !Number.isInteger(workspace) || workspace <= 0)
        return null

    var command = ""
    if (entry.action === "steam") {
        command = "hyprctl eval " + shellQuote('require("modules.Deck").focus_or_start_gamescope()')
    } else if (entry.action === "terminal") {
        command = "uwsm app -- icewine-terminal"
    } else if (entry.action === "application" && applicationOptions
            && applicationOptions.command.length && applicationOptions.workingDirectory) {
        command = "cd -- " + shellQuote(applicationOptions.workingDirectory)
            + " && exec " + applicationOptions.command.map(shellQuote).join(" ")
    } else {
        return null
    }

    return "hl.dsp.exec_cmd(" + JSON.stringify(command)
        + ", { workspace = " + JSON.stringify(String(workspace)) + " })"
}

if (typeof module !== "undefined")
    module.exports = { rootEntries, buildPages, inputRoute, parseInput, sector, controllerEvent,
        neutral, shellQuote, launchExpression }
