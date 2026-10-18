-- Run: lua hyprland/tests/window-policy.lua hyprland/modules/WindowPolicy.lua
local events, active, windows, workspaces, configured = {}, nil, {}, {}, nil
local active_workspace
local rules, closed, focuses = {}, nil, 0
local fitted = {}
local setting = "on\n"
local timers = {}
local function settle()
	local pending = timers
	timers = {}
	for _, callback in ipairs(pending) do callback() end
end
hl = {
	on = function(event, callback) events[event] = callback end,
	timer = function(callback, options)
		assert(options.type == "oneshot" and options.timeout == 1)
		timers[#timers + 1] = callback
	end,
	window_rule = function(rule)
		local saved = rules[rule.name] or {}
		for key, value in pairs(rule) do saved[key] = value end
		function saved:set_enabled(enabled) self.enabled = enabled end
		rules[rule.name] = saved
		return saved
	end,
	get_active_window = function() return active end,
	get_active_workspace = function() return active and active.workspace or active_workspace end,
	get_active_special_workspace = function() return nil end,
	get_config = function(name)
		assert(name == "animations.enabled" or name == "cursor.no_warps")
		return name == "cursor.no_warps"
	end,
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
		focus = function(request) return { focus = request.window, workspace = request.workspace } end,
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
			if request.float.workspace.tiled_layout == "scrolling" and not request.float.floating and request.float.fullscreen then
				request.float.fullscreen = false
				events["window.fullscreen"](request.float)
			end
			request.float.floating = not request.float.floating
		elseif request.workspace then
			active, active_workspace = nil, request.workspace
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
package.loaded["icewine.modules.Layouts"] = {
    autofullscreen = function(ws, fallback)
        if ws and ws.autofullscreen ~= nil then return ws.autofullscreen end
        return fallback
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
		workspace = { id = #windows + 1, tiled_layout = "scrolling" },
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
	local ws = { id = #workspaces + 1, tiled_layout = layout, windows = {}, active = true }
	workspaces[#workspaces + 1] = ws
	return ws
end
local function tiled(ws, fullscreen)
	local win = window(normal, 1, fullscreen or false)
	win.workspace = ws
	ws.windows[#ws.windows + 1] = win
	-- Hyprland maps the newcomer, clears the old fullscreen owner, then
	-- emits openLate (Lua window.open). This is not a manual off request.
	for _, existing in ipairs(ws.windows) do
		if ws.tiled_layout ~= "scrolling" and existing ~= win and existing.fullscreen then
			existing.fullscreen = false
			events["window.fullscreen"](existing)
		end
	end
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
	events["window.close"](second) -- Native close precedes unmapping/refocus.
	second.mapped, active = false, first
	assert(first.fullscreen, layout .. ": native fullscreen exit poisoned singleton restoration")
	second = tiled(ws)
	assert(not first.fullscreen and not second.fullscreen, layout .. ": reopened pair did not tile")
	policy.toggle_floating()
	assert(first.fullscreen and not second.fullscreen, "floating window counted")
	policy.toggle_floating()
	assert(not first.fullscreen, "unfloat did not release singleton fullscreen")
	-- Focus can arrive after a close has unmapped the other window.
	second.mapped, active = false, first
	events["window.active"](first)
	assert(first.fullscreen, layout .. ": refocus did not restore singleton fullscreen")
	second.mapped, active = true, second
	events["window.active"](second)
	assert(not first.fullscreen and not second.fullscreen, layout .. ": refocused pair did not tile")
	events["window.close"](second) -- May precede collection removal.
	second.mapped = false
	assert(first.fullscreen, "close did not restore singleton fullscreen")
	setting = "off\n"
	policy.refresh_autofullscreen()
	events["window.active"](first)
	assert(not first.fullscreen, "off command retained automatic fullscreen")
	setting = "on\n"
	policy.refresh_autofullscreen()
	assert(first.fullscreen, "on command did not restore automatic fullscreen")
	active = first
	policy.toggle_fullscreen()
	policy.refresh_autofullscreen()
	events["window.active"](first)
	assert(not first.fullscreen, "automatic policy erased manual off")
	policy.toggle_fullscreen()
	setting = "off\n"
	policy.refresh_autofullscreen()
	assert(first.fullscreen, "off erased explicit fullscreen")
	setting = "on\n"
	policy.refresh_autofullscreen()
end
-- Deliberate policy off while a pair is tiled must outlast singleton recovery.
workspaces, windows = {}, {}
policy = dofile(arg[1])
local manual_ws = workspace("dwindle")
local manual_first, manual_second = tiled(manual_ws), tiled(manual_ws)
active = manual_first
policy.toggle_fullscreen()
policy.toggle_fullscreen()
events["window.close"](manual_second)
manual_second.mapped = false
assert(not manual_first.fullscreen, "close erased explicit off set while multiple windows were tiled")
-- Genuine client/user fullscreen events still override the automatic default.
manual_first.fullscreen = true
events["window.fullscreen"](manual_first)
setting = "off\n"
policy.refresh_autofullscreen()
assert(manual_first.fullscreen, "off erased external fullscreen intent")
manual_first.fullscreen = false
events["window.fullscreen"](manual_first)
setting = "on\n"
policy.refresh_autofullscreen()
assert(not manual_first.fullscreen, "on erased external fullscreen-off intent")
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
-- Workspace overrides affect actual policy targets without changing global state.
workspaces, windows = {}, {}
setting = "off\n"
policy = dofile(arg[1])
local enabled_ws, inherited_ws = workspace("dwindle"), workspace("master")
enabled_ws.autofullscreen = true
local enabled_win, inherited_win = tiled(enabled_ws), tiled(inherited_ws)
assert(enabled_win.fullscreen and not inherited_win.fullscreen)
enabled_ws.autofullscreen = false
policy.refresh_autofullscreen()
assert(not enabled_win.fullscreen and not inherited_win.fullscreen)
setting = "on\n"
policy.refresh_autofullscreen()
assert(not enabled_win.fullscreen and inherited_win.fullscreen)
active = enabled_win
policy.toggle_fullscreen()
policy.refresh_autofullscreen()
assert(enabled_win.fullscreen, "workspace override erased manual fullscreen")
-- Scrolling open/toggle-width also use the workspace override.
window(normal, 1.0, false)
active.workspace.autofullscreen = false
events["window.open"](active)
check(1.0, false)
window(normal, 1.0, false)
active.workspace.autofullscreen = true
events["window.open"](active)
check(1.0, true)
print("layout policy: singleton open/close/move/float, monocle focus, live toggle and explicit intent pass")

-- Property refresh observes the effective native layout, not the requested one.
-- Pair transitions distinguish scrolling/monocle from singleton-only layouts.
local function switch_layout(ws, layout)
	-- updateTiledAlgo calls old removeTarget (synchronous fullscreen exit)
	-- before publishing the replacement. Do not move this after assignment.
	if ws.tiled_layout == "scrolling" and layout ~= "scrolling" then
		for _, win in ipairs(ws.windows) do
			if win.fullscreen and not win.floating then
				win.fullscreen = false
				events["window.fullscreen"](win)
			end
		end
	end
	ws.tiled_layout = layout
	events["config.props_refreshed"]()
end
for _, from in ipairs({ "scrolling", "dwindle", "master", "monocle" }) do
	for _, to in ipairs({ "scrolling", "dwindle", "master", "monocle" }) do
		for count = 1, 2 do
			workspaces, windows = {}, {}
			policy = dofile(arg[1])
			local ws = workspace(from)
			local a = tiled(ws)
			local b = count == 2 and tiled(ws) or a
			events["config.props_refreshed"]()
			switch_layout(ws, to)
			settle()
			assert(a.fullscreen == (count == 1 or to == "scrolling"), from .. " -> " .. to .. ": wrong first target")
			assert(b.fullscreen == (count == 1 or to == "scrolling" or to == "monocle"), from .. " -> " .. to .. ": wrong focus target")
			assert(active == b, "layout reconciliation stole focus")
		end
	end
end

for _, layout in ipairs({ "dwindle", "master", "monocle" }) do
	for _, intent in ipairs({ "automatic", "manual-on", "manual-off", "external-off" }) do
		workspaces, windows = {}, {}
		policy = dofile(arg[1])
		local ws = workspace("scrolling")
		local win = tiled(ws)
		events["config.props_refreshed"]()
		if intent == "manual-on" then policy.toggle_fullscreen(); policy.toggle_fullscreen()
		elseif intent == "manual-off" then policy.toggle_fullscreen()
		elseif intent == "external-off" then
			win.fullscreen = false
			events["window.fullscreen"](win)
			events["workspace.active"](ws) -- Must not undo a pending genuine off.
			assert(not win.fullscreen)
			settle()
		end
		local expected = intent == "automatic" or intent == "manual-on"
		switch_layout(ws, layout)
		assert(win.fullscreen == expected, layout .. ": teardown erased " .. intent)
		switch_layout(ws, "scrolling")
		settle() -- Round trip before the old teardown's one-shot may fire.
		assert(win.fullscreen == expected, layout .. ": round trip erased " .. intent)
		ws.autofullscreen = false; policy.refresh_autofullscreen()
		assert(win.fullscreen == (intent == "manual-on"), "automatic intent became explicit")
	end
end
print("native layout teardown: automatic/manual on/off and genuine external off round trips pass")

-- A newer explicit Icewine width/off choice wins even before the one-shot.
workspaces, windows = {}, {}
policy = dofile(arg[1])
local pending_ws = workspace("scrolling")
local pending_win = tiled(pending_ws)
events["config.props_refreshed"]()
pending_win.fullscreen = false; events["window.fullscreen"](pending_win)
policy.adjust_width(-0.1)
switch_layout(pending_ws, "master"); switch_layout(pending_ws, "scrolling")
settle()
assert(not pending_win.fullscreen and math.abs(pending_win.size.w / normal.width - 0.9) < 0.001,
	"layout recovery overwrote a newer explicit width/off choice")

-- Scrolling removeTarget is also used by move/float; do not poison those
-- existing callers while distinguishing layout teardown from a manual off.
workspaces, windows = {}, {}
policy = dofile(arg[1])
local move_from, move_to = workspace("scrolling"), workspace("scrolling")
local moved_on = tiled(move_from)
policy.toggle_fullscreen(); policy.toggle_fullscreen()
events["config.props_refreshed"]()
moved_on.fullscreen = false; events["window.fullscreen"](moved_on)
move_from.windows, move_to.windows, moved_on.workspace = {}, { moved_on }, move_to
events["window.move_to_workspace"](moved_on); settle()
assert(moved_on.fullscreen, "same-layout move lost explicit on during native removal")
for _, manual in ipairs({ false, true }) do
	workspaces, windows = {}, {}
	policy = dofile(arg[1])
	local ws = workspace("scrolling")
	local win = tiled(ws)
	if manual then policy.toggle_fullscreen(); policy.toggle_fullscreen() end
	policy.toggle_floating(); settle()
	assert(win.floating and win.fullscreen == manual, "native float teardown lost intent/exclusion")
end

workspaces, windows = {}, {}
policy = dofile(arg[1])
local switched, untouched = workspace("master"), workspace("scrolling")
local automatic = tiled(switched)
local floating = tiled(switched)
floating.floating = true
local manual_off, manual_on = tiled(switched), tiled(switched)
active = manual_off
policy.toggle_fullscreen(); policy.toggle_fullscreen()
active = manual_on
policy.toggle_fullscreen()
local other = tiled(untouched)
events["config.props_refreshed"]()
-- Leave an unrelated workspace deliberately out of policy, to detect accidental
-- global refresh. Its manual intent has not changed.
other.fullscreen = false
local splash = window(normal, 1, true)
splash.initial_title, splash.workspace = "Icewine Steam launch", switched
switched.windows[#switched.windows + 1] = splash
events["window.open"](splash)
local special = workspace("master")
special.special = true
local excluded = tiled(special)
events["config.props_refreshed"]()
active = manual_on
for _, layout in ipairs({ "scrolling", "dwindle", "monocle", "master", "scrolling" }) do
	switched.tiled_layout = layout
	events["config.props_refreshed"]()
	assert(not floating.fullscreen and not excluded.fullscreen and splash.fullscreen, "layout change broke exclusions")
	assert(not manual_off.fullscreen and manual_on.fullscreen, "layout change erased manual intent")
	assert(not other.fullscreen and active == manual_on, "layout change affected unrelated workspace/focus")
end
local before = focuses
events["config.props_refreshed"]()
assert(focuses == before and not other.fullscreen, "unrelated property refresh reconciled windows")
-- Effective workspace override remains stronger than global on after switches.
switched.autofullscreen = false
switched.tiled_layout = "master"; events["config.props_refreshed"]()
switched.tiled_layout = "scrolling"; events["config.props_refreshed"]()
assert(not automatic.fullscreen and manual_on.fullscreen and not manual_off.fullscreen)
-- Empty workspaces, final coalesced choice, and source/destination moves.
local empty = workspace("scrolling")
events["config.props_refreshed"]()
empty.tiled_layout = "monocle"; empty.tiled_layout = "master"
events["config.props_refreshed"]()
switched.windows, empty.windows = { floating, manual_off, manual_on, splash }, { automatic }
automatic.workspace = empty
events["window.move_to_workspace"](automatic)
assert(automatic.fullscreen and not manual_off.fullscreen and manual_on.fullscreen)
-- Reload retains known automatic intent and explicit user choices.
events["config.reloaded"]()
empty.tiled_layout = "scrolling"; events["config.props_refreshed"]()
assert(automatic.fullscreen and not manual_off.fullscreen and manual_on.fullscreen)
print("layout switches: all pairs, manual intent, overrides, exclusions, focus, empty/coalesced changes and moves pass")

-- Returning a background workspace to scrolling restores its saved width while
-- the user remains on an empty workspace (there is no active window to restore).
workspaces, windows = {}, {}
policy = dofile(arg[1])
local blank, background = workspace("master"), workspace("scrolling")
local resized = window(wide, 1, false)
resized.workspace, background.windows = background, { resized }
events["window.open"](resized)
policy.adjust_width(0.2)
background.tiled_layout = "master"; events["config.props_refreshed"]()
resized.size.w = wide.width * 0.3
active, active_workspace = nil, blank
background.tiled_layout = "scrolling"; events["config.props_refreshed"]()
assert(math.abs(resized.size.w / wide.width - 0.7) < 0.001 and not resized.fullscreen)
assert(active == nil and active_workspace == blank, "background resize stole empty-workspace focus")
print("layout switches: saved scrolling width and empty-workspace focus pass")

-- Native focus clears the old fullscreen owner before publishing window.active.
workspaces, windows, setting = {}, {}, "on\n"
policy = dofile(arg[1])
local monocle = workspace("monocle")
local underneath, foreground = tiled(monocle), tiled(monocle)
local function native_monocle_focus(win)
	if active ~= win and active.fullscreen then
		active.fullscreen = false
		events["window.fullscreen"](active)
	end
	active, monocle.last_window = win, win
	events["window.active"](win)
	settle()
end
for _ = 1, 2 do
	native_monocle_focus(underneath)
	assert(underneath.fullscreen and not foreground.fullscreen, "monocle refocus lost automatic fullscreen")
	native_monocle_focus(foreground)
	assert(foreground.fullscreen and not underneath.fullscreen, "monocle return pinned native teardown as manual off")
end
events["window.close"](foreground)
foreground.mapped, foreground.fullscreen = false, false
native_monocle_focus(underneath)
assert(underneath.fullscreen, "monocle close did not fullscreen the app underneath")
-- A genuine external off with unchanged focus must still remain deliberate.
underneath.fullscreen = false
events["window.fullscreen"](underneath)
settle()
events["window.active"](underneath)
assert(not underneath.fullscreen, "monocle genuine external off was ignored")
-- A setting change during deferred focus handling must not become manual intent.
workspaces, windows = {}, {}
policy = dofile(arg[1])
local pending_monocle = tiled(workspace("monocle"))
pending_monocle.fullscreen = false
events["window.fullscreen"](pending_monocle)
setting = "off\n"; policy.refresh_autofullscreen(); settle()
setting = "on\n"; policy.refresh_autofullscreen()
assert(pending_monocle.fullscreen, "monocle setting change pinned a deferred off")
print("monocle native focus: repeated switches, close-to-underneath and deliberate off pass")

-- Every layout distinguishes stable external off from native layout teardown.
for _, layout in ipairs({ "scrolling", "dwindle", "master", "monocle" }) do
	workspaces, windows, setting = {}, {}, "on\n"
	policy = dofile(arg[1])
	local ws = workspace(layout)
	local win = tiled(ws)
	win.fullscreen = false
	events["window.fullscreen"](win)
	events["workspace.active"](ws)
	assert(not win.fullscreen, layout .. ": pending external off was undone")
	settle()
	policy.refresh_autofullscreen()
	assert(not win.fullscreen, layout .. ": stable external off lost intent")

	workspaces, windows = {}, {}
	policy = dofile(arg[1])
	ws = workspace(layout)
	win = tiled(ws)
	win.fullscreen = false
	events["window.fullscreen"](win)
	ws.tiled_layout = layout == "master" and "dwindle" or "master"
	events["config.props_refreshed"]()
	settle()
	assert(win.fullscreen, layout .. ": native teardown became explicit off")
end
-- Known intent survives reload; an unknown existing window is still adopted.
workspaces, windows, setting = {}, {}, "on\n"
policy = dofile(arg[1])
local reload_ws = workspace("dwindle")
local reload_auto = tiled(reload_ws)
events["config.reloaded"]()
local reload_other = tiled(reload_ws)
assert(not reload_auto.fullscreen and not reload_other.fullscreen, "reload pinned automatic singleton fullscreen")
policy.toggle_fullscreen()
events["config.reloaded"]()
setting = "off\n"; policy.refresh_autofullscreen()
assert(reload_other.fullscreen, "reload lost explicit fullscreen")
active = reload_auto
policy.toggle_fullscreen(); policy.toggle_fullscreen()
events["config.reloaded"]()
setting = "on\n"; policy.refresh_autofullscreen()
assert(not reload_auto.fullscreen, "reload lost explicit off")
-- A stale one-shot must not replace a newer explicit command or a closed window.
for _, layout in ipairs({ "scrolling", "dwindle", "master", "monocle" }) do
	workspaces, windows = {}, {}
	policy = dofile(arg[1])
	local win = tiled(workspace(layout))
	win.fullscreen = false; events["window.fullscreen"](win)
	policy.toggle_fullscreen(); settle()
	assert(win.fullscreen, layout .. ": delayed off overwrote newer explicit on")
	win.fullscreen = false; events["window.fullscreen"](win)
	events["window.close"](win); win.mapped = false
	settle()
	assert(not win.fullscreen, layout .. ": delayed off touched closed window")
end
-- Hyprland exposes 0=normal, 1=maximized and 2=fullscreen.
workspaces, windows, setting = {}, {}, "on\n"
policy = dofile(arg[1])
local maximized = window(normal, 1, 1)
events["window.open"](maximized)
assert(maximized.fullscreen == true, "maximized was mistaken for fullscreen")
local native_fullscreen = window(wide, 1, 2)
events["window.open"](native_fullscreen)
assert(native_fullscreen.fullscreen == 2, "native fullscreen was not recognized")
print("shared fullscreen model: external off, teardown, reload, stale callbacks and native modes pass")
