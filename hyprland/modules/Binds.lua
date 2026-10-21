-- All keybindings and mouse drag binds.
-- Lid switches and display calibration remain in host hardware modules.

local apps     = require("icewine.modules.DefaultApps")
local windows  = require("icewine.modules.WindowPolicy")
local bindings = require("icewine.modules.Bindings")
local bind = bindings.bind

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
bind("terminal", hl.dsp.exec_cmd(apps.terminal))
bind("launcher", topbar("launcher"))
-- Toggle on chord release, after the opening key can no longer reach the overlay.
bind("switcher", hl.dsp.global("quickshell:windowSwitcher"))
bind("filemanager", hl.dsp.exec_cmd(apps.file_manager))
if apps.browser ~= "" then bind("browser", hl.dsp.exec_cmd(apps.browser)) end
bind("lock", hl.dsp.exec_cmd(apps.lock))
-- Lua global dispatchers need transparency so intervening clicks cannot shadow release.
bind("taskbar", hl.dsp.global("quickshell:topbarHold"))
-- Either release order ends the chord; ordinary key releases still reach apps.
local modifier_keys = { SUPER = { "SUPER_L", "SUPER_R" }, SHIFT = { "SHIFT_L", "SHIFT_R" },
    CTRL = { "Control_L", "Control_R" }, ALT = { "ALT_L", "ALT_R" } }
local opening_modifiers, taskbar_modifiers = {}, {}
for _, chord in pairs(bindings.values) do
    for modifier in chord:gmatch("([^+]+)+") do opening_modifiers[modifier] = true end
end
for modifier in bindings.values.taskbar:gmatch("([^+]+)+") do taskbar_modifiers[modifier] = true end
for modifier in pairs(opening_modifiers) do
    local action = taskbar_modifiers[modifier] and "topbarModifier" or "topbarOpeningModifier"
    for _, key in ipairs(assert(modifier_keys[modifier])) do
        hl.bind(key, hl.dsp.global("quickshell:" .. action), {
            description = "icewine:taskbar-modifier-" .. key:upper(),
            transparent = true, ignore_mods = true, non_consuming = true,
            dont_inhibit = true, submap_universal = true,
        })
    end
end

-- Native controls; their advanced actions retain the terminal TUIs.
bind("bluetooth", topbar("bluetooth"))
bind("network", topbar("network"))
bind("audio", topbar("audio"))
bind("layout", topbar("layout"))

-- Session control
bind("session_end", hl.dsp.exec_cmd("command -v hyprshutdown >/dev/null 2>&1 && hyprshutdown || uwsm stop"))
bind("reload",  hl.dsp.exec_cmd("hyprctl reload"))
bind("wake", hl.dsp.dpms({ action = "on" })) -- DPMS-wake bandaid (old `dpms on` syntax errors under Hyprland 0.55)

-- Window management
bind("close", hl.dsp.window.close())
bind("floating", windows.toggle_floating)
bind("power", topbar("battery"))
bind("join", function()
	if layout() == "scrolling" then hl.dispatch(hl.dsp.layout("consume_or_expel next")) end
end)
bind("fullscreen", windows.toggle_fullscreen)
bind("width", windows.toggle_width)

-- Gradia FULL capture via the shared enabled-state and instant shell handoff.
bind("screenshot", hl.dsp.exec_cmd("icewine screenshot"))

-- Resolve the active layout at use time, including native runtime changes.
for key, direction in pairs({ left = "l", right = "r", up = "u", down = "d" }) do
	bind("focus_" .. key, function() focus(direction) end)
	bind("swap_" .. key, function() swap(direction) end)
	bind("resize_" .. key, function() resize(direction) end)
end

-- Workspace switch and move-window-to-workspace, 1-10 (0 selects 10).
for i = 1, 10 do
	bind("workspace_" .. i,         hl.dsp.focus({ workspace = i }))
	bind("move_workspace_" .. i, hl.dsp.window.move({ workspace = i }))
end

