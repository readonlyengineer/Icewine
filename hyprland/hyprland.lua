-- Applications
local apps = require("icewine.modules.DefaultApps")
apps.terminal = "@terminal@"
apps.file_manager = "@file_manager@"
apps.browser = "@browser@"

require("icewine.icewine")

-- Monitors: hyprctl monitors all
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })

-- Autolaunch
-- hl.on("hyprland.start", function()
--     hl.exec_cmd(apps.terminal)
-- end)

-- Your overrides
