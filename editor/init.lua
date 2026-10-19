-- Optional editor has its own config/data/cache namespace; personal nvim is untouched.
if not os.getenv("ICEWINE_NVIM_PLUGINS") then
  local lazy = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
  if not vim.uv.fs_stat(lazy) then
    local output = vim.fn.system({ "git", "clone", "--filter=blob:none", "--branch=stable",
      "https://github.com/folke/lazy.nvim.git", lazy })
    if vim.v.shell_error ~= 0 then error("LazyVim bootstrap failed: " .. output) end
  end
  vim.opt.rtp:prepend(lazy)
end
dofile(os.getenv("ICEWINE_NVIM_DEFAULTS") or "/usr/share/icewine/editor/defaults.lua")
