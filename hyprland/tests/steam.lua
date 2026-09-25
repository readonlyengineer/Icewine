-- Run: lua hyprland/tests/steam.lua
local launches, guide = 0, nil
local radialOptions
hl = {
	monitor=function() end, config=function() end,
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
local host = dofile("hyprland/deck/Deck.lua")
assert(radialOptions.transparent and radialOptions.ignore_mods,
	"R5 release must survive intervening clicks and modifier changes")
assert(guide == host.focus_or_start_gamescope)
host.focus_or_start_gamescope()
guide()
assert(launches == 2) -- Quickshell owns autostart, focus, launch deduplication and splash state.
print("Deck Steam: Guide and shared Quickshell launch path checks pass")
