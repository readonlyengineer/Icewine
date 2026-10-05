-- User entry point: Icewine owns implementation; add local overrides below.
local implementation = assert(os.getenv("ICEWINE_IMPLEMENTATION"), "ICEWINE_IMPLEMENTATION is required; use the Icewine session environment")
package.path = implementation .. "/hyprland/?.lua;" .. package.path
require("icewine")
