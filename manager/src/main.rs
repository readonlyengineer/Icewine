use std::{collections::BTreeMap, fs::{self, OpenOptions}, io::{self, IsTerminal}, os::unix::fs::OpenOptionsExt, path::PathBuf, process::{Command, ExitCode}};
use crossterm::event::{self, Event, KeyCode, KeyEventKind};
use ratatui::{layout::Flex, prelude::*, widgets::{Block, BorderType, Cell, Padding, Paragraph, Row, Table, Wrap}};

const ROWS: &[(&str, &str, &str)] = &[
    ("desktop", "Desktop session", "Hyprland + Icewine Quickshell"),
    ("terminal", "Terminal", "Kitty"),
    ("filemanager", "File manager", "Yazi"),
    ("steam", "Steam (unfree)", ""),
    ("gamescope", " +- Gamescope", ""), ("handheld", " \u{005c}- Handheld", "Needs Desktop + native Steam + Gamescope"),
    ("login", "Login styling", "tuigreet (host configuration)"), ("shellExtras", "Shell Extras", "Starship + Fastfetch + btop theme"),
];

#[derive(Clone, Copy, PartialEq)]
enum Control { Theme, Transparency, Layout, Wallpaper, Monitors, Utility(&'static str), Widget(usize), Steam, Overwrite, Apply, Cancel }

const STEAM: &[&str] = &["none", "native", "flatpak"];

const LAYOUTS: &[&str] = &["scrolling", "dwindle", "master", "monocle"];

const TRANSPARENCY: &[&str] = &["off", "low", "med", "high"];

fn appearance_command(args: &[&str]) -> io::Result<String> {
    let output = Command::new("icewine").args(args).output()?;
    let text = String::from_utf8_lossy(&output.stdout).to_string()
        + &String::from_utf8_lossy(&output.stderr);
    if !output.status.success() {
        return Err(io::Error::other(text));
    }
    Ok(text)
}

struct Appearance {
    themes: Vec<String>, theme: usize, policy: bool, transparency: usize,
    layout: usize, wallpaper: PathBuf,
}

impl Appearance {
    fn load() -> io::Result<Self> {
        let theme = appearance_command(&["theme"])?;
        let themes: Vec<String> = theme.lines().find_map(|line| line.strip_prefix("Installed: "))
            .ok_or_else(|| io::Error::other("Missing installed themes"))?
            .split(", ").map(str::to_owned).collect();
        let effective = theme.lines().find_map(|line| line.strip_prefix("Effective: "))
            .ok_or_else(|| io::Error::other("Missing effective theme"))?;
        let policy = effective.ends_with(" (Nix policy)");
        let selected = effective.trim_end_matches(" (Nix policy)");
        let theme = themes.iter().position(|value| value == selected)
            .ok_or_else(|| io::Error::other("Invalid effective theme"))?;
        let level = appearance_command(&["transparency"])?;
        let selected = level.strip_prefix("Transparency: ").and_then(|text| text.split_whitespace().next())
            .ok_or_else(|| io::Error::other("Missing transparency"))?;
        let transparency = TRANSPARENCY.iter().position(|value| *value == selected)
            .ok_or_else(|| io::Error::other("Invalid transparency"))?;
        let layout = appearance_command(&["layout"])?;
        let selected = layout.strip_prefix("Layout: ").and_then(|text| text.split_whitespace().next())
            .ok_or_else(|| io::Error::other("Missing layout"))?;
        let layout = LAYOUTS.iter().position(|value| *value == selected)
            .ok_or_else(|| io::Error::other("Invalid layout"))?;
        let data = std::env::var_os("ICEWINE_WALLPAPER_DATA_HOME")
            .or_else(|| std::env::var_os("XDG_DATA_HOME")).map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from(std::env::var_os("HOME").unwrap_or_default()).join(".local/share"));
        let directory = data.join("icewine/wallpapers");
        let wallpaper = if directory.join("selection.img").is_file() { directory.join("selection.img") }
            else { data.join("wallpapers/default.jpg") };
        Ok(Self { themes, theme, policy, transparency, layout, wallpaper })
    }
}

const WIDGETS: &[(&str, &str, &str)] = &[
    ("notificationToasts", "Notification toasts", "Popup cards; history and sounds stay"),
    ("windowSwitcher", "Window switcher", "Optional window list and shortcut"),
];

struct Widgets {
    enabled: [bool; 2], policy: [bool; 2], supported: bool, revision: String,
}

fn widget_command(args: &[String]) -> io::Result<String> {
    let output = Command::new("icewine-manage-backend").args(args).output()?;
    let text = String::from_utf8_lossy(&output.stdout).to_string()
        + &String::from_utf8_lossy(&output.stderr);
    if !output.status.success() { return Err(io::Error::other(text)); }
    Ok(text)
}

impl Widgets {
    fn load() -> io::Result<Self> {
        let text = widget_command(&["widgets-state".into()])?;
        let mut fields = BTreeMap::new();
        for field in text.split_whitespace() {
            let (name, value) = field.split_once('=').ok_or_else(|| io::Error::other("Invalid widget state"))?;
            if fields.insert(name, value).is_some() { return Err(io::Error::other("Duplicate widget field")); }
        }
        let boolean = |value| match value {
            Some("true") => Ok(true), Some("false") => Ok(false),
            _ => Err(io::Error::other("Invalid widget state")),
        };
        let supported = boolean(fields.remove("supported"))?;
        let revision = fields.remove("revision").filter(|value| value.len() == 64 && value.bytes().all(|c| c.is_ascii_hexdigit()))
            .ok_or_else(|| io::Error::other("Invalid widget revision"))?.to_owned();
        let mut enabled = [true; 2];
        let mut policy = [false; 2];
        for (index, (id, _, _)) in WIDGETS.iter().enumerate() {
            let (value, owner) = fields.remove(id).and_then(|value| value.split_once(':'))
                .ok_or_else(|| io::Error::other("Missing widget state"))?;
            enabled[index] = boolean(Some(value))?;
            policy[index] = match owner { "policy" => true, "user" => false,
                _ => return Err(io::Error::other("Invalid widget ownership")) };
        }
        if !fields.is_empty() { return Err(io::Error::other("Unknown widget state")); }
        Ok(Self { enabled, policy, supported, revision })
    }

