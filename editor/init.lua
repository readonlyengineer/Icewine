-- Installed by explicit Apply in Neovim's standard configuration directory.
local ok, err = xpcall(function()
  local config = vim.fn.stdpath("config") .. "/icewine/"
  local paths = vim.fn.filereadable(config .. "paths.lua") == 1 and dofile(config .. "paths.lua") or {}
  vim.g.icewine_plugins = paths.plugins
  local lazy = paths.plugins and (paths.plugins .. "/lazy.nvim") or (vim.fn.stdpath("data") .. "/lazy/lazy.nvim")
  if not vim.uv.fs_stat(lazy) then
    if paths.plugins then error("Packaged lazy.nvim is missing: " .. lazy) end
    local output = vim.fn.system({ "git", "clone", "--filter=blob:none", "--branch=stable",
      "https://github.com/folke/lazy.nvim.git", lazy })
    if vim.v.shell_error ~= 0 then error("LazyVim bootstrap failed: " .. output) end
  end
  vim.opt.rtp:prepend(lazy)
  dofile(config .. "defaults.lua")
  for name, plugin in pairs(require("lazy.core.config").plugins) do
    if not plugin._.installed or not vim.uv.fs_stat(plugin.dir) then error("Plugin unavailable: " .. name .. " at " .. plugin.dir) end
  end
end, debug.traceback)
if not ok then
  vim.api.nvim_err_writeln("Icewine Neovim startup failed: " .. err .. "\nCheck plugin paths/network access and retry nvim.")
  vim.cmd("cquit")
end
