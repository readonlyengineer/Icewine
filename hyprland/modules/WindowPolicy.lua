-- Monitor defaults and per-window user intent for the scrolling layout.

local M = {}

local epsilon = 0.02
local states = {}
local pending_fullscreen = {}
local configured_default

local function same_number(a, b)
	return math.abs((a or 0) - (b or 0)) < epsilon
end

local function width_of(vec)
	if type(vec) ~= "table" then return nil end
	return vec.w or vec.x or vec[1]
end

local function key_for(win)
	return win and tostring(win.address) or nil
end

local function fullscreen_of(win)
	if not win then return false end
	if win.fullscreen == true then return true end
	return (tonumber(win.fullscreen) or 0) > 0
end

local function monitor_for(win)
	if win and win.monitor then return win.monitor end

	local ws = hl.get_active_special_workspace() or hl.get_active_workspace()
	if ws and ws.monitor then return ws.monitor end

	return hl.get_active_monitor()
end

local function default_width_for_monitor(mon)
	if not mon or not mon.width or not mon.height or mon.height == 0 then return 1.0 end
	return mon.width / mon.height >= 32 / 9 and 0.5 or 1.0
end

local function monitor_opens_fullscreen(mon)
	if not mon or (mon.width or 0) <= 0 or (mon.height or 0) <= 0 then return false end
	return same_number(default_width_for_monitor(mon), 1.0)
end

local function default_width(win)
	return default_width_for_monitor(monitor_for(win))
end

local function current_width(win)
	local mon = monitor_for(win)
	local width = width_of(win and win.size)
	if not mon or not mon.width or mon.width == 0 or not width then return nil end
	return width / mon.width
end

local function state_for(win)
	local key = key_for(win)
	if not key then return nil end
	if not states[key] then states[key] = {} end
	return states[key]
end

local function is_policy_window(win)
	if not win or win.hidden then return false end
	if not win.workspace or win.workspace.special then return false end
	return not win.workspace.tiled_layout or win.workspace.tiled_layout == "scrolling"
end

local function is_resizable(win)
	return is_policy_window(win) and not win.floating
end

local function opens_fullscreen_by_default(win)
	local mon = monitor_for(win)
	return is_resizable(win) and monitor_opens_fullscreen(mon)
end

local function target_for(state, fallback_width)
	local width = state.width or fallback_width
	local fullscreen = state.fullscreen
	if fullscreen == nil then fullscreen = same_number(fallback_width, 1.0) end

	return width, fullscreen
end

local function window_target(win)
	return target_for(state_for(win), default_width(win))
end

local function intended_width(win, state)
	if state.width then return state.width end

	local fallback = default_width(win)
	local measured = not fullscreen_of(win) and current_width(win) or nil
	if measured and not same_number(measured, fallback) then return measured end
	return fallback
end

local function adjusted_width(width, delta)
	return math.max(0.05, width + delta)
end

local function wants_fullscreen(win)
	local _, fullscreen = target_for(state_for(win), default_width(win))
	return fullscreen
end

local function toggled_fullscreen(state, fallback_width)
	local _, fullscreen = target_for(state, fallback_width)
	return not fullscreen
end

local function set_fullscreen(win, fullscreen)
	local key = key_for(win)
	if not key or fullscreen_of(win) == fullscreen then return false end

	pending_fullscreen[key] = fullscreen
	hl.dispatch(hl.dsp.window.fullscreen({
		action       = fullscreen and "set" or "unset",
		mode         = "fullscreen",
		layout_aware = true,
		window       = win,
	}))
	return true
end

local function config_bool(name)
	local value = hl.get_config(name)
	return value == true or value == 1 or tostring(value) == "true" or tostring(value) == "1"
end

local function focus_window(win)
	if not win or win.hidden or hl.get_active_window() == win then return false end
	hl.dispatch(hl.dsp.focus({ window = win }))
	return true
end

local function with_window_focus(win, fn)
	local active = hl.get_active_window()
	if active == win then
		fn()
		return
	end

	local animations = config_bool("animations.enabled")
	local no_warps = config_bool("cursor.no_warps")
	if animations then hl.config({ animations = { enabled = false } }) end
	if not no_warps then hl.config({ cursor = { no_warps = true } }) end

	local ok, err = xpcall(function()
		hl.dispatch(hl.dsp.focus({ window = win }))
		fn()
	end, function(trace) return tostring(trace) end)

	focus_window(active)
	if animations then hl.config({ animations = { enabled = true } }) end
	if not no_warps then hl.config({ cursor = { no_warps = false } }) end
	if not ok then error(err) end
end

local function set_width(win, width)
	local measured = current_width(win)
	if measured and same_number(measured, width) then return false end

	with_window_focus(win, function()
		hl.dispatch(hl.dsp.layout("colresize " .. string.format("%.3f", width)))
	end)
	return true
