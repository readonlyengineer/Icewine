vim.g.mapleader = " "
vim.g.loaded_netrwPlugin = 1
vim.g.maplocalleader = "\\"
-- Keep the packaged defaults stable even when an older lazyvim.json is present.
vim.g.lazyvim_picker = "snacks"
vim.g.lazyvim_explorer = "snacks"
vim.g.lazyvim_cmp = "blink.cmp"
-- Leave personal LazyExtras metadata untouched; extras need matching Nix packages.
vim.g.lazyvim_json = vim.fn.stdpath("state") .. "/lazyvim.json"

local theme = (os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")) .. "/icewine/current/nvim-theme.lua"
local function transparent_canvas()
  for _, group in ipairs({ "Normal", "NormalNC", "NormalFloat", "SignColumn", "EndOfBuffer", "MsgArea" }) do
    local hl = vim.api.nvim_get_hl(0, { name = group, link = false })
    hl.bg, hl.ctermbg = nil, nil
    vim.api.nvim_set_hl(0, group, hl)
  end
end
vim.api.nvim_create_autocmd("ColorScheme", { callback = transparent_canvas })
local function reload_theme()
  if vim.fn.filereadable(theme) == 1 then
    dofile(theme)
  else
    vim.cmd.colorscheme("tokyonight")
  end
  transparent_canvas()
end
vim.api.nvim_create_user_command("IcewineReloadTheme", reload_theme, {})
vim.api.nvim_create_autocmd("Signal", { pattern = "SIGUSR1", callback = reload_theme })

local plugins = os.getenv("ICEWINE_NVIM_PLUGINS")
local packaged = plugins ~= nil
require("lazy").setup({
  spec = {
    { "LazyVim/LazyVim", import = "lazyvim.plugins", opts = { colorscheme = reload_theme } },
    { import = "lazyvim.plugins.extras.lang.markdown" },
    { "folke/snacks.nvim", opts = { explorer = { replace_netrw = false } } },
    { "mason-org/mason.nvim", enabled = false },
    { "mason-org/mason-lspconfig.nvim", enabled = false },
    -- No preview installer or additional Markdown formatter/linter toolchain.
    { "iamcco/markdown-preview.nvim", enabled = false },
    { "stevearc/conform.nvim", opts = function(_, opts)
      opts.formatters_by_ft.markdown = {}
      opts.formatters_by_ft["markdown.mdx"] = {}
    end },
    { "mfussenegger/nvim-lint", opts = function(_, opts)
      opts.linters_by_ft.markdown = {}
    end },
    { "nvim-treesitter/nvim-treesitter", build = false, opts = function(_, opts)
      opts.ensure_installed = {}
      if packaged then opts.install_dir = plugins .. "/nvim-treesitter" end
    end },
    { "saghen/blink.cmp", opts = { fuzzy = { prebuilt_binaries = { download = false } } } },
    { "neovim/nvim-lspconfig", opts = {
      servers = {
        lua_ls = { settings = { Lua = { runtime = { version = "LuaJIT" }, telemetry = { enable = false } } } },
        clangd = {}, nixd = {}, pyright = {}, qmlls = {}, bashls = {},
      },
    } },
    { "folke/tokyonight.nvim", lazy = false },
    { "Mofiqul/dracula.nvim", lazy = false },
    { "shaunsingh/nord.nvim", lazy = false },
    { "ellisonleao/gruvbox.nvim", lazy = false },
    { "catppuccin/nvim", name = "catppuccin", lazy = false },
    { "MeanderingProgrammer/render-markdown.nvim", opts = { heading = { backgrounds = {} } },
      keys = { { "<leader>md", "<cmd>RenderMarkdown toggle<cr>", desc = "Markdown render toggle" } } },
    { "mikavilpas/yazi.nvim", event = "VeryLazy", dependencies = { "nvim-lua/plenary.nvim" },
      keys = {
        { "<leader>ec", "<cmd>Yazi<cr>", desc = "Explore current" },
        { "<leader>ep", "<cmd>Yazi cwd<cr>", desc = "Explore project" },
      },
      config = function()
        local external_exts = {
          png = true, jpg = true, jpeg = true, gif = true, webp = true,
          bmp = true, svg = true, ico = true, tiff = true,
          mp4 = true, mkv = true, webm = true, mov = true, avi = true, m4v = true,
          mp3 = true, flac = true, ogg = true, wav = true, m4a = true, opus = true,
          pdf = true, epub = true,
          odt = true, ods = true, odp = true,
          doc = true, docx = true, xls = true, xlsx = true, ppt = true, pptx = true,
        }
        require("yazi").setup({
          open_for_directories = true,
          open_file_function = function(chosen_file)
            local ext = chosen_file:match("%.([^.]+)$")
            if ext and external_exts[ext:lower()] then
              vim.fn.jobstart({ "xdg-open", chosen_file }, { detach = true })
            else
              vim.cmd(string.format("edit %s", vim.fn.fnameescape(chosen_file)))
            end
          end,
        })
      end,
    },
  },
  dev = { path = plugins or "~/projects", patterns = packaged and { "" } or {}, fallback = false },
  install = { missing = not packaged },
  checker = { enabled = false },
  rocks = { enabled = false },
  change_detection = { notify = false },
  -- Keep the user's existing config lockfile and downloaded plugin tree untouched.
  lockfile = vim.fn.stdpath("state") .. "/lazy-lock.json",
})
