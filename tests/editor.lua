-- Exercise the packaged utility itself, including plugin startup and isolation.
assert(vim.env.NVIM_APPNAME == "icewine-nvim")
assert(vim.fn.stdpath("config"):match("/icewine%-nvim$"))
assert(vim.wait(5000, function() return vim.g.colors_name ~= nil end), "LazyVim theme did not load")
assert(require("lazy.core.config").plugins.LazyVim, "LazyVim is missing")
assert(vim.fn.exists(":IcewineReloadTheme") == 2)
assert(vim.env.EDITOR == "personal-editor" and vim.env.VISUAL == "personal-visual")
assert(vim.g.lazyvim_json == vim.fn.stdpath("state") .. "/lazyvim.json")
print("PASS: packaged LazyVim startup, theme and private namespace")
