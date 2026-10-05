-- Icewine shared defaults first; add your overrides below.
local config = (os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")) .. "/hypr/"
package.path = config .. "icewine/?.lua;" .. package.path
require("icewine")
