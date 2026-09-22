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
local panel, tv, dock = {name="eDP-1"}, {name="HDMI-A-1"}, {name="DP-1"}
local function check(monitors, main, auxiliary, event)
	outputs = monitors
	events[event]()
	for id = 1, 10 do
		local rule = rules[tostring(id)]
		assert(rule.monitor == (id == 10 and auxiliary or main).name)
		assert(rule.persistent)
		assert(rule.default == (id == 1 or (id == 10 and auxiliary ~= main)))
	end
end
check({panel}, panel, panel, "monitor.added")
check({panel,tv}, tv, panel, "monitor.added")
check({tv}, tv, tv, "monitor.removed") -- Close lid.
check({tv,panel}, tv, panel, "monitor.added") -- Open lid.
check({panel,tv,dock}, tv, panel, "monitor.added")
check({panel,dock}, dock, panel, "monitor.removed") -- Remove selected external.
check({panel}, panel, panel, "monitor.removed")
outputs = {{name="FALLBACK"}}
events["monitor.removed"]()
assert(rules["1"].monitor == panel.name) -- No physical display: retain bindings.
print("native docking bindings: dock, lid, multiple externals, unplug and no-display checks pass")
