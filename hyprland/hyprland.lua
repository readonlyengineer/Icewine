-- Applications
local apps = require("icewine.modules.DefaultApps")
apps.terminal = "xdg-terminal-exec"
apps.file_manager = 'xdg-open "$HOME"'
apps.browser = 'gtk-launch "$(xdg-settings get default-web-browser)"'

require("icewine.icewine")

-- Monitors: hyprctl monitors all
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })

-- Optional native monitor preferences; Save sees the standalone import even in HM entries.
if package.searchpath("hyprmon", package.path) then
    local ok, err = pcall(function()
        require("hyprmon")
    end)
    if not ok then print("HyprMon preferences not loaded: " .. tostring(err)) end
end

-- Autolaunch
-- hl.on("hyprland.start", function()
--     hl.exec_cmd(apps.terminal)
-- end)

-- Your overrides
