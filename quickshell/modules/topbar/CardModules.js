// First-party card IDs and persisted stack contract, shared by every shell entry.
var modules = ["launcher", "background", "layout", "media", "audio", "bluetooth",
    "clipboard", "network", "tailscale", "ssh", "notifications", "battery", "performance"]
var defaults = [
    {id: "launcher", modules: ["launcher", "background", "layout"]},
    {id: "media", modules: ["media"]},
    {id: "audio", modules: ["audio", "bluetooth"]},
    {id: "network", modules: ["network", "tailscale", "ssh"]},
    {id: "notifications", modules: ["notifications", "clipboard"]},
    {id: "battery", modules: ["battery", "performance"]}
]

function validate(stacks) {
    if (!Array.isArray(stacks)) throw new Error("Invalid card stacks")
    const ids = new Set(), members = new Set()
    for (const stack of stacks) {
        if (!stack || typeof stack !== "object" || Array.isArray(stack)
                || Object.keys(stack).sort().join(",") !== "id,modules"
                || typeof stack.id !== "string" || !/^[a-z][a-z0-9-]{0,31}$/.test(stack.id)
                || ids.has(stack.id) || !Array.isArray(stack.modules) || !stack.modules.length)
            throw new Error("Invalid card stack")
        ids.add(stack.id)
        for (const name of stack.modules) {
            if (!modules.includes(name) || members.has(name)) throw new Error("Invalid card module")
            members.add(name)
        }
    }
    return stacks
}

var barBehaviours = ["keyboard", "keyboard-mouse", "toggle", "always"]
var barLocations = ["above", "top", "bottom"]

function preferences(value) {
    if (!value || Array.isArray(value) || typeof value !== "object"
            || Object.keys(value).some(name => !["notificationToasts", "windowSwitcher", "cardStacks", "barBehaviour", "barLocation"].includes(name)
                || (name === "barBehaviour" ? !barBehaviours.includes(value[name])
                    : name === "barLocation" ? !barLocations.includes(value[name])
                    : name !== "cardStacks" && typeof value[name] !== "boolean")))
        throw new Error("Invalid widget selections")
    if (value.cardStacks !== undefined) validate(value.cardStacks)
    return value
}

function containing(stacks, name) {
    return stacks.find(stack => stack.modules.includes(name)) ?? null
}

if (typeof module !== "undefined") module.exports = {modules, defaults, validate, preferences, containing, barBehaviours, barLocations}
