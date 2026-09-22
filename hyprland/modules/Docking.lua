return function(internal)
	local function sync()
		local panel = hl.get_monitor(internal)
		local primary = panel
		-- First external wins; add an output preference if multiple need ordering.
		for _, monitor in ipairs(hl.get_monitors()) do
			if monitor.name ~= internal and monitor.name ~= "FALLBACK" then
				primary = monitor
				break
			end
		end
		if not primary then return end

		for id = 1, 10 do
			local target = id == 10 and panel or primary
			hl.workspace_rule({
				workspace = tostring(id), monitor = target.name, persistent = true,
				default = id == 1 or (id == 10 and target.name ~= primary.name),
			})
		end
	end

	hl.on("monitor.added", sync)
	hl.on("monitor.removed", sync)
	sync()
end
