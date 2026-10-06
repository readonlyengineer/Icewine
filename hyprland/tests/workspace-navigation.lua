-- Run: lua hyprland/tests/workspace-navigation.lua hyprland/modules/Binds.lua
local stub = setmetatable({}, {
	__index = function(self) return self end,
	__call = function(self, request) return request or self end,
})
package.loaded["icewine.modules.DefaultApps"] = dofile("hyprland/modules/DefaultApps.lua")
package.loaded["icewine.modules.WindowPolicy"] = stub
local binds, workspaces, active, target = {}, {}, nil, nil
local options, gestures, lastDispatch = {}, {}, nil
hl = {
	dsp = stub,
	gesture = function(gesture)
		assert(gesture.fingers == 3 and not gestures[gesture.direction])
		gestures[gesture.direction] = gesture.action
	end,
	bind = function(key, callback, opts) binds[key], options[key] = callback, opts or {} end,
	unbind = function(key) binds[key] = nil end,
	get_workspaces = function() return workspaces end,
	get_active_workspace = function() return active end,
	dispatch = function(request)
		lastDispatch = request
		if type(request) == "table" and type(request.workspace) == "table" then
			target = request.workspace.id
		end
	end,
}
local module = dofile(assert(arg[1], "Pass the Binds.lua path"))
assert(binds["SUPER + L"] == "qs ipc call session lock")
for key, command in pairs({
	XF86AudioRaiseVolume = "wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+ && wpctl set-mute @DEFAULT_AUDIO_SINK@ 0",
	XF86AudioLowerVolume = "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%- && wpctl set-mute @DEFAULT_AUDIO_SINK@ 0",
	XF86MonBrightnessUp = "icewine-monitor-brightness focused +5",
	XF86MonBrightnessDown = "icewine-monitor-brightness focused -5",
}) do
	assert(binds[key] == command and options[key].locked and options[key].repeating)
end
assert(binds.XF86AudioMute == "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"
	and options.XF86AudioMute.locked and not options.XF86AudioMute.repeating)
for direction, command in pairs({ left = "focus r", right = "focus l" }) do
	gestures[direction]()
	assert(lastDispatch == command)
end
for direction, workspace in pairs({ up = "r+1", down = "r-1" }) do
	gestures[direction]()
	assert(lastDispatch.workspace == workspace)
end
assert(binds["SUPER + SHIFT + P"] == "qs ipc call topbar performance")
assert(binds["SUPER + Print"] == "qs ipc call topbar screenshot")
-- Hyprland shadows Lua bindings after intervening input unless transparent.
for _, key in ipairs({"SUPER + grave", "SUPER_L", "SUPER_R"}) do
	assert(options[key].transparent, key .. ": clicks must not suppress the summon-key release")
end
for _, key in ipairs({"SUPER_L", "SUPER_R"}) do
	assert(options[key].ignore_mods and options[key].non_consuming,
		key .. ": either chord release order must work without swallowing application input")
end
local keyboardBinds = {}
for key, callback in pairs(binds) do
	if key ~= "SUPER + mouse:272" and key ~= "SUPER + mouse:273" then
		keyboardBinds[key] = callback
	end
end
for _, suppressed in ipairs({true, true, false, false, true, false}) do
	module.supress_mouse_binds(suppressed)
	assert((binds["SUPER + mouse:272"] ~= nil) == not suppressed)
	assert((binds["SUPER + mouse:273"] ~= nil) == not suppressed)
	for key, callback in pairs(keyboardBinds) do
		assert(binds[key] == callback, "mouse suppression changed " .. key)
	end
end
assert(not pcall(module.supress_mouse_binds, "false"))
assert(binds["SUPER + mouse:272"] and binds["SUPER + mouse:273"])
print("mouse suppression: repeat suppression/restoration, keyboard preservation and input validation pass")
for id = 10, 1, -1 do -- Deliberately unsorted, with persistent empty workspaces.
	workspaces[#workspaces + 1] = {id=id, windows=(id == 2 or id == 7 or id == 10) and 1 or 0}
end
workspaces[#workspaces + 1] = {id=20, windows=1, special=true}
local function check(key, current, expected)
	active, target = {id=current}, nil
	binds["SUPER + " .. key]()
	assert(target == expected, key .. ": unexpected destination from " .. current)
end
for _, key in ipairs({"TAB", "SHIFT + TAB"}) do
	check(key, 2, 7)
	check(key, 7, 10)
	check(key, 10, 2) -- Wraparound skips the special workspace.
	check(key, 4, 7) -- Start from an empty workspace.
	check(key, 1, 2)
end
for _, key in ipairs({"Home", "SHIFT + Home"}) do check(key, 7, 2) end
for _, key in ipairs({"End", "SHIFT + End"}) do check(key, 7, 10) end
workspaces = {{id=7, windows=1}, {id=10, windows=0}}
check("TAB", 7, 7) -- A single populated workspace stays selected.
check("SHIFT + TAB", 10, 7)
workspaces = {{id=1, windows=0}, {id=2}, {id=20, windows=1, special=true}}
for _, key in ipairs({"TAB", "SHIFT + TAB", "Home", "End", "SHIFT + Home", "SHIFT + End"}) do
	check(key, 1, nil) -- No populated normal workspace: do nothing.
end
print("workspace navigation: skip-empty, wraparound, move, first/last and empty-session checks pass")
