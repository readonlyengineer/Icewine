-- Run with an isolated installed config: lua hyprland/tests/startup.lua ENTRY handheld|desktop
local entry, profile = assert(arg[1]), assert(arg[2])
local emptyBrowser = arg[3] == "empty-browser"
local legacyBrowser = not emptyBrowser and arg[3]
local config = assert(os.getenv("XDG_CONFIG_HOME")) .. "/hypr/"
local binds = 0
local environment, commands, callbacks, launches = {}, {}, {}, {}
local getenv = os.getenv
os.getenv = function(name)
    if name == "EDITOR" then return "user-editor --flag" end
    if name == "VISUAL" then return "user-visual" end
    return getenv(name)
end
local action = setmetatable({}, { __index = function() return function() return {} end end })
hl = setmetatable({
    dsp = setmetatable({ window = action, exec_cmd = function(command) return { command = command } end }, { __index = function() return function() return {} end end }),
    bind = function(key, action)
        binds = binds + 1
        commands[key] = commands[key] or {}
        table.insert(commands[key], type(action) == "table" and action.command or false)
    end,
    env = function(name, value) environment[name] = value end,
    on = function(name, callback)
        if debug.getinfo(callback, "S").source == "@" .. entry then callbacks[name] = callback end
    end,
    exec_cmd = function(command) table.insert(launches, command) end,
}, { __index = function() return function() end end })
-- Exercise the real packaged bootstrap, then an ordinary inline override.
assert(not io.open(config .. "modules/Binds.lua"), "Shared aliases leaked into user configuration")
local file = assert(io.open(entry))
local contents = file:read("*a"); file:close()
assert(not contents:find('"@[%w_]+@"'), "Unpopulated template")
local defaults = dofile(config .. "icewine/modules/DefaultApps.lua")
assert(defaults.terminal == "xdg-terminal-exec" and defaults.file_manager == 'xdg-open "$HOME"',
       "Shared shortcuts bypass XDG defaults")
if not legacyBrowser then
    for name, value in pairs({terminal = "custom-terminal", file_manager = "custom-files", browser = emptyBrowser and "" or "custom-browser"}) do
        contents = contents:gsub('apps%.' .. name .. ' = [^\n]+', 'apps.' .. name .. ' = "' .. value .. '"', 1)
    end
    contents = contents:gsub('%-%- hl.on', 'hl.on'):gsub('%-%-     hl.exec_cmd', '    hl.exec_cmd'):gsub('%-%- end%)', 'end)')
end
file = assert(io.open(entry, "w"))
file:write(contents)
file:write('\n_G.user_override_loaded = package.loaded["icewine.modules.Binds"] ~= nil\n')
file:close()
package.path = config .. "?.lua;" .. package.path
dofile(entry)
assert(environment.EDITOR == nil and environment.VISUAL == nil,
       "Compositor assigned editor variables")
local function command(key)
    local values = commands[key] or {}
    assert(#values <= 1, "Duplicate application binding: " .. key)
    return values[1]
end
if legacyBrowser then
    assert(command("SUPER + RETURN") == "xdg-terminal-exec" and command("SUPER + E") == 'xdg-open "$HOME"'
           and command("SUPER + B") == legacyBrowser, "Legacy entry lost application hotkeys")
else
    local apps = package.loaded["icewine.modules.DefaultApps"]
    assert(apps.terminal == "custom-terminal" and apps.file_manager == "custom-files"
           and apps.editor == nil, "Editable commands missed shared defaults or defined an editor")
    assert(command("SUPER + RETURN") == "custom-terminal" and command("SUPER + E") == "custom-files"
           and command("SUPER + B") == (not emptyBrowser and "custom-browser" or nil), "Shared application bindings missed editable commands")
    assert(#launches == 0)
    callbacks["hyprland.start"]()
    assert(#launches == 1 and launches[1] == "custom-terminal")
    assert(not callbacks["config.reloaded"], "Autolaunch registered on reload")
end
assert(user_override_loaded, "Inline overrides did not run after shared bindings")
assert(type(package.loaded["icewine.modules.Binds"].supress_mouse_binds) == "function")
assert(package.loaded["icewine.modules.WindowPolicy"])
assert((package.loaded["icewine.modules.Deck"] ~= nil) == (profile == "handheld"))
assert(binds > 20, "Real packaged bindings were not registered")
print("packaged Hyprland " .. profile .. " startup checks passed")