-- Relative workspace navigation
bind("previous_workspace",         hl.dsp.focus({ workspace = "r-1" }))
bind("next_workspace",          hl.dsp.focus({ workspace = "r+1" }))
bind("move_previous", hl.dsp.window.move({ workspace = "r-1" }))
bind("move_next",  hl.dsp.window.move({ workspace = "r+1" }))
bind("populated",           function() focus_populated_workspace_edge("next") end)
bind("move_populated",   function() move_to_populated_workspace_edge("next") end)
bind("wheel_right",    function() focus("r") end)
bind("wheel_left",      function() focus("l") end)

-- Jump to first/last populated normal workspace.
bind("first_workspace",         function() focus_populated_workspace_edge("first") end)
bind("last_workspace",          function() focus_populated_workspace_edge("last") end)
bind("move_first", function() move_to_populated_workspace_edge("first") end)
bind("move_last",  function() move_to_populated_workspace_edge("last") end)

-- ALT-Tab: cycle next + lift to top (no `bring_to_top` in the 0.55 API; use alter_zorder)
bind("cycle", function()
	hl.dispatch(hl.dsp.window.cycle_next({}))
	hl.dispatch(hl.dsp.window.alter_zorder({ mode = "top" }))
end)

-- Scratchpad

-- Saved managed chords take precedence over the corresponding preview direction.
local configured = {}
for _, chord in pairs(bindings.values) do configured[chord] = true end
local preview_tabs = {}
if not configured.TAB then
	table.insert(preview_tabs, hl.bind("Tab", hl.dsp.global("quickshell:previewTab"), { transparent = true, description = "icewine:preview-tab" }))
end
if not configured["SHIFT+TAB"] then
	table.insert(preview_tabs, hl.bind("SHIFT + Tab", hl.dsp.global("quickshell:previewBacktab"), { transparent = true, description = "icewine:preview-backtab" }))
end
local function set_preview_tabs(enabled)
	assert(type(enabled) == "boolean", "enabled must be a boolean")
	for _, binding in ipairs(preview_tabs) do binding:set_enabled(enabled) end
end
set_preview_tabs(false)

-- Mouse drag binds (LMB move, RMB resize)
local function supress_mouse_binds(enabled)
	assert(type(enabled) == "boolean", "enabled must be a boolean")
	hl.unbind(bindings.chord("drag_move"))
	hl.unbind(bindings.chord("drag_resize"))
	if not enabled then
		bind("drag_move", hl.dsp.window.drag())
		bind("drag_resize", hl.dsp.window.resize())
	end
end
supress_mouse_binds(false)

-- Display zoom via Super+Shift+wheel; reset with Super+Shift+Z
bind("zoom_in", function()
	hl.config({ cursor = { zoom_factor = (tonumber(hl.get_config("cursor.zoom_factor")) or 1) + 0.5 } })
end)
bind("zoom_out", function()
	hl.config({ cursor = { zoom_factor = (tonumber(hl.get_config("cursor.zoom_factor")) or 1) - 0.5 } })
end)
bind("zoom_reset", function()
	hl.config({ cursor = { zoom_factor = 1 } })
end)

-- Audio (universal, present on any keyboard with media keys)
bind("volume_up", hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+ && wpctl set-mute @DEFAULT_AUDIO_SINK@ 0"))
bind("volume_down", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%- && wpctl set-mute @DEFAULT_AUDIO_SINK@ 0"))
bind("mute",        hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"))
bind("mic_mute",     hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"))

-- Media keys control the same player as the Quickshell panel.
bind("media_next",  topbar("mediaNext"))
bind("media_pause", topbar("mediaToggle"))
bind("media_play",  topbar("mediaToggle"))
bind("media_previous",  topbar("mediaPrevious"))

-- Brightness keys and three-finger desktop navigation.
bind("brightness_up",   hl.dsp.exec_cmd("icewine-monitor-brightness focused +5"))
bind("brightness_down", hl.dsp.exec_cmd("icewine-monitor-brightness focused -5"))

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

return { supress_mouse_binds = supress_mouse_binds, set_preview_tabs = set_preview_tabs }
