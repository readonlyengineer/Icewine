function request(workspace, identity, layout) {
    if (typeof identity !== "string" || !/^(?:[0-9a-f]{2})+$/.test(identity)
        || !Number.isSafeInteger(workspace) || workspace === 0
        || !["scrolling", "dwindle", "master", "monocle", "default"].includes(layout))
        throw new Error("Invalid workspace layout request")
    return ['hyprctl', 'eval', 'require("icewine.modules.Layouts").select('
        + workspace + ',' + JSON.stringify(identity) + ',' + JSON.stringify(layout) + ')']
}

function status(text, workspace) {
    const value = JSON.parse(text)
    const layouts = ["scrolling", "dwindle", "master", "monocle", "unknown"]
    if (typeof value.identity !== "string" || !/^(?:[0-9a-f]{2})+$/.test(value.identity)
        || value.workspace !== workspace || !layouts.includes(value.effective)
        || !layouts.includes(value.default)
        || !["", ...layouts.slice(0, 4)].includes(value.override))
        throw new Error("Invalid Hyprland layout state")
    return value
}

function label(layout) {
    return ({ scrolling: "Scrolling", dwindle: "Dwindle", master: "Master", monocle: "Monocle" })[layout]
        ?? "Other layout"
}

if (typeof module !== "undefined") module.exports = { request, status, label }
