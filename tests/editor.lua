local ok, err = xpcall(function()
-- Exercise the ordinary Neovim configuration, including plugin startup.
assert(vim.env.NVIM_APPNAME == nil or vim.env.NVIM_APPNAME == "nvim")
assert(vim.fn.stdpath("config"):match("/nvim$"))
assert(vim.wait(5000, function() return vim.g.colors_name ~= nil end), "LazyVim theme did not load")
assert(require("lazy.core.config").plugins.LazyVim, "LazyVim is missing")
assert(vim.fn.exists(":IcewineReloadTheme") == 2)
assert(vim.env.EDITOR == "personal-editor" and vim.env.VISUAL == "personal-visual")
assert(vim.g.lazyvim_json == vim.fn.stdpath("state") .. "/lazyvim.json")

local lazy = require("lazy")
local config = require("lazy.core.config")
for _, name in ipairs({ "render-markdown.nvim", "yazi.nvim", "nvim-lspconfig", "nvim-treesitter" }) do
  assert(config.plugins[name], name .. " is missing")
end
lazy.load({ plugins = { "render-markdown.nvim", "yazi.nvim" } })
assert(vim.fn.exists(":RenderMarkdown") == 2)
assert(vim.fn.exists(":Yazi") == 2)
print("PASS: ordinary Neovim startup, plugin commands and theme")
end, debug.traceback)
if not ok then
  vim.api.nvim_err_writeln(err)
  vim.cmd("cquit")
end
