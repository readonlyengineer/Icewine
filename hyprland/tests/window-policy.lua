-- Run: lua hyprland/tests/window-policy.lua hyprland/modules/WindowPolicy.lua
local events, active, windows, configured = {}, nil, {}, nil
local rules, closed, focuses = {}, nil, 0
hl = {
	on = function(event, callback) events[event] = callback end,
	window_rule = function(rule)
		local saved = rules[rule.name] or {}
		for key, value in pairs(rule) do saved[key] = value end
		function saved:set_enabled(enabled) self.enabled = enabled end
		rules[rule.name] = saved
		return saved
	end,
	get_active_window = function() return active end,
	get_active_monitor = function() return active.monitor end,
	get_windows = function() return windows end,
	config = function(config) configured = config.scrolling.column_width end,
	dsp = {
		layout = function(command) return command end,
		focus = function(request) return { focus = request.window } end,
		window = {
			fullscreen = function(request) return request end,
			close = function(request) return { close = request.window } end,
		},
	},
	dispatch = function(request)
		if type(request) == "string" then
			local width = assert(tonumber(request:match("^colresize (.+)$")))
			active.size = { w = width * active.monitor.width }
		elseif request.focus then
			active, focuses = request.focus, focuses + 1
		elseif request.close then
			closed = request.close
			closed.mapped = false
			events["window.close"](closed)
		else
			assert(request.mode == "fullscreen")
			assert(request.layout_aware, "Fullscreen must remain managed by the scrolling layout")
			assert(request.action == "set" or request.action == "unset")
			assert(request.window.initial_title ~= "Icewine Steam launch",
				"Handoff must not toggle the placeholder's fullscreen state")
			request.window.fullscreen = request.action == "set"
			events["window.fullscreen"](request.window)
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
		mapped = true,
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

local placement = rules["icewine-steam-placement"]
assert(not placement.enabled and placement.no_initial_focus)
assert(not placement.no_anim and not rules["icewine-steam-placeholder"].no_anim,
	"Steam and its placeholder must retain normal navigation animations")
assert(placement.suppress_event:find("fullscreenoutput", 1, true))
local function placeholder(id)
	local win = window(normal, 1, true)
	win.initial_title = "Icewine Steam launch"
	win.workspace.id, win.workspace.name = id, tostring(id)
	events["window.open"](win)
	return win
end

-- Keep the reserved workspace, but follow Steam when startup completes.
local splash = placeholder(2)
assert(placement.enabled and placement.workspace == "2 silent")
local elsewhere = window(normal, 1, true)
elsewhere.workspace.id = 1
local game = window(normal, 1, false)
game.class, game.workspace = "gamescope", splash.workspace
active = elsewhere -- the no-initial-focus rule keeps this window active at map.
local before = focuses
events["window.open"](game)
assert(active == game and focuses == before + 1, "Startup did not focus Steam")
assert(game.workspace.id == 2, "Steam lost its reserved workspace")
assert(game.fullscreen and closed == splash and not placement.enabled)

-- Moving the placeholder updates placement; reloading preserves the reservation.
splash = placeholder(2)
splash.workspace.id = 3
events["window.move_to_workspace"](splash)
assert(placement.workspace == "3 silent")
events["config.reloaded"]()
assert(placement.enabled and placement.workspace == "3 silent")
game = window(normal, 1, false)
game.class, game.workspace = "gamescope", splash.workspace
active = splash
events["window.open"](game)
assert(active == game and game.fullscreen and closed == splash,
	"Foreground startup did not transfer focus")

-- Closing the placeholder releases placement rather than affecting later launches.
splash = placeholder(2)
splash.mapped = false
events["window.close"](splash)
assert(not placement.enabled)
game = window(normal, 1, false)
game.class = "gamescope"
closed = nil
events["window.open"](game)
assert(closed == nil and active == game)
print("Steam placeholder: workspace reservation, background/foreground handoff, move, reload and close pass")
