// InputPlumber 0.78 supplies eight digital directions rather than raw XY.
// Keep each page to eight sectors; overflow bookmarks advance through pages.
var rootEntries = [
    { label: "Steam", icon: "", action: "steam" },
    { label: "Web", icon: "󰖟", page: "web-0" },
    { label: "Terminal", icon: "", action: "terminal" },
    { label: "Fullscreen", icon: "󰊓", action: "fullscreen" },
    { label: "Close", icon: "󰅖", action: "close" },
    { label: "Keyboard", icon: "󰌌", action: "keyboard" }
]

var startingBookmarks = [
    { label: "Home", icon: "󰇧", action: "bookmark", url: "" }
]

function validBookmark(bookmark) {
    return bookmark && typeof bookmark.label === "string"
        && typeof bookmark.url === "string"
        && /^https?:\/\//.test(bookmark.url)
}

function buildPages(bookmarks) {
    var pages = { root: rootEntries }
    var seen = {}
    var entries = startingBookmarks.slice()

    for (var i = 0; i < entries.length; i++)
        seen[entries[i].url] = true

    for (var j = 0; j < bookmarks.length; j++) {
        var bookmark = bookmarks[j]
        if (!validBookmark(bookmark) || seen[bookmark.url])
            continue
        seen[bookmark.url] = true
        entries.push({
            label: bookmark.label.trim() || bookmark.url,
            icon: "󰈹",
            iconSource: typeof bookmark.iconSource === "string"
                && /^data:image\/(?:png|svg\+xml);base64,[A-Za-z0-9+/]+={0,2}$/.test(bookmark.iconSource)
                ? bookmark.iconSource : "",
            action: "bookmark",
            url: bookmark.url
        })
    }

    var offset = 0
    var page = 0
    while (offset < entries.length) {
        var remaining = entries.length - offset
        var count = remaining > 8 ? 7 : 8
        var pageEntries = entries.slice(offset, offset + count)
        offset += count
        if (offset < entries.length)
            pageEntries.push({ label: "More", icon: "󰇘", page: "web-" + (page + 1) })
        pages["web-" + page] = pageEntries
        page++
    }

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
    if (x === 0 && y === 0)
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

function launchExpression(entry, workspace) {
    if (!entry || !Number.isInteger(workspace) || workspace <= 0)
        return null

    var command = ""
    if (entry.action === "steam") {
        command = "hyprctl eval " + shellQuote('require("modules.Deck").focus_or_start_gamescope()')
    } else if (entry.action === "terminal") {
        command = "uwsm app -- icewine-terminal"
    } else if (entry.action === "bookmark"
            && (entry.url === "" || /^https?:\/\//.test(entry.url))) {
        command = entry.url ? "uwsm app -- icewine-browser " + shellQuote(entry.url)
                            : "uwsm app -- icewine-browser-home"
    } else {
        return null
    }

    return "hl.dsp.exec_cmd(" + JSON.stringify(command)
        + ", { workspace = " + JSON.stringify(String(workspace)) + " })"
}

if (typeof module !== "undefined")
    module.exports = { rootEntries, startingBookmarks, buildPages, inputRoute, parseInput,
        sector, controllerEvent, neutral, shellQuote, launchExpression }
