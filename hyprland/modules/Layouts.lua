-- Native layout preferences. Runtime choices belong to one compositor instance.
local M = {}
local supported = { scrolling = true, dwindle = true, master = true, monocle = true }
local choices, rules = {}, {}
local runtime, signature = os.getenv("XDG_RUNTIME_DIR"), os.getenv("HYPRLAND_INSTANCE_SIGNATURE")
local session = runtime and signature and runtime .. "/hypr/" .. signature .. "/icewine-layouts"

function M.default()
    local state = os.getenv("XDG_STATE_HOME") or os.getenv("HOME") .. "/.local/state"
    local file = io.open(state .. "/icewine/layout", "r")
    if not file then return "scrolling" end
    local value = file:read("*l"); file:close()
    return supported[value] and value or "scrolling"
end

local function encode(value)
    return (value:gsub(".", function(byte) return string.format("%02x", byte:byte()) end))
end

local function load()
    local file = session and io.open(session, "r")
    if not file then return end
    for line in file:lines() do
        local layout, hex = line:match("^(%a+) ([0-9a-f]+)$")
        if supported[layout] and #hex % 2 == 0 then
            local selector = hex:gsub("..", function(byte) return string.char(tonumber(byte, 16)) end)
            if selector:match("^[1-9]%d*$") or selector:match("^name:.+") or selector:match("^special:.+") then
                choices[selector] = layout
            end
        end
    end
    file:close()
end

local function save(nextChoices)
    assert(session, "Session layout storage unavailable")
    local file = assert(io.open(session .. ".tmp", "w"))
    local ok, err = true, nil
    for selector, layout in pairs(nextChoices) do
        ok, err = file:write(layout .. " " .. encode(selector) .. "\n")
        if not ok then break end
    end
    local closed, closeError = file:close()
    assert(ok and closed, err or closeError)
    assert(os.rename(session .. ".tmp", session))
end

local function apply(selector, layout)
    -- The native manager merges identical raw selectors, while matching trims
    -- leading whitespace. Reserve this spelling so disabling our handle never
    -- disables a user's ordinary workspace rule or its other properties.
    -- Append the replacement after later external rules, retaining their fields.
    -- Ponytail: one disabled rule per reselection stays until reload; use native
    -- removal/reordering when Hyprland exposes it to bound long-session growth.
    if rules[selector] then rules[selector]:set_enabled(false) end
    rules[selector] = assert(hl.workspace_rule({ workspace = "\t " .. selector, layout = layout }))
end

local function workspace(id)
    assert(type(id) == "number" and id % 1 == 0, "Invalid workspace ID")
    -- Scan by ID: negative named/special IDs are relative selectors in Hyprland.
    for _, ws in ipairs(hl.get_workspaces()) do
        if ws.id == id then return ws end
    end
    error("Workspace is no longer available")
end

function M.select(id, identity, layout)
    assert(layout == "default" or supported[layout], "Unsupported layout")
    local ws = workspace(id)
    assert(type(identity) == "string" and encode(ws.config_name) == identity, "Workspace identity changed")
    local selector = ws.config_name
    local nextChoices = {}
    for key, value in pairs(choices) do nextChoices[key] = value end
    nextChoices[selector] = layout ~= "default" and layout or nil
    save(nextChoices) -- Failed storage must not change the live workspace.
    if layout == "default" then
        if rules[selector] then rules[selector]:set_enabled(false) end
    else
        apply(selector, layout)
    end
    choices = nextChoices
end

function M.status(id)
    local ws = workspace(id)
    local effective = supported[ws.tiled_layout] and ws.tiled_layout or "unknown"
    local default = hl.get_config("general.layout")
    default = supported[default] and default or "unknown"
    return string.format('{"workspace":%d,"identity":"%s","effective":"%s","default":"%s","override":"%s"}',
        id, encode(ws.config_name), effective, default, choices[ws.config_name] or "")
end

load()
hl.on("config.reloaded", function()
    for selector, layout in pairs(choices) do apply(selector, layout) end
end)
return M
