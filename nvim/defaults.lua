vim.cmd.packloadall()
vim.g.mapleader = " "

vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.signcolumn = "yes"
vim.opt.cursorline = true
vim.opt.expandtab = true
vim.opt.shiftwidth = 2
vim.opt.tabstop = 2

vim.diagnostic.config({
  virtual_text = { virt_text_pos = "right_align" },
  signs = true,
  underline = true,
  severity_sort = true,
})

local theme = vim.fn.stdpath("config"):gsub("/nvim$", "") .. "/icewine/current/nvim-theme.lua"
local function reload_theme()
  if vim.fn.filereadable(theme) == 1 then
    dofile(theme)
  end
end
reload_theme()
vim.api.nvim_create_user_command("IcewineReloadTheme", reload_theme, {})
vim.api.nvim_create_autocmd("Signal", { pattern = "SIGUSR1", callback = reload_theme })

vim.api.nvim_create_autocmd("FileType", {
  pattern = { "bash", "c", "cpp", "help", "lua", "markdown", "nix", "python", "qml", "sh", "vim" },
  callback = function()
    vim.treesitter.start()
    vim.bo.indentexpr = "v:lua.require'nvim-treesitter'.indentexpr()"
  end,
})

require("render-markdown").setup({ heading = { backgrounds = {} } })
vim.keymap.set("n", "<leader>md", "<cmd>RenderMarkdown toggle<cr>", { desc = "Markdown render toggle" })

vim.g.loaded_netrwPlugin = 1
vim.api.nvim_create_autocmd("UIEnter", {
  once = true,
  callback = function()
    require("yazi").setup({
      open_for_directories = true,
      open_file_function = function(chosen_file)
        local external_exts = {
          png = true, jpg = true, jpeg = true, gif = true, webp = true,
          bmp = true, svg = true, ico = true, tiff = true,
          mp4 = true, mkv = true, webm = true, mov = true, avi = true, m4v = true,
          mp3 = true, flac = true, ogg = true, wav = true, m4a = true, opus = true,
          pdf = true, epub = true,
          odt = true, ods = true, odp = true,
          doc = true, docx = true, xls = true, xlsx = true, ppt = true, pptx = true,
        }
        local ext = chosen_file:match("%.([^.]+)$")
        if ext and external_exts[ext:lower()] then
          vim.fn.jobstart({ "xdg-open", chosen_file }, { detach = true })
        else
          vim.cmd(string.format("edit %s", vim.fn.fnameescape(chosen_file)))
        end
      end,
    })
  end,
})
vim.keymap.set("n", "<leader>ec", "<cmd>Yazi<cr>", { desc = "Explore current" })
vim.keymap.set("n", "<leader>ep", "<cmd>Yazi cwd<cr>", { desc = "Explore project" })

require("blink.cmp").setup({
  keymap = { preset = "enter" },
  fuzzy = { prebuilt_binaries = { download = false } },
})
vim.lsp.config("*", { capabilities = require("blink.cmp").get_lsp_capabilities() })
vim.lsp.config("lua_ls", {
  settings = { Lua = { runtime = { version = "LuaJIT" }, telemetry = { enable = false } } },
})
vim.lsp.enable({ "lua_ls", "clangd", "nixd", "pyright", "qmlls", "bashls" })
