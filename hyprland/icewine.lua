-- Packaged desktop behaviour. User bindings and autostart remain explicit hooks.
local config = (os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")) .. "/hypr/"
require("modules.Baseline")
require("modules.LookAndFeel")
package.loaded["modules.Theme"] = dofile(config .. "modules/Theme.lua") or true
require("modules.WindowPolicy")
package.loaded["modules.Binds"] = dofile(config .. "modules/Binds.lua") or true
package.loaded["modules.Autostart"] = dofile(config .. "modules/Autostart.lua") or true
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })
