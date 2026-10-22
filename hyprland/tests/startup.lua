-- Run with an isolated installed config: lua hyprland/tests/startup.lua ENTRY handheld|desktop
local entry, profile = assert(arg[1]), assert(arg[2])
local emptyBrowser = arg[3] == "empty-browser"
local legacyBrowser = not emptyBrowser and arg[3]
local config = assert(os.getenv("XDG_CONFIG_HOME")) .. "/hypr/"
local binds, generalLayout = 0, nil
local environment, commands, callbacks, launches, descriptions, monitors = {}, {}, {}, {}, {}, {}
local getenv = os.getenv
os.getenv = function(name)
    if name == "EDITOR" then return "user-editor --flag" end
    if name == "VISUAL" then return "user-visual" end
    return getenv(name)
end
local action = setmetatable({}, { __index = function() return function() return {} end end })
hl = setmetatable({
    dsp = setmetatable({ window = action, exec_cmd = function(command) return { command = command } end }, { __index = function() return function() return {} end end }),
    config = function(values) if values.general and values.general.layout then generalLayout = values.general.layout end end,
    monitor = function(value) monitors[value.output] = true end,
    bind = function(key, action, options)
        if options and options.description then descriptions[options.description] = options end
        binds = binds + 1
        commands[key] = commands[key] or {}
        table.insert(commands[key], type(action) == "table" and action.command or false)
        return { set_enabled = function() end }
    end,
    env = function(name, value) environment[name] = value end,
    on = function(name, callback)
        if debug.getinfo(callback, "S").source == "@" .. entry
            or (profile == "onboarding" and debug.getinfo(callback, "S").source == "@" .. arg[3]) then callbacks[name] = callback end
    end,
    exec_cmd = function(command) table.insert(launches, command) end,
}, { __index = function() return function() end end })
if profile == "onboarding" then
    local original_dofile = dofile
    dofile = function(path)
        if path == "/usr/share/icewine/defaults/config/hypr/hyprland.lua" then path = assert(arg[4]) end
        return original_dofile(path)
    end
    dofile(assert(arg[3]))
    assert(binds > 20 and package.loaded["icewine.modules.Binds"] and package.loaded["icewine.modules.WindowPolicy"])
    assert(descriptions["icewine:terminal"], "Managed hotkey action descriptions missing")
    local helpers = 0
    for name, options in pairs(descriptions) do
        if name:match("^icewine:taskbar%-modifier%-") then
            assert(options.non_consuming)
            helpers = helpers + 1
        end
    end
    assert(helpers > 0, "Managed taskbar modifier helpers missing")
    assert(monitors["saved-monitor"], "Persistent real monitor preferences were not imported")
    assert(callbacks["hyprland.start"] and not callbacks["config.reloaded"])
    callbacks["hyprland.start"]()
    assert(#launches == 1 and launches[1] == 'sh "$ICEWINE_ONBOARDING_RUNNER" terminal')
    print("packaged Hyprland onboarding managed-bind/theme/monitor/session callback checks passed")
    return
end
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
assert(generalLayout == (profile == "handheld" and "scrolling" or package.loaded["icewine.modules.Layouts"].default()),
       "Desktop fallback or intentional handheld layout was lost")
assert((package.loaded["icewine.modules.Deck"] ~= nil) == (profile == "handheld"))
assert(binds > 20, "Real packaged bindings were not registered")
print("packaged Hyprland " .. profile .. " startup checks passed")
