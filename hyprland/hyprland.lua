-- Applications
local apps = require("icewine.modules.DefaultApps")
apps.terminal = "xdg-terminal-exec"
apps.file_manager = 'xdg-open "$HOME"'
apps.browser = 'gtk-launch "$(xdg-settings get default-web-browser)"'

require("icewine.icewine")

-- Monitors: hyprctl monitors all
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })

-- Autolaunch
-- hl.on("hyprland.start", function()
--     hl.exec_cmd(apps.terminal)
-- end)

-- Your overrides
