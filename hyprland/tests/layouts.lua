-- Dedicated fixture for real native layout preference helpers (no compositor).
local root, module = assert(arg[1]), assert(arg[2])
local callbacks, native = {}, {}
local layouts
local reconciliations = 0
package.loaded["icewine.modules.WindowPolicy"] = {
    autofullscreen = function(ws) return layouts.autofullscreen(ws, false) end,
    refresh_autofullscreen = function() reconciliations = reconciliations + 1 end,
}
local ws = {
    { id = 1, config_name = "1" }, { id = 2, config_name = "2" },
    { id = -1337, config_name = "name:old" }, { id = -99, config_name = "special:scratch" },
}
local default = "scrolling"
local function refresh()
    for _, workspace in ipairs(ws) do
        workspace.tiled_layout = default
        workspace.gaps_in = 0
        for _, rule in ipairs(native) do
            if rule.enabled and rule.workspace:match("^%s*(.-)%s*$") == workspace.config_name then
                workspace.tiled_layout = rule.layout
                if rule.gaps_in then workspace.gaps_in = rule.gaps_in end
            end
        end
    end
end
hl = {
    on = function(name, callback) callbacks[name] = callback end,
    get_workspaces = function() return ws end,
    get_config = function(name) assert(name == "general.layout"); return default end,
    workspace_rule = function(request)
        -- Native replaceOrAdd merges only an identical, enabled RAW selector.
        local rule
        for _, candidate in ipairs(native) do
            if candidate.enabled and candidate.workspace == request.workspace then rule = candidate; break end
        end
        if not rule then
            rule = { workspace = request.workspace, enabled = true }
            function rule:set_enabled(enabled) self.enabled = enabled; refresh() end
            table.insert(native, rule)
        end
        for key, value in pairs(request) do rule[key] = value end
        refresh()
        return rule
    end,
}
local user = hl.workspace_rule({workspace = "1", layout = "master"})
layouts = dofile(module)
local function identity(id)
    return assert(layouts.status(id):match('"identity":"([0-9a-f]+)"'))
end
local function select(id, layout)
    layouts.select(id, identity(id), layout)
end
assert(layouts.default() == "scrolling")
local file = assert(io.open(root .. "/state/icewine/layout", "w")); file:write("monocle\n"); file:close()
assert(layouts.default() == "monocle")
file = assert(io.open(root .. "/state/icewine/layout", "w")); file:write("bogus\n"); file:close()
assert(layouts.default() == "scrolling")
assert(not pcall(layouts.select, 1, identity(1), "bogus"))
assert(not pcall(layouts.select, 1.5, "31", "master"))
assert(not pcall(layouts.select, 90, "31", "master"))
select(1, "dwindle")
assert(ws[1].tiled_layout == "dwindle" and ws[2].tiled_layout == "scrolling")
assert(user.enabled and user.layout == "master")
assert(layouts.status(1):find('"override":"dwindle"', 1, true))
select(-1337, "monocle"); select(-99, "master")
assert(ws[3].tiled_layout == "monocle" and ws[4].tiled_layout == "master")
-- Native named/special IDs may be reused. Reject the old identity before any
-- session write/rule change, for both selection and reset of the replacement.
for index, name in pairs({[3] = "name:new", [4] = "special:new"}) do
    local original = ws[index]
    local captured = identity(original.id)
    local stored = assert(io.open(root .. "/runtime/hypr/fixture/icewine-layouts", "r"))
    local before = stored:read("*a"); stored:close()
    ws[index] = {id = original.id, config_name = name}
    hl.workspace_rule({workspace = name, layout = "master"})
    for _, layout in ipairs({"dwindle", "default"}) do
        local ok, error = pcall(layouts.select, original.id, captured, layout)
        assert(not ok and tostring(error):find("Workspace identity changed", 1, true))
        assert(ws[index].tiled_layout == "master")
        stored = assert(io.open(root .. "/runtime/hypr/fixture/icewine-layouts", "r"))
        assert(stored:read("*a") == before); stored:close()
    end
    ws[index] = original; refresh()
