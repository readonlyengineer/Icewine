-- Run: lua hyprland/tests/steam.lua
local windows, focused, launches, guide, boot = {}, nil, 0, nil, nil
local radialOptions
hl = {
	monitor=function() end, config=function() end,
	bind=function(key, callback, options)
		if key == "F17" then guide = callback end
		if key == "F14" then radialOptions = options end
	end,
	on=function(event, callback) assert(event == "hyprland.start"); boot = callback end,
	get_windows=function() return windows end,
	dsp={exec_cmd=function() end, global=function() end, focus=function(request) return request end},
	dispatch=function(request) focused = request.window end,
	exec_cmd=function(command)
		assert(command == "uwsm app -- icewine-steam-gamescope")
		launches = launches + 1
	end,
}
local host = dofile("hyprland/deck/Deck.lua")
assert(radialOptions.transparent and radialOptions.ignore_mods,
	"R5 release must survive intervening clicks and modifier changes")
package.loaded["modules.Deck"] = host
dofile("hyprland/deck/Autostart.lua")
assert(launches == 0) -- Config loading/reloading does not start Steam.
assert(guide == host.focus_or_start_gamescope)
boot()
assert(launches == 1) -- Start at session startup.
local game = {class="gamescope"}
windows = {{class="kitty"}, game}
host.focus_or_start_gamescope()
guide()
assert(focused == game and launches == 1) -- Existing Gamescope: focus, never relaunch.
windows = {}
host.focus_or_start_gamescope()
assert(launches == 2) -- Explicit launch after closing Steam.
print("Deck Steam: boot, focus, Guide and explicit relaunch checks pass")
