-- Shared desktop behaviour; the neighbouring entry owns user overrides.
require("icewine.modules.Baseline")
require("icewine.modules.LookAndFeel")
dofile((os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")) .. "/icewine/current/Theme.lua")
require("icewine.modules.WindowPolicy")
require("icewine.modules.Binds")
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })
