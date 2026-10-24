#!/usr/bin/env python3
"""Direct ordinary-Neovim checks: tests/editor.py SOURCE CACHED_PLUGIN_DIRECTORY."""
import contextlib
import importlib.machinery
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
from unittest.mock import patch

source, plugins = (Path(value).resolve() for value in sys.argv[1:])
nvim = shutil.which("nvim")
assert nvim, "Neovim is required"
manage = types.ModuleType("editor_manage")
manage.__file__ = str(source / "scripts/manage")
importlib.machinery.SourceFileLoader(manage.__name__, manage.__file__).exec_module(manage)


with tempfile.TemporaryDirectory(prefix="icewine ordinary nvim ") as temporary:
    root = Path(temporary)
    config, data, state, defaults = (root / name for name in ("config", "data", "state", "defaults"))
    (defaults / "config/nvim/icewine").mkdir(parents=True)
    (defaults / "data").mkdir()
    shutil.copyfile(source / "editor/init.lua", defaults / "config/nvim/init.lua")
    shutil.copyfile(source / "editor/defaults.lua", defaults / "config/nvim/icewine/defaults.lua")
    env = os.environ | dict(HOME=str(root), XDG_CONFIG_HOME=str(config), XDG_DATA_HOME=str(data),
        XDG_STATE_HOME=str(root / "xdg-state"), XDG_CACHE_HOME=str(root / "cache"),
        ICEWINE_DEFAULT_FILES=str(defaults), ICEWINE_THEME_ASSETS=str(source / "theme/assets"),
        EDITOR="personal-editor", VISUAL="personal-visual")
    env.pop("NVIM_APPNAME", None)
    selected = dict.fromkeys(manage.FEATURES, False) | {"steam": "none"}

    def apply(enabled, overwrite=False, readonly=False):
        value = selected | {"texteditor": enabled}
        with patch.dict(os.environ, env, clear=True), \
             patch.object(manage.platform, "freedesktop_os_release", return_value={"ID": "arch"}), \
             patch.object(manage.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)), \
             contextlib.redirect_stdout(io.StringIO()):
            manage.apply(value, overwrite, readonly, value, config, data, state)

    def launch(*args):
        result = subprocess.run([nvim, "--headless", *args, "-c", "qa"], env=env,
            capture_output=True, text=True, timeout=45)
        if result.returncode == 0:
            assert "stack traceback:" not in result.stderr, result.stderr
        return result

    init = config / "nvim/init.lua"
    apply(False)
    assert not init.exists()
    init.parent.mkdir(parents=True)
    init.write_text("vim.g.personal_editor = true\n")
    apply(True)
    assert init.read_text() == "vim.g.personal_editor = true\n"
    assert launch("-c", "lua assert(vim.g.personal_editor and not vim.g.icewine_plugins)").returncode == 0
    apply(False)
    assert init.exists(), "Disabling removed personal config"
    # Explicit Overwrite takes ownership of regular config; Apply works in host-policy mode too.
    apply(True, overwrite=True, readonly=True)
    assert init.read_bytes() == (source / "editor/init.lua").read_bytes()
    personal = data / "nvim/lazy/personal/sentinel"
    personal.parent.mkdir(parents=True)
    personal.write_text("personal plugin data\n")
    # Nix supplies this path in configuration, with no environment or launcher.
    paths = config / "nvim/icewine/paths.lua"
    paths.write_text("return { plugins = " + json.dumps(str(plugins)) + " }\n")
    filename = root / "notes with spaces;$(literal).md"
    filename.write_text("# Markdown\n")
    result = launch(str(filename), "-c", "luafile " + str(source / "tests/editor.lua"))
    assert result.returncode == 0, result.stderr
    assert "PASS: ordinary Neovim startup" in result.stderr, result.stderr
    paths.write_text('return { plugins = "/missing-icewine-plugin-fixture" }\n')
    failed = launch()
    assert failed.returncode != 0 and "Packaged lazy.nvim is missing" in failed.stderr, failed.stderr
    paths.write_text("return { plugins = " + json.dumps(str(plugins)) + " }\n")
    unmanaged = root / "unmanaged.lua"
    unmanaged.write_text("vim.g.personal_editor = true\n")
    assert launch("-u", str(unmanaged), "-c", 'lua assert(vim.g.personal_editor and vim.fn.exists(":IcewineReloadTheme") == 0)').returncode == 0
    # Native config uses the normal user plugin tree. Seed cached dependencies to avoid network.
    paths.unlink()
    for plugin in plugins.iterdir():
        shutil.copytree(plugin.resolve(), data / "nvim/lazy" / plugin.name, symlinks=True)
    result = launch(str(filename), "-c", "luafile " + str(source / "tests/editor.lua"))
    assert result.returncode == 0, result.stderr
    assert "PASS: ordinary Neovim startup" in result.stderr, result.stderr
    apply(False)
    assert not init.exists()
    assert personal.read_text() == "personal plugin data\n"
    assert launch("-c", 'lua assert(vim.fn.exists(":IcewineReloadTheme") == 0)').returncode == 0
    apply(True)
    init.write_text(init.read_text() + "-- user modification\n")
    apply(False)
    assert init.read_text().endswith("-- user modification\n")
    init.unlink()
    outside = root / "personal-init.lua"
    outside.write_text("personal symlink\n")
    init.symlink_to(outside)
    apply(True, overwrite=True)
    apply(False)
    assert init.is_symlink() and outside.read_text() == "personal symlink\n"
    init.unlink()
    vim_init = config / "nvim/init.vim"
    vim_init.write_text('let g:personal_editor = 1\n')
    apply(True, overwrite=True)
    assert not init.exists() and vim_init.read_text() == 'let g:personal_editor = 1\n'
    vim_init.unlink()
    apply(False)
    implementation = root / "implementation"
    (defaults / "config/nvim/icewine").rename(implementation)
    # Start the implementation-link case with an empty support path.
    (config / "nvim/icewine").rmdir()
    (defaults / "config/nvim/icewine").symlink_to(implementation)
    apply(True)
    assert (config / "nvim/icewine").is_symlink()
    apply(False)
    assert not init.exists() and not (config / "nvim/icewine").is_symlink()
    # Both platforms ship a support link. Personal conflicts must block the
    # whole group before a main init can be created or overwritten.
    for kind in ("directory", "symlink"):
        for overwrite in (False, True):
            for personal_init in (False, True):
                fixture = root / f"conflict-{kind}-{overwrite}-{personal_init}"
                config, data, state = (fixture / name for name in ("config", "data", "state"))
                support = config / "nvim/icewine"
                support.parent.mkdir(parents=True)
                outside = fixture / "personal-support" if kind == "symlink" else support
                outside.mkdir()
                (outside / "personal.lua").write_text("personal support\n")
                if kind == "symlink":
                    support.symlink_to(outside)
                init = config / "nvim/init.lua"
                if personal_init:
                    init.write_text("vim.g.personal_editor = true\n")
                env.update(HOME=str(fixture), XDG_CONFIG_HOME=str(config), XDG_DATA_HOME=str(data),
                    XDG_STATE_HOME=str(fixture / "xdg-state"), XDG_CACHE_HOME=str(fixture / "cache"))
                with contextlib.redirect_stderr(io.StringIO()) as pending:
                    apply(True, overwrite=overwrite, readonly=overwrite)
                assert init.exists() == personal_init, "Support conflict installed a new managed init"
                if personal_init:
                    assert init.read_text() == "vim.g.personal_editor = true\n", "Support conflict replaced personal init"
                assert "Pending: Neovim config group" in pending.getvalue()
                assert (outside / "personal.lua").read_text() == "personal support\n"
                assert support.is_symlink() == (kind == "symlink")
                assert not (support / "defaults.lua").exists()
                assert not manage.theme.default_records(state).get("config", {}).get("files")
                ordinary = launch("-c", 'lua assert(vim.fn.exists(":IcewineReloadTheme") == 0)')
                assert ordinary.returncode == 0, ordinary.stderr
    print("PASS: conflicting support directories/symlinks preserve absent/personal init with Overwrite off/on and ordinary startup")
    print("PASS: ordinary Nix/native plugin startup, literal file launch, enable/disable, ownership and preservation")

