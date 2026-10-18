use std::{collections::BTreeMap, fs::{self, OpenOptions}, io::{self, IsTerminal}, os::unix::fs::OpenOptionsExt, path::PathBuf, process::{Command, ExitCode}};
use crossterm::event::{self, Event, KeyCode, KeyEventKind};
use ratatui::{layout::Flex, prelude::*, widgets::{Block, BorderType, Cell, Padding, Paragraph, Row, Table, TableState, Wrap}};

const ROWS: &[(&str, &str, &str)] = &[
    ("desktop", "Desktop session", "Hyprland + Icewine Quickshell"),
    ("terminal", "Terminal", "Kitty"),
    ("filemanager", "File manager", "Yazi"),
    ("steam", "Steam (unfree)", ""),
    ("gamescope", " +- Gamescope", ""), ("handheld", " \u{005c}- Handheld", "Needs Desktop + native Steam + Gamescope"),
    ("login", "Login styling", "tuigreet (host configuration)"), ("shellExtras", "Shell Extras", "Starship + Fastfetch + btop theme"),
];

#[derive(Clone, Copy, PartialEq)]
enum Control { Theme, Transparency, Layout, Wallpaper, Monitors, Utility(&'static str), Widget(usize), Bar(usize), BarWidth, Card(usize), Steam, Overwrite, Apply, Cancel }

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
    layout: usize, wallpaper: PathBuf, readonly: [bool; 5],
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
        let ownership = widget_command(&["file-state".into()])?;
        let mut fields = BTreeMap::new();
        for field in ownership.split_whitespace() {
            let (name, value) = field.split_once('=').ok_or_else(|| io::Error::other("Invalid file ownership"))?;
            if fields.insert(name, value).is_some() { return Err(io::Error::other("Duplicate file ownership")); }
        }
        let mut readonly = [false; 5];
        for (index, name) in ["theme", "transparency", "wallpaper", "monitors", "layout"].iter().enumerate() {
            readonly[index] = match fields.remove(name) {
                Some("true") => true, Some("false") => false,
                _ => return Err(io::Error::other("Missing file ownership")),
            };
        }
        if !fields.is_empty() { return Err(io::Error::other("Unknown file ownership")); }
        Ok(Self { themes, theme, policy, transparency, layout, wallpaper, readonly })
    }
}

const WIDGETS: &[(&str, &str, &str)] = &[
    ("notificationToasts", "Notification toasts", "Popup cards; history and sounds stay"),
    ("windowSwitcher", "Window switcher", "Optional window list and shortcut"),
];

const BAR_SETTINGS: &[(&str, &str, &[&str], &[&str])] = &[
    ("barBehaviour", "Bar Behaviour", &["keyboard", "keyboard-mouse", "toggle", "always"],
        &["Autohide (Keyboard)", "Autohide (Keyboard & Mouse)", "Toggle (Keyboard)", "Always Show"]),
    ("barLocation", "Bar Locations", &["above", "top", "bottom"], &["Above", "Top", "Bottom"]),
    ("barStyle", "Bar Style", &["anchored", "floating"], &["Anchored", "Floating"]),
    ("oskAccess", "Onscreen Keyboard Access", &["none", "launcher", "topbar"], &["None", "Launcher", "Topbar"]),
];

const CARD_MODULES: &[&str] = &["launcher", "background", "layout", "media", "audio", "bluetooth",
    "clipboard", "network", "tailscale", "ssh", "notifications", "battery", "performance"];

struct CardStack { id: String, modules: Vec<usize> }