end
-- A later ordinary rule wins externally, then a new picker choice must win
-- again without changing that rule's non-layout properties or other workspaces.
select(2, "master")
local external = hl.workspace_rule({workspace = "2", layout = "monocle", gaps_in = 23})
assert(ws[2].tiled_layout == "monocle" and ws[2].gaps_in == 23)
assert(layouts.status(2):find('"effective":"monocle"', 1, true))
select(2, "dwindle")
assert(ws[2].tiled_layout == "dwindle" and ws[2].gaps_in == 23,
    "Reselection lost precedence to the later ordinary rule")
assert(ws[1].tiled_layout == "dwindle" and external.enabled and external.layout == "monocle")
-- Failed storage must not disable the active picker handle before saving.
local open = io.open
io.open = function(path, mode) if mode == "w" then return nil, "fixture write failure" end; return open(path, mode) end
assert(not pcall(layouts.select, 2, identity(2), "scrolling"))
io.open = open
assert(ws[2].tiled_layout == "dwindle" and ws[2].gaps_in == 23)
select(2, "default")
assert(ws[2].tiled_layout == "monocle" and ws[2].gaps_in == 23 and external.enabled)
-- A fresh Lua module after native reload restores choices after user rules.
native = {}; user = hl.workspace_rule({workspace = "1", layout = "master"})
layouts = dofile(module); callbacks["config.reloaded"]()
assert(ws[1].tiled_layout == "dwindle" and ws[3].tiled_layout == "monocle")
select(1, "default")
assert(ws[1].tiled_layout == "master" and user.enabled)
default = "monocle"; refresh()
assert(ws[2].tiled_layout == "monocle")
assert(layouts.status(2):find('"override":""', 1, true))
-- External native changes are reported, rather than cached as picker success.
default = "dwindle"; refresh()
assert(layouts.status(2):find('"effective":"dwindle"', 1, true))
-- Boolean overrides share compositor-session storage, including explicit false.
layouts.select_autofullscreen(1, identity(1), true)
layouts.select_autofullscreen(2, identity(2), false)
assert(layouts.autofullscreen(ws[1], false) == true)
assert(layouts.autofullscreen(ws[2], true) == false)
assert(layouts.autofullscreen(ws[3], true) == true)
assert(layouts.status(1):find('"autofullscreen":true', 1, true))
assert(reconciliations == 2)
assert(not pcall(layouts.select_autofullscreen, 1, "wrong", false))
assert(not pcall(layouts.select_autofullscreen, 1, identity(1), "off"))
io.open = function(path, mode) if mode == "w" then return nil, "fixture write failure" end; return open(path, mode) end
assert(not pcall(layouts.select_autofullscreen, 1, identity(1), false))
io.open = open
assert(layouts.autofullscreen(ws[1], false) == true and reconciliations == 2)
select(1, "master") -- Layout changes must retain both boolean overrides.
layouts = dofile(module); callbacks["config.reloaded"]()
assert(layouts.autofullscreen(ws[1], false) == true)
assert(layouts.autofullscreen(ws[2], true) == false)
-- Next compositor instance has a new signature and no previous choices.
local getenv = os.getenv
os.getenv = function(name) if name == "HYPRLAND_INSTANCE_SIGNATURE" then return "next-session" end; return getenv(name) end
native = {}; default = "scrolling"; hl.workspace_rule({workspace = "1", layout = "master"})
layouts = dofile(module); callbacks["config.reloaded"](); refresh()
assert(ws[1].tiled_layout == "master" and ws[3].tiled_layout == "scrolling")
assert(layouts.autofullscreen(ws[1], false) == false)
assert(layouts.autofullscreen(ws[2], true) == true)
print("PASS native layout helpers: fallback, captured IDs, user-rule reset, failure, later-rule reselection/reset, reload and logout")
