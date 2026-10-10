-- Run: lua hyprland/tests/steam.lua
local launches, guide = 0, nil
local radialOptions
local touchpad = {}
hl = {
	monitor=function() end, env=function() end, window_rule=function() end,
	config=function(config)
		for key, value in pairs(config.input and config.input.touchpad or {}) do
			touchpad[key] = value
		end
	end,
	bind=function(key, callback, options)
		if key == "F17" then guide = callback end
		if key == "F14" then radialOptions = options end
	end,
	dsp={exec_cmd=function() end, global=function() end, focus=function(request) return request end},
	exec_cmd=function(command)
		assert(command == "qs ipc call gameLauncher launchSteamGamescope")
		launches = launches + 1
	end,
}
dofile("hyprland/modules/Baseline.lua")
assert(touchpad.natural_scroll and touchpad.disable_while_typing and touchpad.tap_to_click)
assert(touchpad.scroll_factor == 1.0 and touchpad.middle_button_emulation)
local host = dofile("hyprland/deck/Deck.lua")
assert(touchpad.natural_scroll and touchpad.tap_to_click and not touchpad.disable_while_typing,
	"Deck must inherit shared touchpad defaults while retaining its typing exception")
assert(radialOptions.transparent and radialOptions.ignore_mods,
	"R5 release must survive intervening clicks and modifier changes")
assert(guide == host.focus_or_start_gamescope)
host.focus_or_start_gamescope()
guide()
assert(launches == 2) -- Quickshell owns autostart, focus, launch deduplication and splash state.
print("Deck Steam: Guide and shared Quickshell launch path checks pass")
