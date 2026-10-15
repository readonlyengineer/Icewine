"""Use the real live Palette singleton and renderer in isolated QML fixtures."""
import runpy


def theme_fixture(source, root, theme="tokyo-night"):
    (root / "theme").symlink_to(source / "quickshell/theme")
    config = root / "xdg-config"
    current = config / "icewine/current"
    current.mkdir(parents=True)
    renderer = runpy.run_path(str(source / "scripts/theme"))
    assets = source / "theme/assets"
    files = renderer["render_theme"](assets, assets / "themes" / (theme + ".json"))
    (current / "palette.json").write_text(files["palette.json"])
    return str(config)
