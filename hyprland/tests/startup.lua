-- Run with an isolated installed config: lua hyprland/tests/startup.lua ENTRY handheld|desktop
local entry, profile = assert(arg[1]), assert(arg[2])
local config = assert(os.getenv("XDG_CONFIG_HOME")) .. "/hypr/"
local binds = 0
local action = setmetatable({}, { __index = function() return function() return {} end end })
hl = setmetatable({
    dsp = setmetatable({ window = action }, { __index = function() return function() return {} end end }),
    bind = function() binds = binds + 1 end,
}, { __index = function() return function() end end })
-- Deliberately exercise writable hooks, not a copy of the bootstrap logic.
for _, name in ipairs({ "Binds", "Autostart" }) do
    local path = config .. "modules/" .. name .. ".lua"
    local file = assert(io.open(path, "r"))
    local contents = file:read("*a")
    file:close()
    -- Hooks normally alias immutable defaults. A local replacement remains an
    -- active compatibility/host hook; do not write through a package symlink.
    os.remove(path)
    file = assert(io.open(path, "w"))
    -- Prepend because Binds returns its exported functions as its final statement.
    file:write('_G.user_' .. name:lower() .. '_loaded = true\n' .. contents)
    file:close()
end
package.path = config .. "?.lua;" .. package.path
dofile(entry)
assert(user_binds_loaded and user_autostart_loaded, "Writable hooks were shadowed by packaged code")
assert(type(package.loaded["modules.Binds"].supress_mouse_binds) == "function")
assert(package.loaded["modules.Theme"] and package.loaded["modules.WindowPolicy"])
assert((package.loaded["modules.Deck"] ~= nil) == (profile == "handheld"))
assert(binds > 20, "Real writable bindings were not registered")
print("packaged Hyprland " .. profile .. " startup checks passed")