struct Widgets {
    enabled: [bool; 2], policy: [bool; 8], linked: [bool; 8], supported: bool, revision: String,
    stacks: Vec<CardStack>, bar: [usize; 4], width: u8,
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
        let mut policy = [false; 8];
        let mut linked = [false; 8];
        for (index, (id, _, _)) in WIDGETS.iter().enumerate() {
            let (value, owner) = fields.remove(id).and_then(|value| value.split_once(':'))
                .ok_or_else(|| io::Error::other("Missing widget state"))?;
            enabled[index] = boolean(Some(value))?;
            policy[index] = match owner { "policy" | "symlink" => true, "user" => false,
                _ => return Err(io::Error::other("Invalid widget ownership")) };
            linked[index] = owner == "symlink";
        }
        let (value, owner) = fields.remove("cardStacks").and_then(|value| value.split_once(':'))
            .ok_or_else(|| io::Error::other("Missing card stacks"))?;
        policy[2] = match owner { "policy" | "symlink" => true, "user" => false,
            _ => return Err(io::Error::other("Invalid card ownership")) };
        linked[2] = owner == "symlink";
        let mut stacks: Vec<CardStack> = Vec::new();
        let mut seen = Vec::new();
        for entry in value.split(';').filter(|_| !value.is_empty()) {
            let (id, members) = entry.split_once('/').ok_or_else(|| io::Error::other("Invalid card stack"))?;
            if id.is_empty() || id.len() > 32 || !id.as_bytes()[0].is_ascii_lowercase()
                || !id.bytes().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'-')
                || stacks.iter().any(|stack| stack.id == id) {
                return Err(io::Error::other("Invalid card stack ID"));
            }
            let mut modules = Vec::new();
            for name in members.split(',') {
                let index = CARD_MODULES.iter().position(|module| *module == name)
                    .filter(|index| !seen.contains(index)).ok_or_else(|| io::Error::other("Invalid card module"))?;
                seen.push(index);
                modules.push(index);
            }
            stacks.push(CardStack { id: id.to_owned(), modules });
        }
        let mut bar = [0; 4];
        for (index, (id, _, choices, _)) in BAR_SETTINGS.iter().enumerate() {
            let (value, owner) = fields.remove(id).and_then(|value| value.split_once(':'))
                .ok_or_else(|| io::Error::other("Missing bar setting"))?;
            bar[index] = choices.iter().position(|choice| *choice == value)
                .ok_or_else(|| io::Error::other("Invalid bar setting"))?;
            policy[index + 3] = match owner { "policy" | "symlink" => true, "user" => false,
                _ => return Err(io::Error::other("Invalid bar ownership")) };
            linked[index + 3] = owner == "symlink";
        }
        let (value, owner) = fields.remove("barWidth").and_then(|value| value.split_once(':'))
            .ok_or_else(|| io::Error::other("Missing bar width"))?;
        let width = value.parse::<u8>().ok().filter(|width| (50..=100).contains(width) && value == width.to_string())
            .ok_or_else(|| io::Error::other("Invalid bar width"))?;
        policy[7] = match owner { "policy" | "symlink" => true, "user" => false,
            _ => return Err(io::Error::other("Invalid bar width ownership")) };
        linked[7] = owner == "symlink";
        if !fields.is_empty() { return Err(io::Error::other("Unknown widget state")); }
        Ok(Self { enabled, policy, linked, supported, revision, stacks, bar, width })
    }

    fn location(&self, module: usize) -> Option<(usize, usize)> {
        self.stacks.iter().enumerate().find_map(|(stack, value)|
            value.modules.iter().position(|index| *index == module).map(|position| (stack, position)))
    }

    fn remove(&mut self, module: usize) {
        if let Some((stack, position)) = self.location(module) {
            self.stacks[stack].modules.remove(position);
            self.stacks.retain(|stack| !stack.modules.is_empty());
        }
    }

    fn new_stack(&mut self, module: usize) {
        self.remove(module);
        let id = (1..).map(|index| format!("stack-{index}"))
            .find(|id| self.stacks.iter().all(|stack| stack.id != *id)).unwrap();
        self.stacks.push(CardStack { id, modules: vec![module] });
    }

    fn edit(&mut self, module: usize, key: KeyCode) {
        if !self.supported || self.policy[2] { return; }
        match key {
            KeyCode::Char(' ') | KeyCode::Enter => {
                if self.location(module).is_some() { self.remove(module); } else { self.new_stack(module); }
            }
            KeyCode::Char('n') => self.new_stack(module),
            KeyCode::Left | KeyCode::Right => {
                // Capture the destination ID before removing a possibly singleton source.
                let next = match self.location(module) {
                    Some((stack, _)) if key == KeyCode::Right => (stack + 1) % self.stacks.len(),
                    Some((stack, _)) => (stack + self.stacks.len() - 1) % self.stacks.len(),
                    None => 0,
                };
                if let Some(target) = self.stacks.get(next).map(|stack| stack.id.clone()) {
                    if self.location(module).is_some_and(|(stack, _)| self.stacks[stack].id == target) { return; }
                    self.remove(module);
                    self.stacks.iter_mut().find(|stack| stack.id == target).unwrap().modules.push(module);
                } else { self.new_stack(module); }
            }
            KeyCode::Char('+') | KeyCode::Char('-') => {
                if let Some((stack, position)) = self.location(module) {
                    let members = &mut self.stacks[stack].modules;
                    let next = if key == KeyCode::Char('+') { (position + 1).min(members.len() - 1) }
                        else { position.saturating_sub(1) };
                    members.swap(position, next);
                }
            }
            KeyCode::Char('[') | KeyCode::Char(']') => {
                if let Some((stack, _)) = self.location(module) {
                    let next = if key == KeyCode::Char(']') { (stack + 1).min(self.stacks.len() - 1) }
                        else { stack.saturating_sub(1) };
                    self.stacks.swap(stack, next);
                }
            }
            KeyCode::Delete => { if let Some((stack, _)) = self.location(module) { self.stacks.remove(stack); } }
            _ => (),
        }
    }

    fn save(&mut self) -> io::Result<String> {
        let mut args = vec!["widgets-apply".into(), format!("revision={}", self.revision)];
        args.extend(WIDGETS.iter().enumerate().map(|(index, (id, _, _))| format!("{id}={}", self.enabled[index])));
        args.push(format!("cardStacks={}", self.stacks.iter().map(|stack|
            format!("{}/{}", stack.id, stack.modules.iter().map(|index| CARD_MODULES[*index]).collect::<Vec<_>>().join(",")))
            .collect::<Vec<_>>().join(";")));
        args.extend(BAR_SETTINGS.iter().enumerate().map(|(index, (id, _, choices, _))|
            format!("{id}={}", choices[self.bar[index]])));
        args.push(format!("barWidth={}", self.width));
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
        Err(error) => (Widgets { enabled: [true; 2], policy: [true; 8], linked: [false; 8], supported: false, revision: String::new(), stacks: Vec::new(), bar: [0; 4], width: 80 }, error.to_string()),
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
                for (index, control) in [Control::Theme, Control::Transparency, Control::Wallpaper, Control::Monitors, Control::Layout].into_iter().enumerate() {
                    if !appearance.readonly[index] && !(control == Control::Theme && appearance.policy) { controls.push(control); }
                }
                controls.extend([Control::Apply, Control::Cancel]);
                controls
            } else if page == 2 {
                WIDGETS.iter().enumerate().filter(|(index, _)| widgets.supported && !widgets.policy[*index])
                    .map(|(index, _)| Control::Widget(index))
                    .chain((0..BAR_SETTINGS.len()).filter(|index| widgets.supported && !widgets.policy[index + 3]).map(Control::Bar))
                    .chain((widgets.supported && !widgets.policy[7]).then_some(Control::BarWidth))
                    .chain((0..CARD_MODULES.len()).map(Control::Card))
                    .chain((widgets.supported && widgets.policy.iter().any(|locked| !locked)).then_some(Control::Apply)).chain([Control::Cancel]).collect()
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
                        Row::new([Cell::from(label), Cell::from(value + if !controls.contains(&control) && !(control == Control::Theme && appearance.policy) { " (symlink/read-only)" } else { "" })]).bottom_margin(u16::from(control != Control::Layout)).style(if controls[focus] == control { focused }
                            else if !controls.contains(&control) { muted } else { Style::default() })),
                        [Constraint::Length(23), Constraint::Min(20)]).column_spacing(2), utilities);
                    frame.render_widget(Paragraph::new(message.chars().map(|c| if c.is_control() && c != '\n' { '?' } else { c }).collect::<String>()).style(accent).wrap(Wrap { trim: false }), reset);
                } else if page == 2 {
                    frame.render_widget(Paragraph::new(vec![
                        Line::from("First member: topbar icon; accents: primary/secondary/tertiary, repeat.").style(accent),
                        Line::from("Save commits widgets only; Cancel/Esc discards drafts.").style(muted),
                        Line::from("Space: enable/disable  Left/right: move to stack  n: new stack").style(muted),
                        Line::from(if widgets.linked.iter().any(|linked| *linked) { "Symlinked preferences are read-only." }
                            else if widgets.supported { "+/-: member order  [/]: stack order  Delete: remove stack" }
                            else { "Unavailable: restore shipped settings/entry via Installer." }).style(muted),
                    ]), intro);
                    let owner = |index| if widgets.linked[index] { " symlink/read-only" }
                        else if widgets.policy[index] { " Nix policy" } else { "" };
                    let mut entries: Vec<_> = WIDGETS.iter().enumerate().map(|(index, (_, label, _))|
                        (Control::Widget(index), (*label).to_owned(), format!("[{}]{}",
                            if !widgets.supported { "?" } else if widgets.enabled[index] { "x" } else { " " }, owner(index)))).collect();
                    entries.extend(BAR_SETTINGS.iter().enumerate().map(|(index, (_, label, _, labels))|
                        (Control::Bar(index), (*label).to_owned(), if widgets.supported {
                            format!("< {} >{}", labels[widgets.bar[index]], owner(index + 3))
                        } else { "Unavailable".to_owned() })));
                    entries.push((Control::BarWidth, "Bar Width".to_owned(), if widgets.supported {
                        format!("< {}% >{}", widgets.width, owner(7))
                    } else { "Unavailable".to_owned() }));
                    entries.extend(CARD_MODULES.iter().enumerate().map(|(index, name)| {
                        let value = if !widgets.supported { "Unavailable".to_owned() }
                            else if let Some((stack, position)) = widgets.location(index) {
                                format!("{}. {} / {}{} ({})", stack + 1, widgets.stacks[stack].id, position + 1,
                                    if position == 0 { " icon" } else { "" }, ["primary", "secondary", "tertiary"][position % 3])
                            } else { "Disabled".to_owned() };
                        (Control::Card(index), (*name).to_owned(), value + owner(2))
                    }));
                    let selected = entries.iter().position(|(control, _, _)| *control == controls[focus]);
                    let mut table_state = TableState::default().with_selected(selected);
                    // Keep the focused row visible in the existing 80 x 24 minimum.
                    *table_state.offset_mut() = selected.unwrap_or(0).saturating_sub(utilities.height.saturating_sub(1) as usize);
                    frame.render_stateful_widget(Table::new(entries.into_iter().map(|(control, label, value)|
                        Row::new([Cell::from(label), Cell::from(value)]).style(if controls[focus] == control { focused }
                            else if !widgets.supported || match control { Control::Widget(index) => widgets.policy[index], Control::Bar(index) => widgets.policy[index + 3], Control::BarWidth => widgets.policy[7], _ => widgets.policy[2] } { muted }
                            else { Style::default() })), [Constraint::Length(25), Constraint::Min(20)]).column_spacing(1), utilities, &mut table_state);
                    frame.render_widget(Paragraph::new(widget_message.chars().map(|c| if c.is_control() && c != '\n' { '?' } else { c }).collect::<String>()).style(accent).wrap(Wrap { trim: false }), reset);
                } else {
                frame.render_widget(Paragraph::new(vec![
                    Line::from("Optional utilities, configured for Icewine.").style(accent),
                    Line::from("Selected utilities are installed and configured.").style(muted),
                    Line::from(if readonly {
                        "Utility selections are read-only (host policy or symlink)."
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
                    Span::styled(if page == 2 { "[ Save ]" } else { "[ Apply ]" }, if controls[focus] == Control::Apply { focused } else if page == 2 && (!widgets.supported || widgets.policy.iter().all(|locked| *locked)) { muted } else { accent }),
                    Span::raw("   "),
                    Span::styled("[ Cancel ]", if controls[focus] == Control::Cancel { focused } else { muted }),
                ])), buttons);
                frame.render_widget(Paragraph::new(vec![
                    Line::from("Tab: page   Up/down: move   Shift-Tab: previous control"),
                    Line::from(if page == 0 { "Left/right: Steam   Space/Enter: act   Esc: cancel" }
                        else if page == 1 { "Left/right: cycle   Space/Enter: act   Esc: cancel" }
                        else { "Space/Enter: act   s: Save   Esc: cancel" }),
                ]).style(muted), help);
            })?;
            let Event::Key(key) = event::read()? else { continue };
            if key.kind != KeyEventKind::Press { continue; }
            match key.code {
                KeyCode::Esc | KeyCode::Char('q') => return Ok(None),
                KeyCode::Char('c') if key.modifiers.contains(event::KeyModifiers::CONTROL) => return Ok(None),
                _ if terminal.size()?.width < 80 || terminal.size()?.height < 24 => (),
                KeyCode::Char('s') if page == 2 && widgets.supported && widgets.policy.iter().any(|locked| !locked) => {
                    widget_message = match widgets.save() { Ok(text) => text, Err(error) => error.to_string() };
                }
                KeyCode::Left | KeyCode::Right | KeyCode::Char('n' | '+' | '-' | '[' | ']') | KeyCode::Delete
                    if matches!(controls[focus], Control::Card(_)) => {
                    if let Control::Card(index) = controls[focus] { widgets.edit(index, key.code); }
                }
                KeyCode::Left | KeyCode::Right if controls[focus] == Control::BarWidth => {
                    widgets.width = if key.code == KeyCode::Right { (widgets.width + 1).min(100) }
                        else { widgets.width.saturating_sub(1).max(50) };
                }
                KeyCode::Left | KeyCode::Right if matches!(controls[focus], Control::Bar(_)) => {
                    if let Control::Bar(index) = controls[focus] {
                        let count = BAR_SETTINGS[index].2.len();
                        widgets.bar[index] = (widgets.bar[index] + if key.code == KeyCode::Right { 1 } else { count - 1 }) % count;
                    }
                }
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
                            appearance.readonly = updated.readonly;
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
                    Control::BarWidth => widgets.width = (widgets.width + 1).min(100),
                    Control::Bar(index) => widgets.bar[index] = (widgets.bar[index] + 1) % BAR_SETTINGS[index].2.len(),
                    Control::Card(index) => widgets.edit(index, key.code),
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
                        appearance = Appearance::load()?;
                        if appearance.readonly[3] {
                            message = "Monitor configuration is now symlinked/read-only.".into();
                            continue;
                        }
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
        let mut plan = vec![if readonly { "Host packages/services remain unchanged; deploy selected user defaults.".into() }
            else { "Install selected packages; configure selected utilities; deselection keeps packages.".into() }];
        plan.push("Create missing shared Quickshell/wallpaper defaults and publish theme outputs.".into());
        plan.extend(choices);
        plan.push(if overwrite { "Overwrite selected defaults WITHOUT backups.".into() }
            else { "Preserve existing dotfiles; create missing defaults. btop selects the Icewine theme in regular configs.".into() });
        plan.push(if readonly { "Host services and device permissions remain host policy.".into() }
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
