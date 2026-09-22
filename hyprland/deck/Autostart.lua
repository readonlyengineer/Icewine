-- Icewine starts into the handheld shell; Terminal remains on the R5 dial.

hl.on("hyprland.start", function()
	require("modules.Deck").focus_or_start_gamescope()
end)
