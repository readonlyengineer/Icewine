-- Run with an isolated installed config: lua hyprland/tests/startup.lua ENTRY handheld|desktop
local entry, profile = assert(arg[1]), assert(arg[2])
local config = assert(os.getenv("XDG_CONFIG_HOME")) .. "/hypr/"
local binds = 0
local environment = {}
local getenv = os.getenv
os.getenv = function(name)
    if name == "EDITOR" then return "user-editor --flag" end
    if name == "VISUAL" then return "user-visual" end
    return getenv(name)
end
local action = setmetatable({}, { __index = function() return function() return {} end end })
hl = setmetatable({
    dsp = setmetatable({ window = action }, { __index = function() return function() return {} end end }),
    bind = function() binds = binds + 1 end,
    env = function(name, value) environment[name] = value end,
}, { __index = function() return function() end end })
-- Exercise the real packaged bootstrap, then an ordinary inline override.
assert(not io.open(config .. "modules/Binds.lua"), "Shared aliases leaked into user configuration")
local file = assert(io.open(entry, "a"))
file:write('\n_G.user_override_loaded = package.loaded["icewine.modules.Binds"] ~= nil\n')
file:close()
package.path = config .. "?.lua;" .. package.path
dofile(entry)
assert(environment.EDITOR == "user-editor --flag" and environment.VISUAL == "user-visual",
       "Compositor replaced deliberate editor overrides")
assert(user_override_loaded, "Inline overrides did not run after shared bindings")
assert(type(package.loaded["icewine.modules.Binds"].supress_mouse_binds) == "function")
assert(package.loaded["icewine.modules.WindowPolicy"])
assert((package.loaded["icewine.modules.Deck"] ~= nil) == (profile == "handheld"))
assert(binds > 20, "Real packaged bindings were not registered")
print("packaged Hyprland " .. profile .. " startup checks passed")