end

local function apply_window(win)
	if not is_policy_window(win) then return false end

	local width, fullscreen = window_target(win)
	local was_fullscreen = fullscreen_of(win)
	local changed = false
	if was_fullscreen and not fullscreen then
		changed = set_fullscreen(win, false) or changed
		was_fullscreen = false
	end

	if not was_fullscreen and not win.floating then changed = set_width(win, width) or changed end
	if fullscreen then changed = set_fullscreen(win, true) or changed end
	return changed
end

local function sync_default_width(mon)
	local width = default_width_for_monitor(mon)
	if same_number(configured_default, width) then return end

	configured_default = width
	hl.config({ scrolling = { column_width = width } })
end

local function reconcile_workspace(ws)
	if not ws then return end

	local active = hl.get_active_window()
	local focused = active and active.workspace == ws and active or ws.last_window
	local changed = false
	for _, win in ipairs(hl.get_workspace_windows(ws)) do
		if is_policy_window(win) and (fullscreen_of(win) or wants_fullscreen(win)) then
			changed = apply_window(win) or changed
		end
	end

	if changed and focused and not focused.hidden then
		if not focus_window(focused) then
			hl.dispatch(hl.dsp.layout("fit_into_view"))
		end
	end
	focus_window(active)
end

local function reconcile_visible()
	for _, ws in ipairs(hl.get_workspaces()) do
		if ws.active then reconcile_workspace(ws) end
	end
end

local function adopt_existing_windows()
	states = {}
	pending_fullscreen = {}

	for _, win in ipairs(hl.get_windows()) do
		local state = state_for(win)
		if is_policy_window(win) then
			local measured = not fullscreen_of(win) and current_width(win) or nil
			if measured and not same_number(measured, default_width(win)) then
				state.width = measured
			end
			state.fullscreen = fullscreen_of(win)
		end
	end
end

function M.adjust_width(delta)
	local win = hl.get_active_window()
	if not is_resizable(win) then return end

	local state = state_for(win)
	state.width = adjusted_width(intended_width(win, state), delta)
	state.fullscreen = false
	apply_window(win)
end

function M.toggle_width()
	local win = hl.get_active_window()
	if not is_resizable(win) then return end

	local state = state_for(win)
	local fallback = default_width(win)
	if same_number(fallback, 1.0) then
		state.width = 1.0
	else
		local width = intended_width(win, state)
		state.width = width > (1.0 + fallback) / 2 and fallback or 1.0
		state.fullscreen = same_number(state.width, 1.0)
	end
	apply_window(win)
end

function M.toggle_fullscreen()
	local win = hl.get_active_window()
	if not win then return end
	if not is_policy_window(win) then
		hl.dispatch(hl.dsp.window.fullscreen({
			action = "toggle",
			mode = "fullscreen",
			layout_aware = true,
			window = win,
		}))
		return
	end

	local state = state_for(win)
	state.fullscreen = toggled_fullscreen(state, default_width(win))
	apply_window(win)
end

function M.toggle_floating()
	local win = hl.get_active_window()
	if not win then return end

	hl.dispatch(hl.dsp.window.float({ action = "toggle", window = win }))
	apply_window(win)
end

hl.on("hyprland.start", function()
	sync_default_width(hl.get_active_monitor())
end)

hl.on("config.reloaded", function()
	adopt_existing_windows()
	sync_default_width(hl.get_active_monitor())
end)

hl.on("monitor.focused", function(mon)
	sync_default_width(mon)
end)

hl.on("monitor.layout_changed", function()
	sync_default_width(hl.get_active_monitor())
	reconcile_visible()
end)

hl.on("workspace.active", function(ws)
	if ws and ws.monitor and ws.monitor.focused then sync_default_width(ws.monitor) end
	reconcile_workspace(ws)
end)

hl.on("window.open", function(win)
	local state = state_for(win)
	if win.floating then
		state.fullscreen = false
	elseif fullscreen_of(win) and not opens_fullscreen_by_default(win) then
		state.fullscreen = true
	end
	apply_window(win)
end)

hl.on("window.close", function(win)
	local key = key_for(win)
	if not key then return end
	states[key] = nil
	pending_fullscreen[key] = nil
end)

hl.on("window.move_to_workspace", function(win)
	apply_window(win)
end)

hl.on("window.fullscreen", function(win)
	local key = key_for(win)
	local state = key and states[key]
	if not state then return end

	local fullscreen = fullscreen_of(win)
	if pending_fullscreen[key] ~= nil then
		local expected = pending_fullscreen[key]
		pending_fullscreen[key] = nil
		if expected == fullscreen then return end
	end

	state.fullscreen = fullscreen
	if not fullscreen then apply_window(win) end
end)

return M
