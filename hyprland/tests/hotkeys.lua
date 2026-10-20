-- Run through tests/hotkeys.py with isolated XDG state; no compositor or actions.
local stub = setmetatable({}, {
    __index = function(self) return self end,
    __call = function(self, request) return request or self end,
})
package.loaded["icewine.modules.DefaultApps"] = dofile("hyprland/modules/DefaultApps.lua")
package.loaded["icewine.modules.WindowPolicy"] = stub
local bindings = {}
hl = {
    dsp = stub, config = function() end, gesture = function() end,
    unbind = function(key) bindings[key:gsub("%s", ""):upper()] = nil end,
    bind = function(key, action, options)
        bindings[key:gsub("%s", ""):upper()] = { action = action, options = options or {}, keys = key }
    end,
}
dofile("hyprland/modules/Binds.lua")
dofile("hyprland/deck/Deck.lua")
assert(bindings["SUPER+SHIFT+L"].options.description == "icewine:session-end"
    and not bindings["SUPER+SHIFT+L"].options.ignore_mods)
assert(bindings["SUPER+W"].options.transparent)
assert(bindings["SUPER+GRAVE"].options.transparent and bindings["SUPER+GRAVE"].options.submap_universal)
for _, key in ipairs({ "SUPER_L", "SUPER_R" }) do
    local options = bindings[key].options
    assert(options.transparent and options.ignore_mods and options.non_consuming and options.submap_universal)
end
assert(bindings.F14.options.transparent and bindings.F14.options.ignore_mods)
assert(bindings.F16.options.locked and bindings.F16.options.ignore_mods)
assert(bindings.F17.options.dont_inhibit and bindings.F17.options.submap_universal)
local actions = {
    launcher = "qs ipc call topbar launcher", terminal = "xdg-terminal-exec",
    filemanager = 'xdg-open "$HOME"', screenshot = "icewine screenshot", lock = "qs ipc call session lock",
}
local masks = { SUPER = 64, SHIFT = 1, CTRL = 4, ALT = 8 }
local rows, seen = {}, {}
for chord, binding in pairs(bindings) do
    local parts, mask = {}, 0
    for part in chord:gmatch("[^+]+") do parts[#parts + 1] = part end
    for index = 1, #parts - 1 do mask = mask + assert(masks[parts[index]]) end
    local options = binding.options
    local description = options.description or ""
    local id = description:match("^icewine:(%a+)$")
    if id and actions[id] then
        assert(actions[id] == binding.action and not seen[id])
        assert(binding.keys:find(" + ", 1, true), "changed shipped chord spelling")
        if parts[#parts] == "PRINT" then assert(binding.keys:match("Print$"), "broke case-sensitive Print unbind") end
        assert(not next(options, "description"), "managed press action gained flags")
        seen[id] = true
    end
    rows[#rows + 1] = string.format('{"key":%q,"modmask":%d,"keycode":0,"submap":"","description":%q,"release":%s,"mouse":%s,"repeat":%s,"non_consuming":%s,"catch_all":false}',
        binding.keys:match("([^+%s]+)$"), mask, description, tostring(options.release == true), tostring(options.mouse == true),
        tostring(options.repeating == true), tostring(options.non_consuming == true))
end
for id in pairs(actions) do assert(seen[id]) end
print("[" .. table.concat(rows, ",") .. "]")
