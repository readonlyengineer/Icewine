-- Icewine handheld bindings and session behaviour.

hl.config({
	cursor = {
		enable_hyprcursor = false,
		inactive_timeout = 3,
	},

	xwayland = {
		force_zero_scaling = true,
	},

	input = {
		kb_options = "fkeys:basic_13-24", -- Keep rear-button F13–F16 as function-key symbols.
		touchpad = { disable_while_typing = false },
	},
})

-- One shell owner suppresses these while the radial is open. Window cycling
-- otherwise stays in the current workspace, without jumping to the game tape.
hl.bind("F13", hl.dsp.exec_cmd("qs ipc call deckOverlay cycle r"), { dont_inhibit = true }) -- R4
hl.bind("F15", hl.dsp.exec_cmd("qs ipc call deckOverlay cycle l"), { dont_inhibit = true }) -- L4
-- R5 is a hold gesture: press reveals the dial and release dismisses it.
hl.bind("F14", hl.dsp.global("quickshell:deckRadial"), {
	transparent = true, dont_inhibit = true, ignore_mods = true, submap_universal = true,
}) -- R5
hl.bind("F16", hl.dsp.exec_cmd("icewine-keyboard-toggle"), {
	dont_inhibit = true, ignore_mods = true, submap_universal = true,
}) -- L5

local function focus_or_start_gamescope()
	hl.exec_cmd("qs ipc call gameLauncher launchSteamGamescope")
end

hl.bind("F17", focus_or_start_gamescope, {
	dont_inhibit = true, ignore_mods = true, submap_universal = true,
}) -- Steam/Guide outside Gamescope

return { focus_or_start_gamescope = focus_or_start_gamescope }
