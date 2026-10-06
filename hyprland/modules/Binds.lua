-- All keybindings and mouse drag binds.
-- Lid switches and display calibration remain in host hardware modules.

local mainMod  = "SUPER"
local apps     = require("icewine.modules.DefaultApps")
local windows  = require("icewine.modules.WindowPolicy")

local function layout()
	local ws = hl.get_active_special_workspace() or hl.get_active_workspace()
	return ws and ws.tiled_layout
end

local function focus(direction)
	if layout() == "scrolling" and (direction == "l" or direction == "r") then
		hl.dispatch(hl.dsp.layout("focus " .. direction))
	elseif layout() == "monocle" then
		hl.dispatch(hl.dsp.window.cycle_next({ next = direction == "r" or direction == "d", tiled = true }))
	else
		hl.dispatch(hl.dsp.focus({ direction = direction }))
	end
end

local function swap(direction)
	if layout() == "scrolling" and (direction == "l" or direction == "r") then
		hl.dispatch(hl.dsp.layout("swapcol " .. direction))
	elseif layout() ~= "monocle" then
		hl.dispatch(hl.dsp.window.swap({ direction = direction }))
	end -- Monocle has no native directional reordering of its hidden stack.
end

local function resize(direction)
	if layout() == "scrolling" and (direction == "l" or direction == "r") then
		windows.adjust_width(direction == "r" and 0.05 or -0.05)
	else
		hl.dispatch(hl.dsp.window.resize({
			x = direction == "r" and 100 or direction == "l" and -100 or 0,
			y = direction == "d" and 100 or direction == "u" and -100 or 0,
			relative = true,
		})) -- Monocle's native resize operation is a no-op.
	end
end

local function topbar(action)
	return hl.dsp.exec_cmd("qs ipc call topbar " .. action)
end

local function populated_workspace_edge(kind)
	local selected, wrapped
	local active = kind == "next" and hl.get_active_workspace()

	for _, ws in ipairs(hl.get_workspaces()) do
		if not ws.special and ws.windows and ws.windows > 0 then
			if active and ws.id <= active.id then
				if not wrapped or ws.id < wrapped.id then wrapped = ws end
			elseif not selected
				or (kind ~= "last" and ws.id < selected.id)
				or (kind == "last" and ws.id > selected.id)
			then
				selected = ws
			end
		end
	end

	return selected or wrapped
end

local function focus_populated_workspace_edge(kind)
	local ws = populated_workspace_edge(kind)
	if ws then hl.dispatch(hl.dsp.focus({ workspace = ws })) end
end

local function move_to_populated_workspace_edge(kind)
	local ws = populated_workspace_edge(kind)
	if ws then hl.dispatch(hl.dsp.window.move({ workspace = ws })) end
end

-- Application launchers
hl.bind(mainMod .. " + SPACE",  hl.dsp.exec_cmd(apps.terminal))
hl.bind(mainMod .. " + RETURN", topbar("launcher"))
hl.bind(mainMod .. " + E",      hl.dsp.exec_cmd(apps.file_manager))
hl.bind(mainMod .. " + B",      hl.dsp.exec_cmd(apps.browser))
hl.bind(mainMod .. " + L",      hl.dsp.exec_cmd(apps.lock))
-- Lua global dispatchers need transparency so intervening clicks cannot shadow release.
hl.bind(mainMod .. " + grave", hl.dsp.global("quickshell:topbarHold"), { transparent = true, dont_inhibit = true, submap_universal = true })
-- Either release order ends the chord; ordinary key releases still reach apps.
for _, key in ipairs({ "SUPER_L", "SUPER_R" }) do
	hl.bind(key, hl.dsp.global("quickshell:topbarModifier"), {
		transparent = true, ignore_mods = true, non_consuming = true,
		dont_inhibit = true, submap_universal = true,
	})
end

-- Native controls; their advanced actions retain the terminal TUIs.
hl.bind(mainMod .. " + SHIFT + B", topbar("bluetooth"))
hl.bind(mainMod .. " + SHIFT + N", topbar("network"))
hl.bind(mainMod .. " + SHIFT + A", topbar("audio"))
hl.bind(mainMod .. " + SHIFT + J", topbar("battery"))
hl.bind(mainMod .. " + SHIFT + P", topbar("performance"))

-- Session control
hl.bind(mainMod .. " + SHIFT + L", hl.dsp.exec_cmd("command -v hyprshutdown >/dev/null 2>&1 && hyprshutdown || uwsm stop"))
hl.bind(mainMod .. " + CTRL + R",  hl.dsp.exec_cmd("hyprctl reload"))
hl.bind(mainMod .. " + SHIFT + W", hl.dsp.dpms({ action = "on" })) -- DPMS-wake bandaid (old `dpms on` syntax errors under Hyprland 0.55)

-- Window management
hl.bind(mainMod .. " + Q", hl.dsp.window.close())
hl.bind(mainMod .. " + V", windows.toggle_floating)
hl.bind(mainMod .. " + P", hl.dsp.window.pseudo())
hl.bind(mainMod .. " + J", function()
	if layout() == "scrolling" then hl.dispatch(hl.dsp.layout("consume_or_expel next")) end
end)
hl.bind(mainMod .. " + F", windows.toggle_fullscreen)
hl.bind(mainMod .. " + M", windows.toggle_width)

-- Screenshot menu: monitor, region or window.
hl.bind(mainMod .. " + Print", topbar("screenshot"))

