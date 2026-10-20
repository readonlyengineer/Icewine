-- Shared non-executable binding definitions and saved chord preferences.
local directory = debug.getinfo(1, "S").source:sub(2):match("^(.*)/")
local definitions, order = {}, {}
local file = assert(io.open(directory .. "/Bindings.tsv", "r"))
for line in file:lines() do
    local id, _, _, chord, kind, flags = line:match("^([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)\t([^\t]+)$")
    assert(id and not definitions[id], "Invalid binding definitions")
    definitions[id] = { chord = chord, kind = kind, flags = flags }
    order[#order + 1] = id
end
file:close()
local modifiers = { "SUPER", "SHIFT", "CTRL", "ALT" }
local keys = { RETURN=true, SPACE=true, PRINT=true, GRAVE=true, TAB=true, LEFT=true, RIGHT=true,
    UP=true, DOWN=true, PRIOR=true, NEXT=true, HOME=true, END=true, MOUSE_UP=true, MOUSE_DOWN=true }
for _, definition in pairs(definitions) do keys[definition.chord:match("([^+]+)$")] = true end
local function valid_chord(chord, kind)
    if type(chord) ~= "string" then return false end
    local rest, count = chord, 0
    for _, modifier in ipairs(modifiers) do
        local replaced
        rest, replaced = rest:gsub("^" .. modifier .. "%+", "")
        count = count + replaced
    end
    local key_ok = keys[rest] or rest:match("^[A-Z0-9]$")
        or (rest:match("^F%d+$") and tonumber(rest:sub(2)) >= 1 and tonumber(rest:sub(2)) <= 12
            and rest == "F" .. tonumber(rest:sub(2)))
        or rest:match("^MOUSE:27[2-9]$")
    if not key_ok then return false end
    local button = rest:match("^MOUSE:") ~= nil
    if kind == "mouse" then return button end
    if button then return false end
    if kind == "hold" or kind == "switcher" then
        return count > 0 and not rest:match("^MOUSE_")
    end
    return true
end
local values = {}
for id, definition in pairs(definitions) do values[id] = definition.chord end
local state_home = os.getenv("XDG_STATE_HOME")
if not state_home or state_home == "" then state_home = (os.getenv("HOME") or "") .. "/.local/state" end
file = io.open(state_home .. "/icewine/hotkeys", "r")
if file then
    local saved, valid = {}, true
    for line in file:lines() do
        local id, chord = line:match("^([a-z0-9_]+)=([A-Z0-9_+:]+)$")
        if not id or not definitions[id] or saved[id] or not valid_chord(chord, definitions[id].kind) then
            valid = false; break
        end
        saved[id] = chord
    end
    file:close()
    local seen = {}
    for id, chord in pairs(values) do
        chord = saved[id] or chord
        if seen[chord] then valid = false end
        seen[chord] = true
    end
    if valid then for id, chord in pairs(saved) do values[id] = chord end
    else print("Invalid Icewine hotkeys; using defaults") end
end
local spelling = {
    ["GRAVE"] = "grave",
    ["PRINT"] = "Print",
    ["LEFT"] = "left",
    ["RIGHT"] = "right",
    ["UP"] = "up",
    ["DOWN"] = "down",
    ["PRIOR"] = "Prior",
    ["NEXT"] = "Next",
    ["HOME"] = "Home",
    ["END"] = "End",
    ["MOUSE_DOWN"] = "mouse_down",
    ["MOUSE_UP"] = "mouse_up",
    ["MOUSE:272"] = "mouse:272",
    ["MOUSE:273"] = "mouse:273",
    ["XF86AUDIORAISEVOLUME"] = "XF86AudioRaiseVolume",
    ["XF86AUDIOLOWERVOLUME"] = "XF86AudioLowerVolume",
    ["XF86AUDIOMUTE"] = "XF86AudioMute",
    ["XF86AUDIOMICMUTE"] = "XF86AudioMicMute",
    ["XF86AUDIONEXT"] = "XF86AudioNext",
    ["XF86AUDIOPAUSE"] = "XF86AudioPause",
    ["XF86AUDIOPLAY"] = "XF86AudioPlay",
    ["XF86AUDIOPREV"] = "XF86AudioPrev",
    ["XF86MONBRIGHTNESSUP"] = "XF86MonBrightnessUp",
    ["XF86MONBRIGHTNESSDOWN"] = "XF86MonBrightnessDown",
}
local function chord(id)
    local parts = {}
    for part in values[id]:gmatch("[^+]+") do parts[#parts + 1] = part:match("^MOUSE:") and part:lower() or spelling[part] or part end
    if id == "cycle" and parts[#parts] == "TAB" then parts[#parts] = "Tab" end
    return table.concat(parts, " + ")
end
local function bind(id, action)
    local options = { description = "icewine:" .. id }
    for flag in definitions[id].flags:gmatch("[^,]+") do if flag ~= "-" then options[flag] = true end end
    hl.bind(chord(id), action, options)
end
return { values = values, chord = chord, bind = bind, order = order }
