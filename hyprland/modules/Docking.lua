return function(panel, lid_paths)
	panel = panel or {}
	local internal = panel.output
	local function read_lid()
		if not internal then return end
		for _, path in ipairs(lid_paths or {
			"/proc/acpi/button/lid/LID/state",
			"/proc/acpi/button/lid/LID0/state",
		}) do
			local file = io.open(path)
			if file then
				local contents = file:read("a")
				file:close()
				local state = contents and contents:match("state:%s*(%a+)")
				if state == "open" or state == "closed" then return state end
			end
		end
	end
	local function internal_monitor(enabled)
		-- A disabled panel is absent from queries; its host identity still restores it.
		return enabled and internal or nil
	end
	local function manage_workspaces(panel, externals)
		table.sort(externals, function(a, b)
			local ax, bx = a.x or 0, b.x or 0
			return ax == bx and a.name < b.name or ax < bx
		end)
		local targets = {}
		for index = 1, math.min(2, #externals) do targets[index] = externals[index].name end
		if panel then targets[#targets + 1] = panel end
		if #targets == 0 then return end
		local counts = #targets == 3 and {4, 4, 2}
			or #targets == 2 and (panel and {8, 2} or {5, 5}) or {10}
		local id = 0
		for index, target in ipairs(targets) do
			for offset = 1, counts[index] do
				id = id + 1
				hl.workspace_rule({
					workspace = tostring(id), monitor = target, persistent = true,
					default = offset == 1,
				})
			end
		end
	end
	local panel_enabled -- Requested state; monitor refresh is deferred.
	local function reconcile()
		local enabled = read_lid() ~= "closed"
		local desired_panel = internal_monitor(enabled)
		local externals = {}
		for _, monitor in ipairs(hl.get_monitors()) do
			if monitor.name ~= internal and monitor.name ~= "FALLBACK" then
				externals[#externals + 1] = monitor
			end
		end
		if internal and panel_enabled ~= enabled then
			panel_enabled = enabled
			if enabled then panel.disabled = false end
			hl.monitor(enabled and panel or { output = internal, disabled = true })
		end
		manage_workspaces(desired_panel, externals)
	end

	hl.on("monitor.added", reconcile)
	hl.on("monitor.removed", reconcile)
	if read_lid() then hl.bind("switch:Lid Switch", reconcile, { locked = true }) end
	reconcile()
end
