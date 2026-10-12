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
	local function saved_rules()
		local path = package.searchpath("hyprmon", package.path)
		if not path then return {} end
		local rules = {}
		-- Ponytail: capture only generated hl.monitor calls; custom Lua needs a native rule API.
		local chunk = loadfile(path, "t", { hl = { monitor = function(spec)
			assert(type(spec) == "table" and type(spec.output) == "string")
			rules[spec.output] = spec
		end } })
		return chunk and pcall(chunk) and rules or {}
	end
	local function saved_for(rules, monitor)
		return rules[monitor.name] or monitor.description and rules["desc:" .. monitor.description]
	end
	local description
	local function panel_rule(rules)
		local rule = {}
		for key, value in pairs(panel) do rule[key] = value end
		local saved = saved_for(rules, {name=internal, description=description})
		if saved and not saved.disabled and type(saved.mode) == "string"
			and saved.mode:match("^%d+x%d+@%d+%.?%d*$")
			and type(saved.position) == "string" and saved.position:match("^%-?%d+x%-?%d+$")
			and type(saved.scale) == "number"
			and saved.scale > 0 and saved.scale < math.huge then
			for key, value in pairs(saved) do rule[key] = value end
		end
		rule.output, rule.disabled = internal, false
		return rule
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
		local saved = saved_rules()
		local externals = {}
		for _, monitor in ipairs(hl.get_monitors()) do
			if monitor.name == internal then description = monitor.description end
			local preference = saved_for(saved, monitor)
			if monitor.name ~= internal and monitor.name ~= "FALLBACK"
				and monitor.dpms_status ~= false and not (preference and preference.disabled) then
				externals[#externals + 1] = monitor
			end
		end
		local enabled = read_lid() ~= "closed" or #externals == 0
		if internal and panel_enabled ~= enabled then
			-- Native monitor application tests available/preferred modes; Lua has no success return.
			hl.monitor(enabled and panel_rule(saved) or { output = internal, disabled = true })
			panel_enabled = enabled
		end
		manage_workspaces(internal and enabled and internal or nil, externals)
	end

	hl.on("monitor.added", reconcile)
	hl.on("monitor.removed", reconcile)
	if read_lid() then hl.bind("switch:Lid Switch", reconcile, { locked = true }) end
	reconcile()
end
