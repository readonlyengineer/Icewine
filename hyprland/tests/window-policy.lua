-- Run: lua hyprland/tests/window-policy.lua hyprland/modules/WindowPolicy.lua
local events, active, windows, workspaces, configured = {}, nil, {}, {}, nil
local rules, closed, focuses = {}, nil, 0
local fitted = {}
local setting = "on\n"
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
	get_window = function(selector)
		local pid = assert(tonumber(selector:match("^pid:(%d+)$")))
		for _, win in ipairs(windows) do if win.pid == pid then return win end end
	end,
	get_workspaces = function() return workspaces end,
	get_workspace_windows = function(ws) return ws.windows or {} end,
	config = function(config) configured = config.scrolling.column_width end,
	dsp = {
		layout = function(command) return command end,
		focus = function(request) return { focus = request.window } end,
		window = {
			float = function(request) return { float = request.window } end,
			fullscreen = function(request) return request end,
			close = function(request) return { close = request.window } end,
			move = function(request) return { move = request } end,
		},
	},
	dispatch = function(request)
		if request == "fit_into_view" then
			assert(active and active.workspace.tiled_layout == "scrolling")
			fitted[#fitted + 1] = active
		elseif type(request) == "string" then
			local width = assert(tonumber(request:match("^colresize (.+)$")))
			active.size = { w = width * active.monitor.width }
		elseif request.float then
			request.float.floating = not request.float.floating
		elseif request.focus then
			active, focuses = request.focus, focuses + 1
		elseif request.move then
			assert(request.move.follow == false)
			request.move.window.workspace = request.move.workspace
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
local original_open = io.open
io.open = function(path, mode)
	if path:match("/icewine/autofullscreen$") then
		return { read = function() return setting end, close = function() end }
	end
	return original_open(path, mode)
end
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

-- A default-width established window follows its workspace to a wide monitor.
-- The saved fullscreen choice is false, so it was previously skipped here.
local moved = window(normal, 1.0, false)
moved.workspace.active, moved.workspace.windows = true, { moved }
workspaces = { moved.workspace }
events["window.open"](moved)
policy.toggle_fullscreen()
moved.monitor, moved.size = wide, { w = wide.width }
events["monitor.layout_changed"]()
check(0.5, false)
assert(#fitted == 1 and fitted[1] == moved,
	"Expected one view adjustment of the resized active window")

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

assert(not rules["icewine-steam-placement"], "Catch-all Gamescope placement remains")
local function placeholder(id)
    local win = window(normal, 1, true)
    win.initial_title = "Icewine Steam launch"
    win.workspace.id, win.workspace.name = id, tostring(id)
    events["window.open"](win)
    return win
end

local splash = placeholder(2)
local unrelated = window(normal, 1, false)
unrelated.class, unrelated.pid = "gamescope", 111
local previous_workspace = unrelated.workspace
closed = nil
events["window.open"](unrelated)
policy.handoff_steam(222)
assert(closed == nil and unrelated.workspace == previous_workspace,
    "Unrelated Gamescope consumed Steam's reservation")
for _, pid in ipairs({0, -1, 1.5, "111"}) do policy.handoff_steam(pid) end
assert(closed == nil, "Invalid PID reached handoff")
local game = window(normal, 1, false)
game.class, game.pid = "gamescope", 222
events["window.open"](game)
policy.handoff_steam(222)
assert(active == game and game.fullscreen and closed == splash,
    "Matching Steam session did not receive fullscreen/focus")
assert(game.workspace.id == 2, "Steam lost its reserved workspace")

-- Moving/reloading the placeholder preserves the target for explicit handoff.
splash = placeholder(2)
splash.workspace.id = 3
events["window.move_to_workspace"](splash)
events["config.reloaded"]()
policy.handoff_steam(222)
assert(game.workspace.id == 3 and closed == splash, "Reload lost the reservation")

splash = placeholder(4)
splash.mapped = false
events["window.close"](splash)
closed = nil
policy.handoff_steam(222)
assert(closed == nil and game.workspace.id == 3,
    "Closed placeholder still moved the Steam session")
print("Steam placeholder: PID identity, reserved workspace, fullscreen/focus, reload and close pass")

-- Exercise the event-driven policy; no polling or native intent tags are needed.
local function workspace(layout)
	local ws = { tiled_layout = layout, windows = {}, active = true }
	workspaces[#workspaces + 1] = ws
	return ws
end
local function tiled(ws, fullscreen)
	local win = window(normal, 1, fullscreen or false)
	win.workspace = ws
	ws.windows[#ws.windows + 1] = win
	ws.last_window = win
	events["window.open"](win)
	return win
end
workspaces, windows = {}, {}
policy = dofile(arg[1])
for _, layout in ipairs({ "dwindle", "master" }) do
	local ws = workspace(layout)
	local first = tiled(ws)
	assert(first.fullscreen, layout .. ": lone window did not fullscreen")
	local second = tiled(ws)
	assert(not first.fullscreen and not second.fullscreen, layout .. ": pair did not tile")
	policy.toggle_floating()
	assert(first.fullscreen and not second.fullscreen, "floating window counted")
	policy.toggle_floating()
	assert(not first.fullscreen, "unfloat did not release singleton fullscreen")
	events["window.close"](second) -- May precede collection removal.
	second.mapped = false
	assert(first.fullscreen, "close did not restore singleton fullscreen")
	setting = "off\n"
	policy.refresh_autofullscreen()
	assert(not first.fullscreen, "off command retained automatic fullscreen")
	setting = "on\n"
	policy.refresh_autofullscreen()
	assert(first.fullscreen, "on command did not restore automatic fullscreen")
	active = first
	policy.toggle_fullscreen()
	policy.refresh_autofullscreen()
	assert(not first.fullscreen, "automatic policy erased manual off")
	policy.toggle_fullscreen()
	setting = "off\n"
	policy.refresh_autofullscreen()
	assert(first.fullscreen, "off erased explicit fullscreen")
	setting = "on\n"
	policy.refresh_autofullscreen()
end
workspaces, windows = {}, {}
policy = dofile(arg[1])
local source, destination = workspace("dwindle"), workspace("master")
local first, moved = tiled(source), tiled(source)
source.windows, destination.windows = { first }, { moved }
moved.workspace = destination
events["window.move_to_workspace"](moved)
assert(first.fullscreen and moved.fullscreen, "move did not reconcile source and destination")
source.tiled_layout = "monocle"
local next_window = tiled(source)
assert(not first.fullscreen and next_window.fullscreen, "monocle default did not follow focus")
active = first
events["window.active"](first)
assert(first.fullscreen and not next_window.fullscreen, "monocle focus did not transfer default")
setting = "off\n"
policy.refresh_autofullscreen()
assert(not first.fullscreen and not next_window.fullscreen, "monocle off retained automatic fullscreen")
first.fullscreen = true
events["window.fullscreen"](first)
policy.refresh_autofullscreen()
assert(first.fullscreen, "application fullscreen was lost")
events["config.reloaded"]()
assert(first.fullscreen, "reload erased current fullscreen")
print("layout policy: singleton open/close/move/float, monocle focus, live toggle and explicit intent pass")