    fn save(&mut self) -> io::Result<String> {
        let mut args = vec!["widgets-apply".into(), format!("revision={}", self.revision)];
        args.extend(WIDGETS.iter().enumerate().map(|(index, (id, _, _))| format!("{id}={}", self.enabled[index])));
        let text = widget_command(&args)?;
        *self = Self::load().map_err(|error| io::Error::other(format!("Save completed; refresh failed: {error}")))?;
        Ok(text)
    }
}

fn filename(path: &std::path::Path) -> String {
    path.file_name().unwrap_or_default().to_string_lossy().chars()
        .map(|c| if c.is_control() { '?' } else { c }).collect()
}

fn picker(terminal: &mut ratatui::DefaultTerminal) -> io::Result<Option<PathBuf>> {
    // Exclusive creation protects the chooser handoff from pre-existing paths.
    let file = std::env::temp_dir().join(format!("icewine-picker-{}", std::process::id()));
    OpenOptions::new().write(true).create_new(true).mode(0o600).open(&file)?;
    let result = (|| {
        ratatui::restore();
        let result = Command::new("yazi").arg("--chooser-file").arg(&file).status();
        *terminal = ratatui::init();
        if !result.map_err(|error| io::Error::other(format!("Yazi unavailable: {error}")))?.success() {
            return Err(io::Error::other("Yazi exited unsuccessfully"));
        }
        let selected = fs::read_to_string(&file)?;
        let selected = selected.trim_end_matches('\n');
        Ok((!selected.is_empty()).then(|| PathBuf::from(selected)))
    })();
    fs::remove_file(file)?;
    result
}

fn handheld_available(steam: usize, selected: &BTreeMap<&str, bool>) -> bool {
    steam == 1 && selected["desktop"] && selected["gamescope"]
}

fn choose(readonly: bool, selected: &mut BTreeMap<&str, bool>, steam: &mut usize) -> io::Result<Option<bool>> {
    let mut appearance = Appearance::load()?;
    let (mut widgets, mut widget_message) = match Widgets::load() {
        Ok(value) => (value, String::new()),
        Err(error) => (Widgets { enabled: [true; 2], policy: [false; 2], supported: false, revision: String::new() }, error.to_string()),
    };
    let mut message = String::new();
    let mut page = 0;
    let mut focuses = [0, 0, 0];
    let mut terminal = ratatui::init();
    let result = (|| {
        let mut focus = 0;
        let mut overwrite = false;
        loop {
            let rows: Vec<_> = ROWS.iter().filter(|(id, _, _)|
                (readonly || *id != "login") && (*steam != 0 || !matches!(*id, "gamescope" | "handheld"))).collect();
            let controls: Vec<_> = if page == 1 {
                let mut controls = Vec::new();
                if !appearance.policy { controls.push(Control::Theme); }
                controls.extend([Control::Transparency, Control::Wallpaper]);
                controls.extend([Control::Monitors, Control::Layout, Control::Apply, Control::Cancel]);
                controls
            } else if page == 2 {
                WIDGETS.iter().enumerate().filter(|(index, _)| widgets.supported && !widgets.policy[*index])
                    .map(|(index, _)| Control::Widget(index))
                    .chain(widgets.supported.then_some(Control::Apply)).chain([Control::Cancel]).collect()
            } else { rows.iter().filter(|(id, _, _)| !readonly
                && (*id != "handheld" || handheld_available(*steam, selected)))
                .map(|(id, _, _)| if *id == "steam" { Control::Steam } else { Control::Utility(*id) })
                .chain([Control::Overwrite, Control::Apply, Control::Cancel]).collect() };
            focus = focus.min(controls.len() - 1);
            terminal.draw(|frame| {
                let accent = Style::default().fg(Color::Cyan).bold();
                let muted = Style::default().fg(Color::DarkGray);
                let focused = Style::default().fg(Color::Black).bg(Color::Cyan).bold();
                let [panel] = Layout::horizontal([Constraint::Max(96)])
                    .flex(Flex::Center).areas(frame.area());
                let [panel] = Layout::vertical([Constraint::Max(24)])
                    .flex(Flex::Center).areas(panel);
                let block = Block::bordered().border_type(BorderType::Rounded)
                    .border_style(muted).title(Line::from(match page {
                        0 => " Icewine Installer (1/3) | Tab: Appearance ",
                        1 => " Icewine Appearance (2/3) | Tab: Widgets ",
                        _ => " Icewine Widgets (3/3) | Tab: Installer ",
                    }).style(accent))
                    .padding(Padding::horizontal(1));
                if frame.area().width < 80 || frame.area().height < 24 {
                    frame.render_widget(Paragraph::new("Icewine needs an 80 x 24 terminal.\nResize to continue; Esc: cancel.").style(accent), frame.area());
                    return;
                }
                let inner = block.inner(panel);
                frame.render_widget(block, panel);
                let [intro, utilities, reset, buttons, help] = Layout::vertical([
                    Constraint::Length(4), Constraint::Min(10),
                    Constraint::Length(3), Constraint::Length(2), Constraint::Length(2),
                ]).areas(inner);
                if page == 1 {
                    frame.render_widget(Paragraph::new(vec![
                        Line::from("Appearance updates immediately.").style(accent),
                        Line::from("Apply/Cancel here control utility choices only.").style(muted),
                        Line::from("HyprMon live/save changes remain after Cancel.").style(muted),
                    ]), intro);
                    let settings = vec![
                        (Control::Theme, "Theme", format!("< {} >{}", appearance.themes[appearance.theme], if appearance.policy { " (Nix policy)" } else { "" })),
                        (Control::Transparency, "Transparency", format!("< {} >", TRANSPARENCY[appearance.transparency])),
                        (Control::Wallpaper, "Wallpaper", format!("[ {} ]", filename(&appearance.wallpaper))),
                        (Control::Monitors, "Monitors", "[ Configure monitors… ]".to_owned()),
                        (Control::Layout, "Desktop layout default", format!("< {} >", LAYOUTS[appearance.layout])),
                    ];
                    frame.render_widget(Table::new(settings.into_iter().map(|(control, label, value)|
                        Row::new([Cell::from(label), Cell::from(value)]).bottom_margin(u16::from(control != Control::Layout)).style(if controls[focus] == control { focused }
                            else if control == Control::Theme && appearance.policy { muted } else { Style::default() })),
                        [Constraint::Length(23), Constraint::Min(20)]).column_spacing(2), utilities);
                    frame.render_widget(Paragraph::new(message.chars().map(|c| if c.is_control() && c != '\n' { '?' } else { c }).collect::<String>()).style(accent).wrap(Wrap { trim: false }), reset);
                } else if page == 2 {
                    frame.render_widget(Paragraph::new(vec![
                        Line::from("First-party widgets; no plugin loading.").style(accent),
                        Line::from("Save commits widgets only; Cancel/Esc discards drafts.").style(muted),
                        Line::from("Installer drafts stay pending; appearance stays live.").style(muted),
                        Line::from(if widgets.supported { "Saved preferences apply live and survive session restart." }
                            else { "Unavailable: restore shipped settings/entry via Installer." }).style(muted),
                    ]), intro);
                    frame.render_widget(Table::new(WIDGETS.iter().enumerate().map(|(index, (_, label, description))| {
                        Row::new([Cell::from(Text::from(vec![Line::from(*label), Line::from(*description).style(if controls[focus] == Control::Widget(index) { focused } else { muted })])),
                            Cell::from(format!("[{}]{}", if !widgets.supported { "?" } else if widgets.enabled[index] { "x" } else { " " },
                                if widgets.policy[index] { " Nix policy" } else if !widgets.supported { " unavailable" } else { "" }))]).height(2).top_margin(u16::from(index == 0)).bottom_margin(1)
                            .style(if controls[focus] == Control::Widget(index) { focused }
                                else if widgets.policy[index] || !widgets.supported { muted } else { Style::default() })
                    }), [Constraint::Min(36), Constraint::Length(16)]).column_spacing(2), utilities);
                    frame.render_widget(Paragraph::new(widget_message.chars().map(|c| if c.is_control() && c != '\n' { '?' } else { c }).collect::<String>()).style(accent).wrap(Wrap { trim: false }), reset);
                } else {
                frame.render_widget(Paragraph::new(vec![
                    Line::from("Optional utilities, configured for Icewine.").style(accent),
                    Line::from("Selected utilities are installed and configured.").style(muted),
                    Line::from(if readonly {
                        "NixOS: utility selections are read-only."
                    } else {
                        "Deselecting removes Icewine configuration; packages stay installed."
                    }).style(muted),
                ]), intro);
                let rows = rows.iter().map(|(id, purpose, defaults)| {
                    let available = *id != "handheld" || handheld_available(*steam, selected);
                    let active = controls[focus] == (if *id == "steam" { Control::Steam } else { Control::Utility(id) });
                    Row::new(vec![
                        Cell::from(*purpose),
                        Cell::from(*defaults).style(muted),
                        Cell::from(Line::from(if *id == "steam" { format!("< {} >", STEAM[*steam]) }
                            else { (if selected[id] { "[x]" } else { "[ ]" }).to_owned() }).right_aligned())
                            .style(if active { focused } else if readonly || !available { muted } else { accent }),
                    ]).style(if active { focused } else { Style::default() })
                });
                frame.render_widget(Table::new(rows, [
                    Constraint::Length(18), Constraint::Min(20), Constraint::Length(11),
                ]).column_spacing(2).header(Row::new([
                    Cell::from("Utility"), Cell::from("Contains"),
                    Cell::from(Line::from("Configure").right_aligned()),
                ]).style(accent).bottom_margin(1)), utilities);
                frame.render_widget(Paragraph::new(format!("[{}] Overwrite existing dotfiles",
                    if overwrite { "x" } else { " " }))
                    .style(if controls[focus] == Control::Overwrite { focused } else { Style::default() }), reset);
                }
                frame.render_widget(Paragraph::new(Line::from(vec![
                    Span::styled(if page == 2 { "[ Save ]" } else { "[ Apply ]" }, if controls[focus] == Control::Apply { focused } else if page == 2 && !widgets.supported { muted } else { accent }),
                    Span::raw("   "),
                    Span::styled("[ Cancel ]", if controls[focus] == Control::Cancel { focused } else { muted }),
                ])), buttons);
                frame.render_widget(Paragraph::new(vec![
                    Line::from("Tab: page   Up/down: move   Shift-Tab: previous control"),
                    Line::from(if page == 0 { "Left/right: Steam   Space/Enter: act   Esc: cancel" }
                        else if page == 1 { "Left/right: cycle   Space/Enter: act   Esc: cancel" }
                        else { "Space/Enter: act   Esc: cancel" }),
                ]).style(muted), help);
            })?;
            let Event::Key(key) = event::read()? else { continue };
            if key.kind != KeyEventKind::Press { continue; }
            match key.code {
                KeyCode::Esc | KeyCode::Char('q') => return Ok(None),
                KeyCode::Char('c') if key.modifiers.contains(event::KeyModifiers::CONTROL) => return Ok(None),
                _ if terminal.size()?.width < 80 || terminal.size()?.height < 24 => (),
                KeyCode::Tab => { focuses[page] = focus; page = (page + 1) % 3; focus = focuses[page]; }
                KeyCode::Left | KeyCode::Right if matches!(controls[focus], Control::Theme | Control::Transparency | Control::Layout) => {
                    let (values, current, command) = if controls[focus] == Control::Theme {
                        (appearance.themes.iter().map(String::as_str).collect::<Vec<_>>(), appearance.theme, "theme")
                    } else if controls[focus] == Control::Layout {
                        (LAYOUTS.to_vec(), appearance.layout, "layout")
                    } else { (TRANSPARENCY.to_vec(), appearance.transparency, "transparency") };
                    let next = (current + if key.code == KeyCode::Right { 1 } else { values.len() - 1 }) % values.len();
                    message = match appearance_command(&[command, values[next]]) {
                        Ok(text) => text, Err(error) => error.to_string(),
                    };
                    // Selection can commit before live delivery fails. Read the
                    // effective backend values even when the action returned an error.
                    match Appearance::load() {
                        Ok(updated) => {
                            appearance.themes = updated.themes;
                            appearance.theme = updated.theme;
                            appearance.policy = updated.policy;
                            appearance.transparency = updated.transparency;
                            appearance.layout = updated.layout;
                        }
                        Err(error) => message.push_str(&format!("\nCould not refresh appearance state: {error}")),
                    }
                }
                KeyCode::Left | KeyCode::Right if controls[focus] == Control::Steam => {
                    let previous = *steam;
                    *steam = (*steam + if key.code == KeyCode::Right { 1 } else { STEAM.len() - 1 }) % STEAM.len();
                    if previous == 0 { selected.insert("gamescope", true); }
                    if *steam == 0 { selected.insert("gamescope", false); }
                    if !handheld_available(*steam, selected) { selected.insert("handheld", false); }
                }
                KeyCode::Down | KeyCode::Right => {
                    focus = (focus + 1) % controls.len();
                }
                KeyCode::BackTab | KeyCode::Up | KeyCode::Left => {
                    focus = (focus + controls.len() - 1) % controls.len();
                }
                KeyCode::Char(' ') | KeyCode::Enter => match controls[focus] {
                    Control::Widget(index) => widgets.enabled[index] ^= true,
                    Control::Utility(id) => {
                        *selected.get_mut(id).unwrap() ^= true;
                        if !handheld_available(*steam, selected) { selected.insert("handheld", false); }
                    }
                    Control::Steam => {
                        let previous = *steam;
                        *steam = (*steam + 1) % STEAM.len();
                        if previous == 0 { selected.insert("gamescope", true); }
                        if *steam == 0 { selected.insert("gamescope", false); }
                        if !handheld_available(*steam, selected) { selected.insert("handheld", false); }
                    }
                    Control::Theme | Control::Transparency | Control::Layout => (),
                    Control::Wallpaper => {
                        let result = (|| -> io::Result<String> {
                            let Some(path) = picker(&mut terminal)? else { return Ok("Picker cancelled.".into()); };
                            let path_text = path.to_str().ok_or_else(|| io::Error::other("Image path is not UTF-8"))?;
                            let text = appearance_command(&["wallpaper", path_text])?;
                            appearance.wallpaper = path;
                            Ok(if text.is_empty() { "Wallpaper saved.".into() } else { text })
                        })();
                        message = match result { Ok(text) => text, Err(error) => error.to_string() };
                    }
                    Control::Monitors => {
                        ratatui::restore();
                        let result = Command::new("hyprmon").status();
                        terminal = ratatui::init();
                        message = match result {
                            Ok(status) if status.success() => "Returned from HyprMon; live/save actions have their own effect.".into(),
                            Ok(status) => format!("HyprMon exited with {status}"),
                            Err(error) if error.kind() == io::ErrorKind::NotFound =>
                                "HyprMon unavailable: install Lua-compatible hyprmon on PATH.\nNixOS: enable services.icewine.monitors with a compatible package.".into(),
                            Err(error) => format!("HyprMon unavailable: could not run hyprmon: {error}"),
                        };
                    }
                    Control::Overwrite => overwrite = !overwrite,
                    Control::Apply if page == 2 => {
                        widget_message = match widgets.save() { Ok(text) => text, Err(error) => error.to_string() };
                    }
                    Control::Apply => return Ok(Some(overwrite)),
                    Control::Cancel => return Ok(None),
                },
                _ => (),
            }
        }
    })();
    ratatui::restore();
    result
}

// Shared confirmations stay in the existing TUI; subprocesses run after restore.
fn confirm(title: &str, lines: Vec<String>) -> io::Result<bool> {
    let mut scroll = 0u16;
    let mut terminal = ratatui::init();
    let result = (|| {
        loop {
            terminal.draw(|frame| {
                if frame.area().width < 80 || frame.area().height < 24 {
                    frame.render_widget(Paragraph::new("Icewine needs an 80 x 24 terminal.\nResize to continue; Esc: cancel."), frame.area());
                    return;
                }
                let block = Block::bordered().title(title).padding(Padding::uniform(1));
                let inner = block.inner(frame.area());
                frame.render_widget(block, frame.area());
                let [body, help] = Layout::vertical([Constraint::Min(1), Constraint::Length(2)]).areas(inner);
                frame.render_widget(Paragraph::new(lines.join("\n"))
                    .wrap(ratatui::widgets::Wrap { trim: false }).scroll((scroll, 0)), body);
                frame.render_widget(Paragraph::new("Up/down: scroll   I: continue\nEsc/Q/Ctrl+C: cancel"), help);
            })?;
            let Event::Key(key) = event::read()? else { continue };
            if key.kind != KeyEventKind::Press { continue; }
            match key.code {
                KeyCode::Esc | KeyCode::Char('q') => return Ok(false),
                KeyCode::Char('c') if key.modifiers.contains(event::KeyModifiers::CONTROL) => return Ok(false),
                _ if terminal.size()?.width < 80 || terminal.size()?.height < 24 => (),
                KeyCode::Down => scroll = scroll.saturating_add(1).min(lines.iter().map(|line| line.len()).sum::<usize>().min(u16::MAX as usize) as u16),
                KeyCode::Up => scroll = scroll.saturating_sub(1),
                KeyCode::Char('i') => return Ok(true),
                _ => (),
            }
        }
    })();
    ratatui::restore();
    result
}

fn bootstrap(directory: &str, revision: &str) -> Result<ExitCode, Box<dyn std::error::Error>> {
    let directory = fs::canonicalize(directory)?;
    if revision.len() != 40 || !revision.bytes().all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
        || fs::read_to_string(directory.join("source-revision"))?.trim() != revision {
        return Err("Invalid prepared source revision".into());
    }
    let archives = fs::read_dir(&directory)?.filter_map(Result::ok).map(|entry| entry.path())
        .filter(|path| path.file_name().is_some_and(|name| {
            let name = name.to_string_lossy();
            name.starts_with("icewine-0.1-1-x86_64.pkg.tar.") && !name.ends_with(".sig")
        })).collect::<Vec<_>>();
    if archives.len() != 1 || !archives[0].is_file() || archives[0].is_symlink() {
        return Err("Expected one regular Icewine base archive; preparation incomplete".into());
    }
    if !confirm(" Icewine onboarding: base package ", vec![
        "Experimental Arch/CachyOS x86_64; installed sessions remain unqualified.".into(),
        format!("Source commit: {revision}"),
        "Prerequisites: full distro upgrade, base-devel, cargo, python; keep a fallback desktop.".into(),
        "Plan: sudo pacman -U the prepared base archive and its runtime dependencies.".into(),
        format!("Archive: {}", archives[0].display()),
        "Pacman will show its transaction and request approval. User configuration is untouched here.".into(),
        "Then choose optional integrations in the installed manager; all begin unchecked on first use.".into(),
        "Cancel retains build/cache files; packages and user configuration remain unchanged.".into(),
    ])? { return Ok(ExitCode::SUCCESS); }
    let status = Command::new("sudo").args(["pacman", "-U"]).arg(&archives[0]).status()?;
    if !status.success() {
        eprintln!("Base installation failed; packages may have changed. Retained archives: {}. Retry this bootstrap or inspect pacman output before proceeding.", directory.display());
        return Ok(ExitCode::FAILURE);
    }
    let status = Command::new("icewine-manage").env("ICEWINE_PACKAGE_DIR", &directory).status()?;
    Ok(if status.success() { ExitCode::SUCCESS } else { ExitCode::FAILURE })
}

fn run() -> Result<ExitCode, Box<dyn std::error::Error>> {
    if !io::stdin().is_terminal() || !io::stdout().is_terminal() {
        return Err("A terminal is required; run icewine manage from a TTY".into());
    }
    let args = std::env::args().collect::<Vec<_>>();
    if args.len() == 4 && args[1] == "--bootstrap" { return bootstrap(&args[2], &args[3]); }
    if args.len() != 1 { return Err("Usage: icewine manage".into()); }
    let output = Command::new("icewine-manage-backend").arg("state").output()?;
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).into_owned().into());
    }
    let state = String::from_utf8(output.stdout)?;
    let mut fields = BTreeMap::new();
    for field in state.split_whitespace() {
        let (id, value) = field.split_once('=').ok_or("Invalid manager state")?;
        if fields.insert(id, value).is_some() { return Err("Duplicate manager field".into()); }
    }
    let mut steam = STEAM.iter().position(|value| fields.get("steam") == Some(value))
        .ok_or("Invalid Steam choice")?;
    fields.remove("steam");
    let mut selected = BTreeMap::new();
    for (id, value) in fields {
        selected.insert(id, match value {
            "true" => true, "false" => false, _ => return Err("Invalid manager state".into()),
        });
    }
    let readonly = selected.remove("readonly").ok_or("Missing read-only state")?;
    if selected.len() + 1 != ROWS.len() || ROWS.iter().any(|(id, _, _)| *id != "steam" && !selected.contains_key(id))
        || (steam == 0 && (selected["gamescope"] || selected["handheld"]))
        || (selected["handheld"] && !handheld_available(steam, &selected)) {
        return Err("Invalid manager selections".into());
    }
    if let Some(overwrite) = choose(readonly, &mut selected, &mut steam)? {
        let choices = ROWS.iter().map(|(id, label, _)| format!("{label}: {}",
            if *id == "steam" { STEAM[steam].to_owned() } else { selected[id].to_string() })).collect::<Vec<_>>();
        let mut plan = vec![if readonly { "NixOS: host packages/services remain declarative; deploy selected user defaults.".into() }
            else { "Install selected packages; configure selected utilities; deselection keeps packages.".into() }];
        plan.push("Create missing shared Quickshell/wallpaper defaults and publish theme outputs.".into());
        plan.extend(choices);
        plan.push(if overwrite { "Overwrite selected defaults WITHOUT backups.".into() }
            else { "Preserve existing dotfiles; create missing defaults. btop selects the Icewine theme in regular configs.".into() });
        plan.push(if readonly { "Host services and device permissions remain in your NixOS configuration.".into() }
            else { "Host prerequisites: services/device permissions; Multilib for native Steam; private packages for Handheld.".into() });
        plan.push("Earlier package/file changes can remain after failure or interruption. Retry Apply after resolving the error.".into());
        plan.push("Cancel leaves utility choices unapplied; earlier Appearance changes remain.".into());
        if !confirm(" Icewine: planned changes ", plan)? { return Ok(ExitCode::SUCCESS); }
        let status = Command::new("icewine-manage-backend").arg("apply")
            .args(selected.iter().map(|(id, value)| format!("{id}={value}")))
            .arg(format!("steam={}", STEAM[steam]))
            .arg(format!("overwrite={overwrite}")).status()?;
        return Ok(if status.success() { ExitCode::SUCCESS } else { ExitCode::FAILURE });
    }
    Ok(ExitCode::SUCCESS)
}

fn main() -> ExitCode {
    match run() {
        Ok(code) => code,
        Err(error) => { eprintln!("Icewine: {error}"); ExitCode::FAILURE }
    }
}
