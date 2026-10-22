-- Only the launch entry is private. All saved desktop preferences use real XDG roots.
local stage = assert(os.getenv("ICEWINE_ONBOARDING_DIR"))
local config = os.getenv("XDG_CONFIG_HOME") or os.getenv("HOME") .. "/.config"
package.path = stage .. "/lua/?.lua;" .. config .. "/hypr/?.lua;" .. package.path
dofile("/usr/share/icewine/defaults/config/hypr/hyprland.lua")
hl.on("hyprland.start", function()
    hl.exec_cmd('sh "$ICEWINE_ONBOARDING_RUNNER" terminal')
end)
