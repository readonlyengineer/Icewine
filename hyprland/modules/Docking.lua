return function(internal)
	local function sync()
		local panel = hl.get_monitor(internal)
		local externals = {}
		for _, monitor in ipairs(hl.get_monitors()) do
			if monitor.name ~= internal and monitor.name ~= "FALLBACK" then
				externals[#externals + 1] = monitor
			end
		end
		table.sort(externals, function(a, b)
			local ax, bx = a.x or 0, b.x or 0
			return ax == bx and a.name < b.name or ax < bx
		end)
		if #externals == 0 and not panel then return end

		local previous
		for id = 1, 10 do
			local target
			if #externals >= 2 then
				if panel then
					target = id <= 4 and externals[1] or id <= 8 and externals[2] or panel
				else
					target = id <= 5 and externals[1] or externals[2]
				end
			elseif #externals == 1 then
				target = panel and (id <= 8 and externals[1] or panel) or externals[1]
			else
				target = panel
			end
			hl.workspace_rule({
				workspace = tostring(id), monitor = target.name, persistent = true,
				default = target ~= previous,
			})
			previous = target
		end
	end

	hl.on("monitor.added", sync)
	hl.on("monitor.removed", sync)
	sync()
end
