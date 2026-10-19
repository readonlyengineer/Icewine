{ pkgs, ... }:
let
  treesitter = pkgs.vimPlugins.nvim-treesitter.withPlugins (p: with p; [
    bash c cpp diff lua markdown markdown_inline nix python qmljs vim vimdoc
  ]);
  # lazy.nvim resolves its normal plugin names to immutable Nix packages.
  plugins = with pkgs.vimPlugins; {
    "LazyVim" = LazyVim;
    "lazy.nvim" = lazy-nvim;
    "snacks.nvim" = snacks-nvim;
    "persistence.nvim" = persistence-nvim;
    "nvim-treesitter" = pkgs.symlinkJoin {
      name = "nvim-treesitter-with-parsers";
      # Include inherited queries too (for example QML's ecma queries).
      paths = map (entry: entry.plugin) (builtins.genericClosure {
        startSet = [ { key = treesitter.outPath; plugin = treesitter; } ];
        operator = entry: map (plugin: { key = plugin.outPath; inherit plugin; })
          (entry.plugin.dependencies or []);
      });
    };
    "nvim-treesitter-textobjects" = nvim-treesitter-textobjects;
    "nvim-ts-autotag" = nvim-ts-autotag;
    "render-markdown.nvim" = render-markdown-nvim;
    "yazi.nvim" = yazi-nvim;
    "plenary.nvim" = plenary-nvim;
    "nvim-lspconfig" = nvim-lspconfig;
    "blink.cmp" = blink-cmp;
    "friendly-snippets" = friendly-snippets;
    "tokyonight.nvim" = tokyonight-nvim;
    "dracula.nvim" = dracula-nvim;
    "nord.nvim" = nord-nvim;
    "gruvbox.nvim" = gruvbox-nvim;
    "catppuccin" = catppuccin-nvim;
    "mini.pairs" = mini-pairs;
    "mini.ai" = mini-ai;
    "mini.icons" = mini-icons;
    "ts-comments.nvim" = ts-comments-nvim;
    "lazydev.nvim" = lazydev-nvim;
    "grug-far.nvim" = grug-far-nvim;
    "flash.nvim" = flash-nvim;
    "which-key.nvim" = which-key-nvim;
    "gitsigns.nvim" = gitsigns-nvim;
    "trouble.nvim" = trouble-nvim;
    "todo-comments.nvim" = todo-comments-nvim;
    "conform.nvim" = conform-nvim;
    "nvim-lint" = nvim-lint;
    "bufferline.nvim" = bufferline-nvim;
    "lualine.nvim" = lualine-nvim;
    "noice.nvim" = noice-nvim;
    "nui.nvim" = nui-nvim;
  };
  pluginDirectory = pkgs.linkFarm "lazyvim-plugins" (pkgs.lib.mapAttrsToList
    (name: path: { inherit name path; }) plugins);
  editor = pkgs.wrapNeovimUnstable pkgs.neovim-unwrapped {
    wrapRc = false;
    plugins = [ pkgs.vimPlugins.lazy-nvim ];
  };
in pkgs.writeShellScriptBin "icewine-editor" ''
  export PATH=${pkgs.lib.makeBinPath (with pkgs; [ git curl gcc tree-sitter ripgrep fd unzip lazygit stylua shfmt
    lua-language-server clang-tools nixd pyright kdePackages.qtdeclarative bash-language-server marksman ])}:"$PATH"
  export NVIM_APPNAME=icewine-nvim
  export ICEWINE_NVIM_PLUGINS=${pluginDirectory}
  export ICEWINE_NVIM_DEFAULTS=${./defaults.lua}
  exec ${editor}/bin/nvim -u ${./init.lua} "$@"
''
