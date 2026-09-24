-- Run: lua hyprland/tests/window-policy.lua hyprland/modules/WindowPolicy.lua
local events, active, windows, configured = {}, nil, {}, nil
hl = {
	on = function(event, callback) events[event] = callback end,
	get_active_window = function() return active end,
	get_active_monitor = function() return active.monitor end,
	get_windows = function() return windows end,
	config = function(config) configured = config.scrolling.column_width end,
	dsp = {
		layout = function(command) return command end,
		window = { fullscreen = function(request) return request end },
	},
	dispatch = function(request)
		if type(request) == "string" then
			local width = assert(tonumber(request:match("^colresize (.+)$")))
			active.size = { w = width * active.monitor.width }
		else
			assert(request.window == active and request.mode == "fullscreen" and request.layout_aware)
			assert(request.action == "set" or request.action == "unset")
			active.fullscreen = request.action == "set"
			events["window.fullscreen"](active)
		end
	end,
}
local policy = dofile(assert(arg[1], "Pass the WindowPolicy.lua path"))
local normal = { width = 1920, height = 1080 }
local boundary = { width = 2560, height = 1280 }
local intermediate = { width = 2560, height = 1200 }
local wide = { width = 5120, height = 1440 }
local function window(monitor, width, fullscreen)
	active = {
		address = #windows + 1, monitor = monitor,
		workspace = { tiled_layout = "scrolling" },
		size = { w = width * (monitor.width or 1) }, fullscreen = fullscreen,
	}
	windows[#windows + 1] = active
	return active
end
local function check(width, fullscreen)
	assert(math.abs(active.size.w / active.monitor.width - width) < 0.001,
		"unexpected column width")
	assert(active.fullscreen == fullscreen, "unexpected fullscreen state")
end

-- Default targets and monitor fullscreen policy, through real window events.
window(wide, 1.0, false)
events["window.open"](active)
check(0.5, false)
policy.adjust_width(0.05)
check(0.55, false)

-- A wide monitor must preserve a client's explicit fullscreen request.
window(wide, 1.0, true)
events["window.open"](active)
check(1.0, true)
policy.toggle_fullscreen()
check(0.5, false)

window(normal, 1.0, false)
events["window.open"](active)
check(1.0, true)
policy.toggle_fullscreen()
check(1.0, false)
policy.toggle_fullscreen()
check(1.0, true)
policy.adjust_width(-0.05)
check(0.95, false)

-- Exactly 2:1 remains fullscreen; only a strictly wider monitor uses half width.
window(boundary, 1.0, false)
events["window.open"](active)
check(1.0, true)
policy.toggle_fullscreen()
check(1.0, false)

-- A monitor just above 2:1 uses half width and stays tiled.
window(intermediate, 1.0, false)
events["window.open"](active)
check(0.5, false)

-- Adopt a user's explicit width/fullscreen choice, then move to a wide monitor.
window(normal, 0.7, false)
events["config.reloaded"]()
active.monitor, active.size = wide, { w = wide.width }
events["window.move_to_workspace"](active)
check(0.7, false)

-- An invalid monitor gets a numeric width fallback, but must not be classified
-- as opening fullscreen by default: preserve a client's fullscreen request.
window({}, 1.0, true)
events["monitor.focused"](active.monitor)
assert(configured == 1.0)
events["window.open"](active)
active.monitor, active.size = wide, { w = wide.width }
events["window.move_to_workspace"](active)
check(1.0, true)

-- A valid narrow monitor's fullscreen default is not an explicit client choice.
window(normal, 1.0, true)
events["window.open"](active)
active.monitor, active.size = wide, { w = wide.width }
events["window.move_to_workspace"](active)
check(0.5, false)
print("window policy: defaults, user overrides, toggles, adjustments and invalid-monitor fallback pass")