-- Resolve the active layout at use time, including native runtime changes.
for key, direction in pairs({ left = "l", right = "r", up = "u", down = "d" }) do
	hl.bind(mainMod .. " + " .. key, function() focus(direction) end)
	hl.bind(mainMod .. " + SHIFT + " .. key, function() swap(direction) end)
	hl.bind(mainMod .. " + CTRL + " .. key, function() resize(direction) end)
end

-- Workspace switch and move-window-to-workspace, 1-10 (0 selects 10).
for i = 1, 10 do
	hl.bind(mainMod .. " + " .. (i % 10),         hl.dsp.focus({ workspace = i }))
	hl.bind(mainMod .. " + SHIFT + " .. (i % 10), hl.dsp.window.move({ workspace = i }))
end

-- Relative workspace navigation
hl.bind(mainMod .. " + Prior",         hl.dsp.focus({ workspace = "r-1" }))
hl.bind(mainMod .. " + Next",          hl.dsp.focus({ workspace = "r+1" }))
hl.bind(mainMod .. " + SHIFT + Prior", hl.dsp.window.move({ workspace = "r-1" }))
hl.bind(mainMod .. " + SHIFT + Next",  hl.dsp.window.move({ workspace = "r+1" }))
hl.bind(mainMod .. " + TAB",           function() focus_populated_workspace_edge("next") end)
hl.bind(mainMod .. " + SHIFT + TAB",   function() move_to_populated_workspace_edge("next") end)
hl.bind(mainMod .. " + mouse_down",    function() focus("r") end)
hl.bind(mainMod .. " + mouse_up",      function() focus("l") end)

-- Jump to first/last populated normal workspace.
hl.bind(mainMod .. " + Home",         function() focus_populated_workspace_edge("first") end)
hl.bind(mainMod .. " + End",          function() focus_populated_workspace_edge("last") end)
hl.bind(mainMod .. " + SHIFT + Home", function() move_to_populated_workspace_edge("first") end)
hl.bind(mainMod .. " + SHIFT + End",  function() move_to_populated_workspace_edge("last") end)

-- ALT-Tab: cycle next + lift to top (no `bring_to_top` in the 0.55 API; use alter_zorder)
hl.bind("ALT + Tab", function()
	hl.dispatch(hl.dsp.window.cycle_next({}))
	hl.dispatch(hl.dsp.window.alter_zorder({ mode = "top" }))
end, { repeating = true })

-- Scratchpad

-- Mouse drag binds (LMB move, RMB resize)
local function supress_mouse_binds(enabled)
	assert(type(enabled) == "boolean", "enabled must be a boolean")
	hl.unbind(mainMod .. " + mouse:272")
	hl.unbind(mainMod .. " + mouse:273")
	if not enabled then
		hl.bind(mainMod .. " + mouse:272", hl.dsp.window.drag(),   { mouse = true })
		hl.bind(mainMod .. " + mouse:273", hl.dsp.window.resize(), { mouse = true })
	end
end
supress_mouse_binds(false)

-- Display zoom via Super+Shift+wheel; reset with Super+Shift+Z
hl.bind(mainMod .. " + SHIFT + mouse_down", function()
	hl.config({ cursor = { zoom_factor = (tonumber(hl.get_config("cursor.zoom_factor")) or 1) + 0.5 } })
end)
hl.bind(mainMod .. " + SHIFT + mouse_up", function()
	hl.config({ cursor = { zoom_factor = (tonumber(hl.get_config("cursor.zoom_factor")) or 1) - 0.5 } })
end)
hl.bind(mainMod .. " + SHIFT + Z", function()
	hl.config({ cursor = { zoom_factor = 1 } })
end)

-- Audio (universal, present on any keyboard with media keys)
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+ && wpctl set-mute @DEFAULT_AUDIO_SINK@ 0"), { locked = true, repeating = true })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%- && wpctl set-mute @DEFAULT_AUDIO_SINK@ 0"),       { locked = true, repeating = true })
hl.bind("XF86AudioMute",        hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"),      { locked = true })
hl.bind("XF86AudioMicMute",     hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"),    { locked = true })

-- Media keys control the same player as the Quickshell panel.
hl.bind("XF86AudioNext",  topbar("mediaNext"),     { locked = true })
hl.bind("XF86AudioPause", topbar("mediaToggle"),   { locked = true })
hl.bind("XF86AudioPlay",  topbar("mediaToggle"),   { locked = true })
hl.bind("XF86AudioPrev",  topbar("mediaPrevious"), { locked = true })

-- Brightness keys and three-finger desktop navigation.
hl.bind("XF86MonBrightnessUp",   hl.dsp.exec_cmd("icewine-monitor-brightness focused +5"), { locked = true, repeating = true })
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("icewine-monitor-brightness focused -5"), { locked = true, repeating = true })

hl.gesture({ fingers = 3, direction = "left", action = function()
	focus("r")
end })
hl.gesture({ fingers = 3, direction = "right", action = function()
	focus("l")
end })
hl.gesture({ fingers = 3, direction = "up", action = function()
	hl.dispatch(hl.dsp.focus({ workspace = "r+1" }))
end })
hl.gesture({ fingers = 3, direction = "down", action = function()
	hl.dispatch(hl.dsp.focus({ workspace = "r-1" }))
end })

return { supress_mouse_binds = supress_mouse_binds }
