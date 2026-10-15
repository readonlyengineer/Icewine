use std::{collections::BTreeMap, fs::{self, OpenOptions}, io, os::unix::fs::OpenOptionsExt, path::PathBuf, process::{Command, ExitCode}};
use crossterm::event::{self, Event, KeyCode, KeyEventKind};
use ratatui::{layout::Flex, prelude::*, widgets::{Block, BorderType, Cell, Padding, Paragraph, Row, Table}};

const ROWS: &[(&str, &str, &str)] = &[
    ("desktop", "Desktop session", "Hyprland + Icewine Quickshell"),
    ("terminal", "Terminal", "Kitty"),
    ("filemanager", "File manager", "Yazi"),
    ("steam", "Steam (unfree)", ""),
    ("gamescope", " +- Gamescope", ""), ("handheld", " \u{005c}- Handheld", "Requires Desktop Session, Steam native, and Gamescope"),
    ("login", "Login screen", "SDDM"), ("shellExtras", "Shell Extras", "Starship + Fastfetch + btop theme"),
];

#[derive(Clone, Copy, PartialEq)]
enum Control { Theme, Transparency, Wallpaper, Inherit, AuthWallpaper, Monitors, Utility(&'static str), Widget(usize), Steam, Overwrite, Apply, Cancel }

const STEAM: &[&str] = &["none", "native", "flatpak"];

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
    wallpaper: PathBuf, auth: Option<PathBuf>,
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
        let data = std::env::var_os("ICEWINE_WALLPAPER_DATA_HOME")
            .or_else(|| std::env::var_os("XDG_DATA_HOME")).map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from(std::env::var_os("HOME").unwrap_or_default()).join(".local/share"));
        let directory = data.join("icewine/wallpapers");
        let wallpaper = if directory.join("selection.img").is_file() { directory.join("selection.img") }
            else { data.join("wallpapers/default.jpg") };
        let auth = directory.join("auth.img");
        Ok(Self { themes, theme, policy, transparency, wallpaper, auth: auth.is_file().then_some(auth) })
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
                *steam != 0 || !matches!(*id, "gamescope" | "handheld")).collect();
            let controls: Vec<_> = if page == 1 {
                let mut controls = Vec::new();
                if !appearance.policy { controls.push(Control::Theme); }
                controls.extend([Control::Transparency, Control::Wallpaper, Control::Inherit]);
                if appearance.auth.is_some() { controls.push(Control::AuthWallpaper); }
                controls.extend([Control::Monitors, Control::Apply, Control::Cancel]);
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
                let [panel] = Layout::horizontal([Constraint::Max(90)])
                    .flex(Flex::Center).areas(frame.area());
                let [panel] = Layout::vertical([Constraint::Max(ROWS.len() as u16 + 15)])
                    .flex(Flex::Center).areas(panel);
                let block = Block::bordered().border_type(BorderType::Rounded)
                    .border_style(muted).title(Line::from(match page {
                        0 => " Icewine Installer (1/3) | Tab: Appearance ",
                        1 => " Icewine Appearance (2/3) | Tab: Widgets ",
                        _ => " Icewine Widgets (3/3) | Tab: Installer ",
                    }).style(accent))
                    .padding(Padding::uniform(1));
                let inner = block.inner(panel);
                frame.render_widget(block, panel);
                let [intro, utilities, reset, buttons, help] = Layout::vertical([
                    Constraint::Length(4), Constraint::Length(ROWS.len() as u16 + 2),
                    Constraint::Length(2), Constraint::Length(2), Constraint::Length(1),
                ]).areas(inner);
                frame.render_widget(Paragraph::new(vec![
                    Line::from("Optional utilities, configured for Icewine."),
                    Line::from("Selected utilities are installed and configured.").style(muted),
                    Line::from(if readonly {
                        "NixOS: utility selections are read-only."
                    } else {
                        "Deselecting removes Icewine configuration; packages stay installed."
                    }).style(muted),
                ]), intro);
                if page == 1 {
                    frame.render_widget(Paragraph::new(vec![
                        Line::from("Appearance updates immediately."),
                        Line::from("Apply/Cancel here control utility choices only.").style(muted),
                        Line::from("HyprMon live/save changes remain after Cancel.").style(muted),
                    ]), intro);
                    let settings = vec![
                        (Control::Theme, "Theme", format!("< {} >{}", appearance.themes[appearance.theme], if appearance.policy { " (Nix policy)" } else { "" })),
                        (Control::Transparency, "Transparency", format!("< {} >", TRANSPARENCY[appearance.transparency])),
                        (Control::Wallpaper, "Wallpaper", format!("[ {} ]", filename(&appearance.wallpaper))),
                        (Control::Inherit, "Lockscreen Wallpaper", (if appearance.auth.is_none() { "Wallpaper [x]" } else { "Wallpaper [ ]" }).to_owned()),
                        (Control::AuthWallpaper, "Separate image", appearance.auth.as_ref().map(|path| format!("[ {} ]", filename(path))).unwrap_or_default()),
                        (Control::Monitors, "Monitors", "[ Configure monitors… ]".to_owned()),
                    ];
                    frame.render_widget(Table::new(settings.into_iter().filter(|(control, _, _)|
                        *control != Control::AuthWallpaper || appearance.auth.is_some()).map(|(control, label, value)|
                        Row::new([Cell::from(label), Cell::from(value)]).style(if controls[focus] == control { focused }
                            else if control == Control::Theme && appearance.policy { muted } else { Style::default() })),
                        [Constraint::Length(23), Constraint::Min(20)]).column_spacing(2), utilities);
                    frame.render_widget(Paragraph::new(message.chars().map(|c| if c.is_control() && c != '\n' { '?' } else { c }).collect::<String>()).style(accent), reset);
                } else if page == 2 {
                    frame.render_widget(Paragraph::new(vec![
                        Line::from("First-party widgets; no plugin loading."),
                        Line::from("Save commits widgets only; Cancel/Esc discards drafts.").style(muted),
                        Line::from("Installer drafts stay pending; appearance stays live.").style(muted),
                        Line::from(if widgets.supported { "Saved preferences apply live and survive session restart." }
                            else { "Unavailable: restore shipped settings/entry via Installer." }).style(muted),
                    ]), intro);
                    frame.render_widget(Table::new(WIDGETS.iter().enumerate().map(|(index, (_, label, description))| {
                        Row::new([Cell::from(*label), Cell::from(*description),
                            Cell::from(format!("[{}]{}", if !widgets.supported { "?" } else if widgets.enabled[index] { "x" } else { " " },
                                if widgets.policy[index] { " Nix policy" } else if !widgets.supported { " unavailable" } else { "" }))])
                            .style(if controls[focus] == Control::Widget(index) { focused }
                                else if widgets.policy[index] || !widgets.supported { muted } else { Style::default() })
                    }), [Constraint::Length(20), Constraint::Min(10), Constraint::Length(16)]).column_spacing(1), utilities);
                    frame.render_widget(Paragraph::new(widget_message.chars().map(|c| if c.is_control() && c != '\n' { '?' } else { c }).collect::<String>()).style(accent), reset);
                } else {
                let rows = rows.iter().map(|(id, purpose, defaults)| {
                    let available = *id != "handheld" || handheld_available(*steam, selected);
                    Row::new(vec![
                        Cell::from(*purpose),
                        Cell::from(*defaults).style(muted),
                        Cell::from(Line::from(if *id == "steam" { format!("< {} >", STEAM[*steam]) }
                            else { (if selected[id] { "[x]" } else { "[ ]" }).to_owned() }).right_aligned())
                            .style(if readonly || !available { muted } else { accent }),
                    ]).style(if controls[focus] == (if *id == "steam" { Control::Steam } else { Control::Utility(id) }) { focused } else { Style::default() })
                });
                frame.render_widget(Table::new(rows, [
                    Constraint::Length(18), Constraint::Min(20), Constraint::Length(11),
                ]).column_spacing(2).header(Row::new([
                    Cell::from("Utility"), Cell::from("Contains"),
                    Cell::from(Line::from("Configure").right_aligned()),
                ]).style(accent)), utilities);
                frame.render_widget(Paragraph::new(format!("[{}] Overwrite existing dotfiles",
                    if overwrite { "x" } else { " " }))
                    .style(if controls[focus] == Control::Overwrite { focused } else { Style::default() }), reset);
                }
                frame.render_widget(Paragraph::new(Line::from(vec![
                    Span::styled(if page == 2 { "[ Save ]" } else { "[ Apply ]" }, if controls[focus] == Control::Apply { focused } else if page == 2 && !widgets.supported { muted } else { accent }),
                    Span::raw("   "),
                    Span::styled("[ Cancel ]", if controls[focus] == Control::Cancel { focused } else { muted }),
                ])), buttons);
                frame.render_widget(Paragraph::new(
                    if page == 0 { "Tab: page   Up/down: move   Left/right: Steam   Space/Enter: act   Esc: cancel" }
                    else { "Tab: page   Up/down: move   Left/right: cycle   Space/Enter: act   Esc: cancel" }
                ).style(muted), help);
            })?;
            let Event::Key(key) = event::read()? else { continue };
            if key.kind != KeyEventKind::Press { continue; }
            match key.code {
                KeyCode::Tab => { focuses[page] = focus; page = (page + 1) % 3; focus = focuses[page]; }
                KeyCode::Esc | KeyCode::Char('q') => return Ok(None),
                KeyCode::Char('c') if key.modifiers.contains(event::KeyModifiers::CONTROL) => return Ok(None),
                KeyCode::Left | KeyCode::Right if matches!(controls[focus], Control::Theme | Control::Transparency) => {
                    let (values, current, command) = if controls[focus] == Control::Theme {
                        (appearance.themes.iter().map(String::as_str).collect::<Vec<_>>(), appearance.theme, "theme")
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
                    Control::Theme | Control::Transparency => (),
                    Control::Wallpaper | Control::AuthWallpaper | Control::Inherit => {
                        let result = (|| -> io::Result<String> {
                            if controls[focus] == Control::Inherit && appearance.auth.is_some() {
                                let text = appearance_command(&["wallpaper", "--auth-reset"])?;
                                appearance.auth = None;
                                return Ok(text);
                            }
                            let Some(path) = picker(&mut terminal)? else { return Ok("Picker cancelled.".into()); };
                            let path_text = path.to_str().ok_or_else(|| io::Error::other("Image path is not UTF-8"))?;
                            let auth = controls[focus] != Control::Wallpaper;
                            let text = if auth { appearance_command(&["wallpaper", "--auth", path_text]) } else { appearance_command(&["wallpaper", path_text]) }?;
                            if auth { appearance.auth = Some(path); } else { appearance.wallpaper = path; }
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

fn run() -> Result<ExitCode, Box<dyn std::error::Error>> {
    if std::env::args().len() != 1 { return Err("Usage: icewine manage".into()); }
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
