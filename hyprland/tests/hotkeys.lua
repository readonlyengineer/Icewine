-- Run through tests/hotkeys.py with isolated XDG state; no compositor or actions.
local stub = setmetatable({}, {
    __index = function(self) return self end,
    __call = function(self, request) return request or self end,
})
local apps = dofile("hyprland/modules/DefaultApps.lua")
if os.getenv("HOTKEY_TEST_NO_BROWSER") == "true" then apps.browser = "" end
package.loaded["icewine.modules.DefaultApps"] = apps
package.loaded["icewine.modules.WindowPolicy"] = stub
local definitions = dofile("hyprland/modules/Bindings.lua")
package.loaded["icewine.modules.Bindings"] = definitions
local bindings, dispatched = {}, nil
hl = {
    dsp = stub, config = function() end, gesture = function() end,
    get_active_workspace = function() return { tiled_layout = "dwindle" } end,
    get_active_special_workspace = function() end,
    dispatch = function(request) dispatched = request end,
    unbind = function(key) bindings[key:gsub("%s", ""):upper()] = nil end,
    bind = function(key, action, options)
        local chord = key:gsub("%s", ""):upper()
        assert(not bindings[chord], "Duplicate registration: " .. chord)
        bindings[chord] = { action = action, options = options or {}, keys = key, enabled = true,
            set_enabled = function(self, enabled) self.enabled = enabled end }
        return bindings[chord]
    end,
}
local module = dofile("hyprland/modules/Binds.lua")
dofile("hyprland/deck/Deck.lua")
local by_id = {}
for _, binding in pairs(bindings) do
    local id = (binding.options.description or ""):match("^icewine:([a-z0-9_]+)$")
    if id then assert(not by_id[id]); by_id[id] = binding end
end
for _, id in ipairs(definitions.order) do
    assert(by_id[id] or id == "browser" and apps.browser == "", "Missing managed action: " .. id)
end
-- Group members still dispatch their own direction/number after arbitrary remaps.
for i = 1, 10 do
    assert(by_id["workspace_" .. i].action.workspace == i)
    assert(by_id["move_workspace_" .. i].action.workspace == i)
end
for key, direction in pairs({ left = "l", right = "r", up = "u", down = "d" }) do
    by_id["focus_" .. key].action(); assert(dispatched.direction == direction)
    by_id["swap_" .. key].action(); assert(dispatched.direction == direction)
    by_id["resize_" .. key].action(); assert(dispatched.relative == true)
end
-- Preview capture toggles only available internal handles, never saved actions.
for chord, action in pairs({ TAB = "quickshell:previewTab", ["SHIFT+TAB"] = "quickshell:previewBacktab" }) do
    local binding = assert(bindings[chord])
    if binding.options.description == "icewine:preview-tab" or binding.options.description == "icewine:preview-backtab" then
        assert(not binding.enabled and binding.action == action)
        assert(not binding.options.non_consuming and not binding.options.ignore_mods)
    end
end
for _, enabled in ipairs({false, true, false}) do
    module.set_preview_tabs(enabled)
    for _, binding in pairs(bindings) do
        local preview = binding.options.description == "icewine:preview-tab" or binding.options.description == "icewine:preview-backtab"
        assert(binding.enabled == (not preview or enabled))
    end
end
-- Suppress/restore the selected mouse chords, preserving keyboard bindings.
local move, resize = definitions.chord("drag_move"), definitions.chord("drag_resize")
module.supress_mouse_binds(true)
assert(not bindings[move:gsub("%s", ""):upper()] and not bindings[resize:gsub("%s", ""):upper()])
assert(bindings[definitions.values.launcher])
module.supress_mouse_binds(false)
local taskbar_mods = {}
for modifier in definitions.values.taskbar:gmatch("([^+]+)+") do taskbar_mods[modifier] = true end
for mod, keys in pairs({ SUPER = {"SUPER_L", "SUPER_R"}, CTRL = {"CONTROL_L", "CONTROL_R"},
                        SHIFT = {"SHIFT_L", "SHIFT_R"}, ALT = {"ALT_L", "ALT_R"} }) do
    for _, key in ipairs(keys) do
        local helper = bindings[key]
        if helper then
            assert(helper.action == "quickshell:" .. (taskbar_mods[mod] and "topbarModifier" or "topbarOpeningModifier"))
            assert(helper.options.transparent and helper.options.ignore_mods and helper.options.non_consuming)
        end
    end
end
assert(by_id.switcher.options.transparent)
assert(by_id.taskbar.options.transparent and by_id.taskbar.options.submap_universal)
assert(bindings.F14.options.transparent and bindings.F14.options.ignore_mods)
assert(bindings.F16.options.locked and bindings.F16.options.ignore_mods)
assert(bindings.F17.options.dont_inhibit and bindings.F17.options.submap_universal)
local actions = {
    launcher = "qs ipc call topbar launcher", terminal = "xdg-terminal-exec",
    filemanager = 'xdg-open "$HOME"', screenshot = "icewine screenshot", lock = "qs ipc call session lock",
    power = "qs ipc call topbar battery",
}
for id, action in pairs(actions) do assert(by_id[id].action == action) end
local masks = { SUPER = 64, SHIFT = 1, CTRL = 4, ALT = 8 }
local rows = {}
for chord, binding in pairs(bindings) do
    local parts, mask = {}, 0
    for part in chord:gmatch("[^+]+") do parts[#parts + 1] = part end
    for index = 1, #parts - 1 do mask = mask + assert(masks[parts[index]]) end
    local options = binding.options
    local fields = { string.format('"key":%q,"modmask":%d,"keycode":0,"submap":"","description":%q',
        binding.keys:match("([^+%s]+)$"), mask, options.description or "") }
    -- Hyprland 0.56.2 hlBind ignores opts.mouse. HyprCtl serializes kb.mouse
    -- (false for Lua), not that option; drag/resize dispatchers own releasePending.
    fields[#fields + 1] = '"mouse":false,"dispatcher":"__lua"'
    for _, flag in ipairs({ "release", "locked", "non_consuming", "catch_all" }) do
        fields[#fields + 1] = string.format('%q:%s', flag, tostring(options[flag] == true))
    end
    fields[#fields + 1] = '"repeat":' .. tostring(options.repeating == true)
    rows[#rows + 1] = "{" .. table.concat(fields, ",") .. "}"
end
print("[" .. table.concat(rows, ",") .. "]")
