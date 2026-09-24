-- Run: lua hyprland/tests/docking.lua hyprland/modules/Docking.lua
local setup = dofile(assert(arg[1], "Pass the Docking.lua path"))
local outputs, rules, events = {}, {}, {}
hl = {
	get_monitor = function(name)
		for _, monitor in ipairs(outputs) do if monitor.name == name then return monitor end end
	end,
	get_monitors = function() return outputs end,
	workspace_rule = function(rule) rules[rule.workspace] = rule end,
	on = function(event, callback) events[event] = callback end,
}
setup("eDP-1")
local panel, tv, dock = {name="eDP-1", x=0}, {name="HDMI-A-1", x=0}, {name="DP-1", x=1920}
local function check(monitors, expected, event)
	outputs = monitors
	events[event]()
	for id = 1, 10 do
		local rule = rules[tostring(id)]
		assert(rule.monitor == expected[id], rule.monitor .. " for workspace " .. id)
		assert(rule.persistent)
		assert(rule.default == (id == 1 or expected[id] ~= expected[id - 1]))
	end
end
local function repeated(a, b)
	local expected = {}
	for id = 1, 10 do expected[id] = (id == 10 and b or a).name end
	return expected
end
check({panel}, repeated(panel, panel), "monitor.added")
check({panel,tv}, (function() local e = {}; for id = 1, 10 do e[id] = id <= 8 and tv.name or panel.name end; return e end)(), "monitor.added")
check({tv}, repeated(tv, tv), "monitor.removed") -- Close lid.
check({tv,panel}, (function() local e = {}; for id = 1, 10 do e[id] = id <= 8 and tv.name or panel.name end; return e end)(), "monitor.added") -- Open lid.
check({panel,tv,dock}, (function() local e = {}; for id = 1, 10 do e[id] = id <= 4 and tv.name or id <= 8 and dock.name or panel.name end; return e end)(), "monitor.added")
check({tv,dock}, (function() local e = {}; for id = 1, 10 do e[id] = id <= 5 and tv.name or dock.name end; return e end)(), "monitor.removed") -- Close lid with two externals.
check({dock,tv}, (function() local e = {}; for id = 1, 10 do e[id] = id <= 5 and tv.name or dock.name end; return e end)(), "monitor.added") -- Enumeration order is irrelevant.
check({panel,dock}, (function() local e = {}; for id = 1, 10 do e[id] = id <= 8 and dock.name or panel.name end; return e end)(), "monitor.removed") -- Remove selected external.
check({panel}, repeated(panel, panel), "monitor.removed")
outputs = {{name="FALLBACK"}}
events["monitor.removed"]()
assert(rules["1"].monitor == panel.name) -- No physical display: retain bindings.
print("native docking bindings: dock, lid, multiple externals, unplug and no-display checks pass")
