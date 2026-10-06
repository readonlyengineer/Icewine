-- Run: lua hyprland/tests/docking.lua hyprland/modules/Docking.lua
local setup = dofile(assert(arg[1], "Pass the Docking.lua path"))
local outputs, rules, events = {}, {}, {}
hl = {
		get_monitors = function() return outputs end,
	workspace_rule = function(rule) rules[rule.workspace] = rule end,
	on = function(event, callback) events[event] = callback end,
}
local real_open = io.open
io.open = function()
 local closed = true
 for _, output in ipairs(outputs) do if output.name == "eDP-1" then closed = false end end
 return {read=function() return "state: " .. (closed and "closed" or "open") end, close=function() end}
end
hl.monitor = function() end
hl.bind = function(_, callback) events.lid = callback end
setup({output="eDP-1", mode="preferred"}, {"/lid"})
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
check({panel,tv,dock,{name="USB-C-1", x=4000}}, (function() local e = {}; for id = 1, 10 do e[id] = id <= 4 and tv.name or id <= 8 and dock.name or panel.name end; return e end)(), "monitor.added") -- Ignore third and later externals.
dock.x = tv.x
check({panel,tv,dock}, (function() local e = {}; for id = 1, 10 do e[id] = id <= 4 and dock.name or id <= 8 and tv.name or panel.name end; return e end)(), "monitor.added") -- Name breaks position ties.
dock.x = 1920
check({panel}, repeated(panel, panel), "monitor.removed")
outputs = {{name="FALLBACK"}}
events["monitor.removed"]()
assert(rules["1"].monitor == panel.name) -- No physical display: retain bindings.
print("native docking bindings: dock, lid, multiple externals, unplug and no-display checks pass")

-- Calibrated callers reconcile desired panel state before deferred monitor refresh.
local state, readable = "closed", true
local writes, workspace_writes, lid, monitors = {}, 0, nil, {}
io.open = function(path)
 assert(path == "/lid")
 if not readable then return nil end
 return { read = function() return "state: " .. state end, close = function() end }
end
hl.monitor = function(rule)
 writes[#writes + 1] = rule
 -- Deliberately do not update the monitor query until after the callback ends.
end
hl.get_monitors = function() return monitors end
hl.bind = function(trigger, callback, options)
 assert(trigger == "switch:Lid Switch" and options.locked)
 lid = callback
end
hl.workspace_rule = function(rule) rules[rule.workspace] = rule; workspace_writes = workspace_writes + 1 end
local calibrated = {output="eDP-1", mode="native", position="0x0", scale=1.5, transform=3}
setup(calibrated, {"/lid"})
assert(#writes == 1 and writes[1].disabled and workspace_writes == 0) -- Closed, no externals.
monitors = {panel, dock, tv} -- Stale panel remains visible after disable request.
events["monitor.added"]()
assert(rules["5"].monitor == tv.name and rules["6"].monitor == dock.name)
lid(); events["monitor.removed"]()
assert(#writes == 1) -- Repeated/deferred events do not reapply the monitor rule.
state = "open"
monitors = {tv} -- Disabled panel absent: configured identity must still restore.
lid()
assert(#writes == 2 and writes[2] == calibrated and not writes[2].disabled)
assert(writes[2].position == "0x0" and writes[2].transform == 3)
assert(rules["8"].monitor == tv.name and rules["9"].monitor == panel.name)
-- The native monitor rule schedules refresh after the current callback.
monitors = {tv, dock}
events["monitor.added"](); lid()
assert(#writes == 2 and rules["5"].monitor == dock.name and rules["9"].monitor == panel.name)
state = "closed"; lid()
assert(#writes == 3 and writes[3].disabled)
readable = false; lid() -- Established source disappears: reopen calibrated panel.
assert(#writes == 4 and not writes[4].disabled and rules["9"].monitor == panel.name)
state, readable = "closed", true; lid()
io.open = function() return {read=function() return nil end, close=function() end} end
lid() -- Established source becomes unreadable: open.
assert(#writes == 6 and not writes[6].disabled)
-- No internal identity: only externals, no monitor rule or lid binding.
io.open = function() error("no internal panel should probe no lid") end
hl.bind = function() error("no internal panel should bind no lid") end
local before = #writes
setup(nil)
assert(#writes == before and rules["6"].monitor == dock.name and rules["10"].monitor == dock.name)
monitors = {{name="FALLBACK"}}
local count = workspace_writes
events["monitor.removed"]()
assert(workspace_writes == count)
io.open = real_open
print("reconcile: closed/no-display, desired/deferred state, repeated/deferred events, source loss and no-panel checks pass")