with tempfile.TemporaryDirectory(prefix="icewine failed nvim ") as temporary:
    root = Path(temporary)
    config = root / "config/nvim"
    (config / "icewine").mkdir(parents=True)
    shutil.copyfile(source / "editor/init.lua", config / "init.lua")
    shutil.copyfile(source / "editor/defaults.lua", config / "icewine/defaults.lua")
    (root / "bin").mkdir()
    git = root / "bin/git"
    git.write_text('#!/bin/sh\nif [ "$1" = --version ]; then echo "git version 2.50.0"; exit 0; fi\necho "offline acquisition fixture" >&2\nexit 1\n')
    git.chmod(0o755)
    env = os.environ | dict(HOME=str(root), XDG_CONFIG_HOME=str(root / "config"),
        XDG_DATA_HOME=str(root / "data"), XDG_STATE_HOME=str(root / "state"),
        XDG_CACHE_HOME=str(root / "cache"), PATH=str(root / "bin") + ":" + os.environ["PATH"])
    env.pop("NVIM_APPNAME", None)
    failed = subprocess.run([nvim, "--headless", "-c", "qa"], env=env, capture_output=True, text=True, timeout=45)
    assert failed.returncode != 0 and "LazyVim bootstrap failed" in failed.stderr, failed.stderr
    lazy = root / "data/nvim/lazy/lazy.nvim"
    lazy.parent.mkdir(parents=True)
    lazy.symlink_to((plugins / "lazy.nvim").resolve())
    failed = subprocess.run([nvim, "--headless", "-c", "qa"], env=env, capture_output=True, text=True, timeout=45)
    assert failed.returncode != 0 and "Plugin unavailable:" in failed.stderr, failed.stderr
    print("PASS: offline lazy.nvim bootstrap and downstream plugin acquisition fail visibly and nonzero")
