----------------
---- MODULES ----
-----------------
--- This is the root of the Hyprland lua tree,
--- Modules are sorted roughly by context upon which
--- they might be invoked in the future
----------------
require("modules.Baseline")
require("modules.LookAndFeel")
require("modules.Theme")
require("modules.WindowPolicy")
require("modules.Binds")
--- DefaultApps piggy backs in on Binds
require("modules.Autostart")

hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })
