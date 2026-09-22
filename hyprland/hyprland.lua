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

-- Load handheld behaviour before optional host overrides.
if package.searchpath("modules.Deck", package.path) then
  require("modules.Deck")
end

-- import host personalisation if it exists
if package.searchpath("modules.host", package.path) then
  require("modules.host")
end

if package.searchpath("modules.Personal", package.path) then
  require("modules.Personal")
end
