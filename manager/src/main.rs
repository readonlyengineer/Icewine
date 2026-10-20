use std::{collections::BTreeMap, fs::{self, OpenOptions}, io::{self, IsTerminal}, os::unix::fs::OpenOptionsExt, path::PathBuf, process::{Command, ExitCode}};
use crossterm::event::{self, Event, KeyCode, KeyEventKind};
use ratatui::{prelude::*, widgets::{Block, BorderType, Paragraph, Wrap}};

const ROWS: &[(&str, &str, &str)] = &[
    ("desktop", "Desktop session", "Hyprland + Quickshell"), ("terminal", "Terminal", "Kitty"),
    ("filemanager", "File manager", "Yazi"), ("texteditor", "Terminal Editor", "Neovim + LazyVIM"),
    ("shellExtras", "Shell extras", "Starship / Fastfetch"), ("screenshot", "Screenshots", "Gradia (Flatpak/Flathub)"),
    ("media", "Pictures and Video", "imv, VLC (Flatpak/Flathub)"),
    ("steam", "Steam", ""), ("gamescope", "Gamescope", "Nested Steam session"),
    ("handheld", "Handheld", "Handheld UI"), ("login", "Login styling", "Host configuration"),
];
#[derive(Clone, Copy, PartialEq)]
enum Control { Theme, Preview(usize), Taskbar, Transparency, Layout, Wallpaper, Monitors,
    Utility(&'static str), Widget(usize), Bar(usize), BarWidth, Back, Card(usize), Stack(usize),
    GridAction(usize), GridTools, Hotkeys, DefaultRole(usize), DefaultChoice(usize), Steam, Overwrite, Apply }

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

const DEFAULT_ROLES: &[&str] = &["Browser", "Terminal", "File manager", "Text files", "PDFs", "Images", "Videos", "Audio"];
struct DefaultApp { readonly: bool, revision: String, label: String, current: String, choices: Vec<(String, String)> }
fn default_text(hex: &str) -> io::Result<String> {
    if hex.len() % 2 != 0 || !hex.bytes().all(|c| c.is_ascii_hexdigit()) { return Err(io::Error::other("Invalid default application text")); }
    let bytes = (0..hex.len()).step_by(2).map(|i| u8::from_str_radix(&hex[i..i + 2], 16).map_err(io::Error::other)).collect::<io::Result<Vec<_>>>()?;
    let value = String::from_utf8(bytes).map_err(io::Error::other)?;
    if value.chars().any(char::is_control) { return Err(io::Error::other("Invalid default application text")); }
    Ok(value)
}
impl DefaultApp {
    fn load() -> io::Result<Vec<Self>> {
        let text = widget_command(&["default-apps-state".into()])?;
        let mut result = Vec::new();
        for (index, line) in text.lines().enumerate() {
            let fields: Vec<_> = line.split('\t').collect();
            if fields.len() != 6 || fields[0] != index.to_string() || index >= DEFAULT_ROLES.len()
                || fields[2].len() != 64 || !fields[2].bytes().all(|c| c.is_ascii_hexdigit()) {
                return Err(io::Error::other("Invalid default application state"));
            }
            let readonly = match fields[1] { "true" => true, "false" => false, _ => return Err(io::Error::other("Invalid default application ownership")) };
            let mut choices = Vec::new();
            for pair in fields[5].split(',') {
                let (id, label) = pair.split_once(':').ok_or_else(|| io::Error::other("Invalid application choice"))?;
                let (id, label) = (default_text(id)?, default_text(label)?);
                if id.is_empty() || label.is_empty() || choices.iter().any(|(previous, _)| previous == &id) {
                    return Err(io::Error::other("Invalid application choice"));
                }
                choices.push((id, label));
            }
            if choices.last().map(|pair| pair.0.as_str()) != Some("@unset") { return Err(io::Error::other("Missing unset application choice")); }
            result.push(Self { readonly, revision: fields[2].into(), label: default_text(fields[3])?, current: default_text(fields[4])?, choices });
        }
        if result.len() != DEFAULT_ROLES.len() { return Err(io::Error::other("Missing default application roles")); }
        Ok(result)
    }
    fn save(&self, role: usize, choice: usize) -> io::Result<String> {
        widget_command(&["default-apps-apply".into(), self.revision.clone(), role.to_string(), self.choices[choice].0.clone()])
    }
}
// The accepted reference clips a row rather than moving the following rows.
fn default_clip(text: &str, width: usize) -> String {
    if Line::from(text).width() <= width { return text.into(); }
    let mut value = String::new();
    for character in text.chars() {
        if Line::from(format!("{value}{character}…")).width() > width { break; }
        value.push(character);
    }
    value + "…"
}

struct Appearance {
    themes: Vec<String>, theme: usize, policy: bool, transparency: usize,
    layout: usize, wallpaper: PathBuf, readonly: [bool; 5],
}

impl Appearance {
    fn load() -> io::Result<Self> {
        let response = widget_command(&["appearance-state".into()])?;
        let mut fields = BTreeMap::new();
        for field in response.split_whitespace() {
            let (name, value) = field.split_once('=').ok_or_else(|| io::Error::other("Invalid appearance state"))?;
            if fields.insert(name, value).is_some() { return Err(io::Error::other("Duplicate appearance field")); }
        }
        let themes: Vec<String> = fields.remove("themes").unwrap_or_default().split(',').map(str::to_owned).collect();
        if themes.iter().any(|id| id.is_empty() || !id.bytes().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'-')
            || !id.as_bytes()[0].is_ascii_alphanumeric()) || themes.windows(2).any(|pair| pair[0] >= pair[1]) {
            return Err(io::Error::other("Invalid installed themes"));
        }
        let theme = fields.remove("selected").and_then(|selected| themes.iter().position(|value| value == selected))
            .ok_or_else(|| io::Error::other("Invalid effective theme"))?;
        let policy = match fields.remove("policy") {
            Some("true") => true, Some("false") => false,
            _ => return Err(io::Error::other("Invalid theme policy")),
        };
        let transparency = fields.remove("level").and_then(|selected| TRANSPARENCY.iter().position(|value| *value == selected))
            .ok_or_else(|| io::Error::other("Invalid transparency"))?;
        let layout = fields.remove("desktopLayout").and_then(|selected| LAYOUTS.iter().position(|value| *value == selected))
            .ok_or_else(|| io::Error::other("Invalid layout"))?;
        let data = std::env::var_os("ICEWINE_WALLPAPER_DATA_HOME")
            .or_else(|| std::env::var_os("XDG_DATA_HOME")).map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from(std::env::var_os("HOME").unwrap_or_default()).join(".local/share"));
        let directory = data.join("icewine/wallpapers");
        let wallpaper = if directory.join("selection.img").is_file() { directory.join("selection.img") }
            else { data.join("wallpapers/default.jpg") };
        let mut readonly = [false; 5];
        for (index, name) in ["theme", "transparency", "wallpaper", "monitors", "layout"].iter().enumerate() {
            readonly[index] = match fields.remove(name) {
                Some("true") => true, Some("false") => false,
                _ => return Err(io::Error::other("Missing file ownership")),
            };
        }
        if !fields.is_empty() { return Err(io::Error::other("Unknown appearance field")); }
        Ok(Self { themes, theme, policy, transparency, layout, wallpaper, readonly })
    }
}

struct HotkeyAction { id: String, categories: Vec<String>, label: String, kind: String, available: bool }
struct HotkeySettings { actions: Vec<HotkeyAction>, values: Vec<String>, revision: String, readonly: bool, live: bool }
impl HotkeySettings {
    fn load() -> io::Result<Self> {
        let text = widget_command(&["hotkeys-state".into()])?;
        let mut lines = text.lines();
        let mut fields = BTreeMap::new();
        for field in lines.next().unwrap_or("").split_whitespace() {
            let (name, value) = field.split_once('=').ok_or_else(|| io::Error::other("Invalid hotkey state"))?;
            if fields.insert(name, value).is_some() { return Err(io::Error::other("Duplicate hotkey field")); }
        }
        let readonly = match fields.remove("readonly") { Some("true") => true, Some("false") => false,
            _ => return Err(io::Error::other("Invalid hotkey ownership")) };
        let live = match fields.remove("live") { Some("true") => true, Some("false") => false,
            _ => return Err(io::Error::other("Invalid hotkey session state")) };
        let revision = fields.remove("revision").filter(|value| value.len() == 64 && value.bytes().all(|c| c.is_ascii_hexdigit()))
            .ok_or_else(|| io::Error::other("Invalid hotkey revision"))?.to_owned();
        let chord_valid = |value: &str| !value.is_empty() && value.len() <= 64
            && value.bytes().all(|c| c.is_ascii_uppercase() || c.is_ascii_digit() || b"+_:".contains(&c));
        let mut actions: Vec<HotkeyAction> = Vec::new();
        let mut values = Vec::new();
        for line in lines {
            let row: Vec<_> = line.split('\t').collect();
            if row.len() != 6 || row[..5].iter().any(|v| v.is_empty() || v.len() > 160 || v.chars().any(char::is_control))
                || !row[0].bytes().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'_')
                || actions.iter().any(|a| a.id == row[0]) || !chord_valid(row[3])
                || !matches!(row[4], "press" | "hold" | "switcher" | "mouse") {
                return Err(io::Error::other("Invalid hotkey definition"));
            }
            let available = match row[5] { "true" => true, "false" => false, _ => return Err(io::Error::other("Invalid hotkey availability")) };
            let value = fields.remove(row[0]).filter(|value| chord_valid(value))
                .ok_or_else(|| io::Error::other("Invalid hotkey chord"))?;
            values.push(value.to_owned());
            actions.push(HotkeyAction { id: row[0].into(), categories: row[1].split('|').map(str::to_owned).collect(),
                label: row[2].into(), kind: row[4].into(), available });
        }
        if actions.is_empty() || !fields.is_empty() { return Err(io::Error::other("Invalid hotkey catalogue")); }
        Ok(Self { actions, values, revision, readonly, live })
    }

    fn save(&self, action: usize, chord: &str) -> io::Result<String> {
        widget_command(&["hotkeys-apply".into(), self.revision.clone(), self.actions[action].id.clone(), chord.into()])
    }
}

fn hotkey_label(chord: &str) -> String {
    chord.split('+').map(|part| match part {
        "SUPER" => "Super".into(), "SHIFT" => "Shift".into(), "CTRL" => "Ctrl".into(), "ALT" => "Alt".into(),
        "RETURN" => "Enter".into(), "SPACE" => "Space".into(), "PRINT" => "Print".into(), _ => part.to_owned(),
    }).collect::<Vec<_>>().join("+")
}

const WIDGETS: &[(&str, &str, &str)] = &[
    ("notificationToasts", "Notification toasts", "Popup cards; history and sounds stay"),
    ("windowSwitcher", "Window switcher", "Optional window list and shortcut"),
];

const BAR_SETTINGS: &[(&str, &str, &[&str], &[&str])] = &[
    ("barBehaviour", "Behaviour", &["keyboard", "keyboard-mouse", "toggle", "always"],
        &["Autohide (Keyboard)", "Autohide (Keyboard + Mouse)", "Toggle", "Always show (legacy)"]),
    ("barLocation", "Position", &["above", "top", "bottom"], &["Above", "Top", "Bottom"]),
    ("barStyle", "Style", &["anchored", "floating"], &["Anchored", "Floating"]),
    ("oskAccess", "Onscreen Keyboard", &["none", "launcher", "topbar"], &["None", "Launcher", "Taskbar"]),
];

const CARD_MODULES: &[&str] = &["launcher", "background", "layout", "media", "audio", "bluetooth",
    "clipboard", "network", "tailscale", "ssh", "notifications", "battery", "performance"];

const CARD_LABELS: &[&str] = &["Launcher", "Background apps", "Layout", "Media", "Audio", "Bluetooth",
    "Clipboard", "Network", "Tailscale", "SSH", "Notifications", "Battery", "Performance"];

#[derive(Clone)]
struct CardStack { id: String, modules: Vec<usize> }

#[derive(Clone, Copy, PartialEq)]
enum Ownership { User, Policy, Readonly }

#[derive(Clone)]
struct Widgets {
    enabled: [bool; 2], ownership: [Ownership; 8], supported: bool, revision: String,
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
        let mut ownership = [Ownership::User; 8];
        for (index, (id, _, _)) in WIDGETS.iter().enumerate() {
            let (value, owner) = fields.remove(id).and_then(|value| value.split_once(':'))
                .ok_or_else(|| io::Error::other("Missing widget state"))?;
            enabled[index] = boolean(Some(value))?;
            ownership[index] = match owner { "policy" => Ownership::Policy, "readonly" | "symlink" => Ownership::Readonly, "user" => Ownership::User,
                _ => return Err(io::Error::other("Invalid widget ownership")) };
        }
        let (value, owner) = fields.remove("cardStacks").and_then(|value| value.split_once(':'))
            .ok_or_else(|| io::Error::other("Missing card stacks"))?;
        ownership[2] = match owner { "policy" => Ownership::Policy, "readonly" | "symlink" => Ownership::Readonly, "user" => Ownership::User,
            _ => return Err(io::Error::other("Invalid card ownership")) };
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
            ownership[index + 3] = match owner { "policy" => Ownership::Policy, "readonly" | "symlink" => Ownership::Readonly, "user" => Ownership::User,
                _ => return Err(io::Error::other("Invalid bar ownership")) };
        }
        let (value, owner) = fields.remove("barWidth").and_then(|value| value.split_once(':'))
            .ok_or_else(|| io::Error::other("Missing bar width"))?;
        let width = value.parse::<u8>().ok().filter(|width| (50..=100).contains(width) && value == width.to_string())
            .ok_or_else(|| io::Error::other("Invalid bar width"))?;
        ownership[7] = match owner { "policy" => Ownership::Policy, "readonly" | "symlink" => Ownership::Readonly, "user" => Ownership::User,
            _ => return Err(io::Error::other("Invalid bar width ownership")) };
        if !fields.is_empty() { return Err(io::Error::other("Unknown widget state")); }
        Ok(Self { enabled, ownership, supported, revision, stacks, bar, width })
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

    fn reorder_member(&mut self, module: usize, forward: bool) {
        if !self.supported || self.ownership[2] != Ownership::User { return; }
        if let Some((stack, position)) = self.location(module) {
            let members = &mut self.stacks[stack].modules;
            let next = if forward { (position + 1).min(members.len() - 1) } else { position.saturating_sub(1) };
            members.swap(position, next);
        }
    }

    fn save_subset(&mut self, fields: &[&str]) -> io::Result<String> {
        let mut args = vec!["widgets-apply".into(), format!("revision={}", self.revision)];
        args.extend(WIDGETS.iter().enumerate().map(|(index, (id, _, _))| format!("{id}={}", self.enabled[index])));
        args.push(format!("cardStacks={}", self.stacks.iter().map(|stack|
            format!("{}/{}", stack.id, stack.modules.iter().map(|index| CARD_MODULES[*index]).collect::<Vec<_>>().join(",")))
            .collect::<Vec<_>>().join(";")));
        args.extend(BAR_SETTINGS.iter().enumerate().map(|(index, (id, _, choices, _))|
            format!("{id}={}", choices[self.bar[index]])));
        args.push(format!("barWidth={}", self.width));
        args = args.into_iter().enumerate().filter_map(|(index, value)|
            (index < 2 || value.split_once('=').is_some_and(|(name, _)| fields.contains(&name))).then_some(value)).collect();
        let text = widget_command(&args)?;
        let refreshed = Self::load().map_err(|error| io::Error::other(format!("Save completed; refresh failed: {error}")))?;
        self.revision = refreshed.revision;
        self.ownership = refreshed.ownership;
        self.supported = refreshed.supported;
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
        crossterm::execute!(io::stdout(), event::DisableMouseCapture)?;
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

#[derive(Clone)]
struct ViewRow { label: String, value: String, control: Control, enabled: bool }
fn row(label: &str, value: String, control: Control, enabled: bool) -> ViewRow {
    ViewRow { label: label.into(), value: if enabled { value } else { format!("{value} - Read Only") }, control, enabled }
}
// Keep wrapped labels and values within their terminal columns.
fn wrap_cells(text: &str, width: usize) -> Vec<String> {
    let mut lines = Vec::new();
    for paragraph in text.split('\n') {
        let mut line = String::new();
        for word in paragraph.split_whitespace() {
            if !line.is_empty() && Line::from(format!("{line} {word}")).width() > width {
                lines.push(std::mem::take(&mut line));
            }
            if !line.is_empty() { line.push(' '); }
            for character in word.chars() {
                if !line.is_empty() && Line::from(format!("{line}{character}")).width() > width {
                    lines.push(std::mem::take(&mut line));
                }
                line.push(character);
            }
        }
        lines.push(line);
    }
    lines
}

fn columns(label: &str, value: &str, label_width: usize, width: usize) -> Vec<String> {
    let labels = wrap_cells(label, label_width);
    let values = wrap_cells(value, width.saturating_sub(label_width + 2).max(1));
    (0..labels.len().max(values.len())).map(|index| {
        let label = labels.get(index).map(String::as_str).unwrap_or("");
        let padding = " ".repeat(label_width + 2 - Line::from(label).width());
        format!("{label}{padding}{}", values.get(index).map(String::as_str).unwrap_or(""))
    }).collect()
}

fn display_name(id: &str) -> String {
    id.split('-').map(|word| {
        let mut characters = word.chars();
        characters.next().map(|first| first.to_uppercase().collect::<String>() + characters.as_str()).unwrap_or_default()
    }).collect::<Vec<_>>().join(" ")
}

fn tick(value: bool) -> String { if value { "[x]" } else { "[ ]" }.into() }
fn cycle(value: &mut usize, count: usize, forward: bool) { *value = (*value + if forward { 1 } else { count - 1 }) % count; }
fn theme_colours(id: &str) -> io::Result<[Color; 6]> {
    let text = widget_command(&["theme-preview".into(), id.into()])?;
    let fields: BTreeMap<_, _> = text.split_whitespace().filter_map(|field| field.split_once('=')).collect();
    let mut colours = [Color::Reset; 6];
    for (index, name) in ["primary", "foreground", "background", "muted", "secondary", "tertiary"].iter().enumerate() {
        let value = fields.get(name).ok_or_else(|| io::Error::other("Missing preview colour"))?.trim_start_matches('#');
        let rgb = u32::from_str_radix(value, 16).map_err(io::Error::other)?;
        colours[index] = Color::Rgb((rgb >> 16) as u8, (rgb >> 8) as u8, rgb as u8);
    }
    Ok(colours)
}
fn choose(readonly: bool, selected: &mut BTreeMap<&str, bool>, steam: &mut usize) -> io::Result<Option<bool>> {
    let mut appearance = Appearance::load()?;
    let (mut widgets, mut message) = match Widgets::load() {
        Ok(value) => (value, String::new()),
        Err(error) => (Widgets { enabled: [true; 2], ownership: [Ownership::Policy; 8], supported: false,
            revision: String::new(), stacks: Vec::new(), bar: [0; 4], width: 80 }, error.to_string()),
    };
    let mut hot_settings = match HotkeySettings::load() {
        Ok(value) => value,
        Err(error) => {
            message = error.to_string();
            HotkeySettings { actions: Vec::new(), values: Vec::new(), revision: String::new(), readonly: true, live: false }
        }
    };
    let mut default_settings: Option<Vec<DefaultApp>> = None;
    let mut default_chooser: Option<usize> = None;
    let mut default_row = 0usize;
    let mut default_start = 0usize;
    let mut hot_cursor = 0usize;
    let mut hot_edit: Option<(usize, String)> = None;
    let mut hot_follow = false;
    let mut hot_anchor = None;
    let mut taskbar = widgets.clone();
    let mut page = 0usize;
    let mut pane = false;
    let mut subpage = 0; // 1: local theme preview, 2: local Taskbar draft.
    let mut preview = appearance.theme;
    let mut colours = theme_colours(&appearance.themes[preview]).unwrap_or([Color::Cyan, Color::White, Color::Black, Color::Gray, Color::Green, Color::Magenta]);
    let mut focus = 0usize;
    let mut overwrite = false;
    let mut stack = 0usize;
    let mut member = None;
    let mut remembered = 0usize;
    let mut placement = None;
    let mut grid_start = 0usize;
    let mut grid_tools = false;
    let mut hot_scroll = 0usize;
    let effective_screenshot = selected["screenshot"];
    let mut icons = widget_command(&["widget-icons".into()]).unwrap_or_default();
    let mut terminal = ratatui::init();
    let result = (|| {
        crossterm::execute!(io::stdout(), event::EnableMouseCapture)?;
        loop {
            if page == 2 && default_settings.is_none() {
                match DefaultApp::load() {
                    Ok(value) => default_settings = Some(value),
                    Err(error) => { message = error.to_string(); default_settings = Some(Vec::new()); },
                }
            }
            let editable = |index: usize| widgets.supported && widgets.ownership[index] == Ownership::User;
            let mut rows = Vec::new();
            if subpage == 1 {
                for (index, id) in appearance.themes.iter().enumerate() {
                    rows.push(row(&display_name(id), if index == appearance.theme { "Current" } else { "" }.into(), Control::Preview(index), true));
                }
                rows.extend([row("[ Use theme ]", "".into(), Control::Apply, !appearance.readonly[0] && !appearance.policy), row("[ Back ]", "".into(), Control::Back, true)]);
            } else if subpage == 2 {
                for (index, (_, label, _, labels)) in BAR_SETTINGS.iter().enumerate() {
                    let value = if index == 0 && taskbar.bar[index] == 3 { "Always show (legacy)" } else { labels[taskbar.bar[index]] };
                    rows.push(row(label, value.into(), Control::Bar(index), editable(index + 3)));
                    if index == 2 { rows.push(row("Width", format!("{}%", taskbar.width), Control::BarWidth, editable(7))); }
                }
                rows.extend([row("[ Save ]", "".into(), Control::Apply, (3..8).any(editable)), row("[ Back ]", "".into(), Control::Back, true)]);
            } else if page == 0 {
                for (id, label, detail) in ROWS.iter().filter(|(id, _, _)| *id != "login") {
                    let enabled = !readonly && (*id != "gamescope" || *steam != 0) && (*id != "handheld" || handheld_available(*steam, selected));
                    let value = match *id {
                        "steam" => ["None", "Native", "Flatpak"][*steam].into(),
                        "handheld" => if selected[id] && enabled { "Steamdeck" } else { "Off" }.into(),
                        _ => tick(selected[id]),
                    };
                    let detail = match *id {
                        "gamescope" if *steam == 0 => "Requires Steam",
                        "handheld" if !handheld_available(*steam, selected) => "Requires Steam native", _ => detail,
                    };
                    rows.push(ViewRow { label: format!("{label}\t{detail}"), value,
                        control: if *id == "steam" { Control::Steam } else { Control::Utility(id) }, enabled });
                }
                rows.extend([row("Overwrite existing dotfiles", tick(overwrite), Control::Overwrite, true),
                    ViewRow { label: if appearance.readonly[3] { "Setup Monitors - Read Only" } else if executable("hyprmon") { "[ Setup Monitors... ]" } else { "Hyprmon Unavailable" }.into(),
                        value: "".into(), control: Control::Monitors, enabled: !appearance.readonly[3] && executable("hyprmon") },
                    row("[ Review and Apply ]", "".into(), Control::Apply, true)]);
            } else if page == 1 {
                rows = vec![row("Theme", display_name(&appearance.themes[appearance.theme]), Control::Theme, !appearance.readonly[0] && !appearance.policy),
                    row("Transparency", ["Off", "Low", "Medium", "High"][appearance.transparency].into(), Control::Transparency, !appearance.readonly[1]),
                    row("Wallpaper", filename(&appearance.wallpaper), Control::Wallpaper, !appearance.readonly[2]),
                    row("Default layout", display_name(LAYOUTS[appearance.layout]), Control::Layout, !appearance.readonly[4]),
                    row("Taskbar", "Configure…".into(), Control::Taskbar, true),
                    row("Notifications", tick(widgets.enabled[0]), Control::Widget(0), editable(0))];
            }
            let mut controls: Vec<Control> = rows.iter().filter(|row| row.enabled).map(|row| row.control).collect();
            if page == 3 && subpage == 0 {
                controls = (0..=widgets.stacks.len()).map(Control::Stack).collect();
                if editable(1) { controls.push(Control::Widget(1)); }
                if editable(2) { controls.extend((0..8).map(Control::GridAction)); }
                if editable(1) || editable(2) { controls.push(Control::Apply); }
                controls.push(Control::GridTools);
            }
            if page == 2 {
                controls = if let Some(role) = default_chooser {
                    default_settings.as_ref().and_then(|values| values.get(role)).map(|value| (0..value.choices.len()).map(Control::DefaultChoice).collect()).unwrap_or_default()
                } else {
                    default_settings.as_ref().map(|values| values.iter().enumerate().filter(|(_, value)| !value.readonly).map(|(index, _)| Control::DefaultRole(index)).collect()).unwrap_or_default()
                };
            }
            if page == 4 && subpage == 0 { controls = vec![Control::Hotkeys]; }
            if controls.is_empty() { controls.push(Control::Back); }
            focus = focus.min(controls.len() - 1);
            stack = stack.min(widgets.stacks.len());
            if let Some(module) = member { if widgets.location(module).map(|v| v.0).unwrap_or(widgets.stacks.len()) != stack { member = None; } }
            let current = controls[focus];
            if page == 3 && matches!(current, Control::Widget(_) | Control::GridAction(0 | 1 | 3..=7)) { grid_tools = true; }
            let mut hits: Vec<(Rect, Control)> = Vec::new();
            let mut page_hits = Vec::new();
            let mut grid_columns = 2usize;
            let mut visible_grid_rows = 1usize;
            let mut hot_max_scroll = 0usize;
            let mut hot_line_count = 0usize;
            let mut hot_height = 0usize;
            let mut hot_actions = Vec::new();
            terminal.draw(|frame| {
                let area = frame.area();
                if area.width < 80 || area.height < 24 {
                    frame.render_widget(Paragraph::new("Icewine needs an 80 x 24 terminal.\nResize to continue; Esc: cancel."), area); return;
                }
                let accent = Style::default().fg(colours[0]).bold();
                let normal = Style::default().fg(colours[1]).bg(Color::Reset);
                let muted = normal.fg(colours[3]);
                let highlighted = normal.fg(colours[2]).bg(colours[0]).bold();
                frame.render_widget(Block::default().style(normal), area);
                let [sidebar, content] = Layout::horizontal([Constraint::Length(20), Constraint::Min(1)]).spacing(2).areas(area);
                for (rect, active) in [(sidebar, !pane), (content, pane)] {
                    frame.render_widget(Block::bordered().border_type(BorderType::Rounded).border_style(if active { accent } else { muted }), rect);
                }
                let left = Rect::new(sidebar.x + 2, sidebar.y + 1, sidebar.width - 4, sidebar.height - 2);
                frame.render_widget(Paragraph::new("Icewine").style(accent), Rect::new(left.x, left.y, left.width, 1));
                frame.render_widget(Paragraph::new(format!("├{}┤", "─".repeat(sidebar.width.saturating_sub(2) as usize))).style(if pane { muted } else { accent }), Rect::new(sidebar.x, sidebar.y + 2, sidebar.width, 1));
                for (index, name) in ["Utilities", "Appearance", "Default Apps", "Widgets", "Hotkeys"].iter().enumerate() {
                    let rect = Rect::new(left.x, left.y + 3 + index as u16 * 2, left.width, 1);
                    frame.render_widget(Paragraph::new(*name).style(if index == page { if !pane { highlighted } else { accent } } else { normal }), rect);
                    page_hits.push((rect, index));
                }
                let inner = Rect::new(content.x + 2, content.y + 1, content.width - 4, content.height - 2);
                let title = if subpage == 1 { "Appearance / Theme" } else if subpage == 2 { "Appearance / Taskbar" } else if page == 4 && hot_settings.readonly { "Hotkeys - Read Only" } else if page == 0 && readonly { "Utilities - Read Only" } else { ["Utilities", "Appearance", "Default Apps", "Widgets", "Hotkeys"][page] };
                let default_title = default_chooser.map(|role| format!("Default Apps / {}", DEFAULT_ROLES[role]));
                let title = if page == 2 { default_title.as_deref().unwrap_or("Default Apps") } else { title };
                frame.render_widget(Paragraph::new(title).style(accent), Rect::new(inner.x, inner.y, inner.width, 1));
                frame.render_widget(Paragraph::new(format!("├{}┤", "─".repeat(content.width.saturating_sub(2) as usize))).style(if pane { accent } else { muted }), Rect::new(content.x, content.y + 2, content.width, 1));
                let footer = Rect::new(inner.x, inner.bottom() - 1, inner.width, 1);
                if (page != 3 || subpage != 0) && subpage != 1 {
                    frame.render_widget(Paragraph::new(if subpage > 0 || (page == 2 && default_chooser.is_some()) { "Tab: Switch pane   Esc: Back" } else if page == 4 && !hot_settings.live { "Saved chords - no managed session. Esc: Close" } else if page == 4 { "↑/↓: Move  Enter: Edit  r: Reset  Esc: Close" } else { "Tab: Switch pane   Esc: Close" }).style(muted), footer);
                }
                let status_bottom = if page == 3 && subpage == 0 { footer.y + 1 } else if subpage > 0 { footer.y - 3 } else { footer.y - 1 };
                let content_bottom = (if message.is_empty() { status_bottom } else { status_bottom - 3 })
                    .saturating_sub(if page == 4 && hot_edit.is_some() { 4 } else { 0 });
                let body_y = content.y + if subpage == 0 && matches!(page, 0 | 3) { 3 } else { 4 };
                let body = Rect::new(inner.x, body_y, inner.width, content_bottom.saturating_sub(body_y));
                if page == 2 {
                    if let Some(values) = &default_settings {
                        if let Some(role) = default_chooser {
                            if let Some(value) = values.get(role) {
                                let empty = value.choices.iter().all(|pair| pair.0.starts_with('@'));
                                let top = content.y + if empty { 6 } else { 4 };
                                if empty { frame.render_widget(Paragraph::new("No installed applications found.").style(muted), Rect::new(inner.x, content.y + 4, inner.width, 1)); }
                                let available = ((area.height - 9) / 2) as usize;
                                if focus < default_start { default_start = focus; }
                                if focus >= default_start + available { default_start = focus - available + 1; }
                                let start = default_start;
                                for (index, (id, label)) in value.choices.iter().enumerate().skip(start).take(available) {
                                    let marker = if id == &value.current { "Current" } else { "" };
                                    let text = format!("{}{}{marker}", default_clip(label, 25), " ".repeat(25usize.saturating_sub(Line::from(label.as_str()).width())));
                                    let rect = Rect::new(inner.x, top + (index - start) as u16 * 2, inner.width, 1);
                                    frame.render_widget(Paragraph::new(default_clip(&text, inner.width as usize)).style(if pane && index == focus { highlighted } else { normal }), rect);
                                    hits.push((rect, Control::DefaultChoice(index)));
                                }
                                for (x, label, control) in [(inner.x, "[ Use ]", Control::DefaultChoice(focus)), (inner.x + 10, "[ Back ]", Control::Back)] {
                                    let rect = Rect::new(x, area.height - 4, label.len() as u16, 1);
                                    frame.render_widget(Paragraph::new(label).style(accent), rect);
                                    hits.push((rect, control));
                                }
                            }
                        } else {
                            for (index, value) in values.iter().enumerate() {
                                let suffix = if value.readonly { " - Read Only" } else { "  ›" };
                                let text = format!("{:<20}{}{suffix}", DEFAULT_ROLES[index], value.label);
                                let rect = Rect::new(inner.x, content.y + 4 + index as u16 * 2, inner.width, 1);
                                frame.render_widget(Paragraph::new(default_clip(&text, inner.width as usize)).style(if value.readonly { muted } else if pane && current == Control::DefaultRole(index) { highlighted } else { normal }), rect);
                                if !value.readonly { hits.push((rect, Control::DefaultRole(index))); }
                            }
                        }
                    }
                } else if page == 3 && subpage == 0 {
                    let unassigned: Vec<_> = (0..CARD_MODULES.len()).filter(|module| widgets.location(*module).is_none()).collect();
                    let mut actions = Vec::new();
                    for control in controls.iter().filter(|c| !matches!(c, Control::Stack(_) | Control::Widget(_))
                            && (grid_tools || matches!(c, Control::GridAction(2) | Control::Apply | Control::GridTools))) {
                        if *control == Control::GridTools { actions.push((None, "[ Import (coming soon) ]".to_string())); }
                        let label = match control {
                            Control::GridAction(index) => format!("[ {} ]", ["New stack", "Remove stack", "Make primary", "Member -", "Member +", "Stack [", "Stack ]", "Unassign"][*index]),
                            Control::GridTools => "[⋯]".into(),
                            _ => "[ Save ]".into(),
                        };
                        actions.push((Some(*control), label));
                    }
                    let mut toolbar_rows = 1u16;
                    let mut toolbar_x = 0;
                    for (_, label) in &actions {
                        let width = Line::from(label.as_str()).width() as u16;
                        if toolbar_x + width > body.width { toolbar_rows += 1; toolbar_x = 0; }
                        toolbar_x += width + 1;
                    }
                    let reserved = 4 + toolbar_rows + u16::from(grid_tools);
                    let grid_height = body.height.saturating_sub(reserved);
                    visible_grid_rows = (grid_height / 5).max(1) as usize;
                    grid_columns = if body.width >= 90 { 3 } else { 2 };
                    let selected_row = stack / grid_columns;
                    if stack < widgets.stacks.len() {
                        if selected_row < grid_start { grid_start = selected_row; }
                        if selected_row >= grid_start + visible_grid_rows { grid_start = selected_row + 1 - visible_grid_rows; }
                    }
                    let available_width = body.width - (grid_columns as u16 - 1) * 2;
                    let cell_width = available_width / grid_columns as u16;
                    let extra = available_width % grid_columns as u16;
                    for index in grid_start * grid_columns..((grid_start + visible_grid_rows) * grid_columns).min(widgets.stacks.len()) {
                        let value = &widgets.stacks[index];
                        let column = (index % grid_columns) as u16;
                        let rect = Rect::new(body.x + column * (cell_width + 2) + column.min(extra), body.y + u16::from(grid_tools) + (index / grid_columns - grid_start) as u16 * 5, cell_width + u16::from(column < extra), 5);
                        let active = pane && stack == index;
                        let title = icons.split_whitespace().find_map(|field| field.split_once('=').filter(|(id, _)| *id == CARD_MODULES[value.modules[0]]).map(|(_, icon)| icon)).unwrap_or("·");
                        frame.render_widget(Block::bordered().title(format!(" {title} ")).border_type(if active { BorderType::Double } else { BorderType::Rounded }).border_style(if active { accent } else { muted }), rect);
                        hits.push((rect, Control::Stack(index)));
                        let selected_pos = member.and_then(|m| value.modules.iter().position(|v| *v == m)).unwrap_or(0);
                        let start = selected_pos.saturating_sub(2);
                        for (offset, module) in value.modules.iter().enumerate().skip(start).take(3) {
                            let selected = active && member == Some(*module) && placement.is_none();
                            let label = format!("{}{}{}", if selected { "›" } else { " " }, if offset == 0 { "" } else { "  " }, CARD_LABELS[*module]);
                            let r = Rect::new(rect.x + 1, rect.y + 1 + (offset - start) as u16, rect.width - 2, 1);
                            frame.render_widget(Paragraph::new(label).style(if selected { highlighted } else { if offset == 0 { accent } else { normal } }), r);
                            hits.push((r, Control::Card(*module)));
                        }
                    }
                    let unrect = Rect::new(body.x, body.y + u16::from(grid_tools) + visible_grid_rows as u16 * 5, body.width, 4);
                    let active = pane && stack == widgets.stacks.len() && placement.is_none();
                    frame.render_widget(Block::bordered().title(format!(" Unassigned ({}) ", unassigned.len())).border_type(if active { BorderType::Double } else { BorderType::Rounded }).border_style(if active { accent } else { muted }), unrect);
                    hits.push((unrect, Control::Stack(widgets.stacks.len())));
                    if unassigned.is_empty() { frame.render_widget(Paragraph::new("None").style(muted), Rect::new(unrect.x + 1, unrect.y + 1, unrect.width - 2, 1)); }
                    let position = member.and_then(|m| unassigned.iter().position(|v| *v == m)).unwrap_or(0);
                    for (offset, module) in unassigned.iter().enumerate().skip(position.saturating_sub(1)).take(2) {
                        let r = Rect::new(unrect.x + 1, unrect.y + 1 + (offset - position.saturating_sub(1)) as u16, unrect.width - 2, 1);
                        let selected = active && member == Some(*module);
                        frame.render_widget(Paragraph::new(format!("{} {}", if selected { "›" } else { " " }, CARD_LABELS[*module])).style(if selected { highlighted } else { normal }), r);
                        hits.push((r, Control::Card(*module)));
                    }
                    if grid_tools {
                        let switcher_rect = Rect::new(body.x, body.y, body.width, 1);
                        frame.render_widget(Paragraph::new(format!("Window switcher {}{}", tick(widgets.enabled[1]), if editable(1) { "" } else { " - Read Only" })).style(if pane && current == Control::Widget(1) { highlighted } else if editable(1) { normal } else { muted }), switcher_rect);
                        if editable(1) { hits.push((switcher_rect, Control::Widget(1))); }
                    }
                    let mut x = body.x;
                    let mut y = body.bottom() - toolbar_rows;
                    for (control, label) in actions {
                        let width = Line::from(label.as_str()).width() as u16;
                        if x + width > body.right() { x = body.x; y += 1; }
                        let rect = Rect::new(x, y, width, 1);
                        frame.render_widget(Paragraph::new(label).style(if control.is_none() { muted } else if pane && control == Some(current) { highlighted } else { accent }), rect);
                        if let Some(control) = control { hits.push((rect, control)); }
                        x += width + 1;
                    }
                } else if page == 4 && subpage == 0 {
                    let (mut lines, actions) = hotkeys(&widgets, &hot_settings, effective_screenshot, body.width as usize, accent);
                    hot_actions = actions;
                    if let Some(index) = hot_anchor {
                        if let Some((start, _, _)) = hot_actions.get(index) { hot_cursor = *start; }
                        if hot_edit.is_none() { hot_anchor = None; }
                    }
                    hot_line_count = lines.len();
                    hot_height = body.height as usize;
                    hot_cursor = hot_cursor.min(lines.len().saturating_sub(1));
                    hot_max_scroll = lines.len().saturating_sub(hot_height);
                    if hot_follow || hot_edit.is_some() {
                        let (start, end) = hot_actions.iter().find(|(start, end, _)| (*start..*end).contains(&hot_cursor))
                            .map(|(start, end, _)| (*start, *end)).unwrap_or((hot_cursor, hot_cursor + 1));
                        if start < hot_scroll { hot_scroll = start; }
                        if end > hot_scroll + hot_height { hot_scroll = end.saturating_sub(hot_height); }
                    }
                    hot_follow = false;
                    hot_scroll = hot_scroll.min(hot_max_scroll);
                    for (start, end, _) in &hot_actions {
                        if (*start..*end).contains(&hot_cursor) && pane {
                            for line in &mut lines[*start..*end] { *line = line.clone().style(if hot_settings.readonly { muted } else { highlighted }); }
                        }
                    }
                    frame.render_widget(Paragraph::new(lines.into_iter().skip(hot_scroll).take(hot_height).collect::<Vec<_>>()).style(normal), body);
                    hits.push((body, Control::Hotkeys));
                    if let Some((action, draft)) = &hot_edit {
                        let input = if hot_settings.actions[*action].kind == "mouse" { "Shift/Ctrl/Alt/Super + mouse:272-279" } else { "Shift/Ctrl/Alt/Super + key" };
                        let editor = format!("{}: {}_\n{input}\nEnter: Save   Esc: Cancel   Ctrl+U: Clear", hot_settings.actions[*action].label, draft);
                        frame.render_widget(Paragraph::new(editor).style(accent), Rect::new(body.x, body.bottom() + 1, body.width, 3));
                    }
                } else {
                    let mut top = body.y;
                    if page == 0 && subpage == 0 {
                        let introduction = wrap_cells("Selected utilities are installed and configured by Icewine.", body.width as usize);
                        frame.render_widget(Paragraph::new(introduction.join("\n")).style(muted), Rect::new(body.x, top, body.width, introduction.len() as u16));
                        top += introduction.len() as u16 + 1;
                    }
                    let sample_y = body.bottom().saturating_sub(3);
                    let list_bottom = if subpage == 1 { sample_y.saturating_sub(1) } else { body.bottom() };
                    let row_count = rows.len().saturating_sub(if subpage > 0 { 2 } else { 0 });
                    let mut laid_out = Vec::new();
                    let mut offset = 0u16;
                    for value in rows.iter().take(row_count) {
                        if page == 0 && subpage == 0 && matches!(value.control, Control::Steam | Control::Overwrite) { offset += 1; }
                        let parts: Vec<_> = value.label.split('\t').collect();
                        let plain_value = value.value.strip_suffix(" - Read Only").unwrap_or(&value.value);
                        let mut displayed = if matches!(value.control, Control::Steam | Control::Utility("handheld") | Control::Transparency | Control::Layout | Control::Bar(_) | Control::BarWidth) {
                            format!("‹ {plain_value} ›")
                        } else if value.enabled && matches!(value.control, Control::Theme | Control::Wallpaper | Control::Taskbar) {
                            format!("{plain_value}  ›")
                        } else { plain_value.to_string() };
                        if plain_value != value.value {
                            displayed.push_str(if Line::from(displayed.as_str()).width() + 12 > body.width as usize - 20 { "\n- Read Only" } else { " - Read Only" });
                        }
                        let text = if parts.len() == 2 {
                            let label_width = if value.control == Control::Utility("media") { 19 } else { 18 };
                            let padding = 14usize.saturating_sub(Line::from(displayed.as_str()).width()) / 2;
                            // Let Gradia's label use the existing gap before its aligned checkbox.
                            let extra = if value.control == Control::Utility("screenshot") { padding } else { 0 };
                            let detail_width = body.width as usize - label_width - 14 + extra;
                            let details = wrap_cells(parts[1], detail_width);
                            let padding = padding - extra;
                            details.iter().enumerate().map(|(line, detail)| {
                                let label = if line == 0 { parts[0] } else { "" };
                                format!("{label:<label_width$}{detail}{}{}{}", " ".repeat(detail_width - Line::from(detail.as_str()).width()), " ".repeat(padding), if line == 0 { displayed.as_str() } else { "" })
                            }).collect::<Vec<_>>()
                        } else if value.control == Control::Overwrite {
                            wrap_cells(&format!("{} {}", value.value, value.label), body.width as usize)
                        } else if value.value.is_empty() {
                            wrap_cells(&value.label, body.width as usize)
                        } else { columns(&value.label, &displayed, 18, body.width as usize) };
                        let height = text.len() as u16;
                        laid_out.push((offset, height, text));
                        offset += height + u16::from(page == 1 || subpage == 2);
                    }
                    let selected_row = rows.iter().take(row_count).position(|row| row.control == current).unwrap_or(0);
                    let available = list_bottom.saturating_sub(top);
                    let scroll = if let Some((y, height, _)) = laid_out.get(selected_row) {
                        (y + height).saturating_sub(available)
                    } else { 0 };
                    for (index, (offset, height, text)) in laid_out.iter().enumerate() {
                        if *offset < scroll || offset + height > scroll + available { continue; }
                        let value = &rows[index];
                        let rect = Rect::new(body.x, top + offset - scroll, body.width, *height);
                        let style = if !value.enabled { muted } else if pane && value.control == current { highlighted } else { normal };
                        frame.render_widget(Paragraph::new(text.join("\n")).style(style), rect);
                        if value.enabled { hits.push((rect, value.control)); }
                    }
                    if subpage > 0 {
                        if subpage == 1 {
                            frame.render_widget(Paragraph::new(Line::from(vec![Span::styled("Aa  Normal text     ", normal), Span::styled("Accent     ", accent), Span::styled("Supporting text", muted)])), Rect::new(body.x, sample_y, body.width, 1));
                        }
                        let mut x = body.x;
                        for value in rows.iter().skip(row_count) {
                            let rect = Rect::new(x, footer.y - 2, value.label.chars().count() as u16, 1);
                            frame.render_widget(Paragraph::new(value.label.as_str()).style(if !value.enabled { muted } else if pane && current == value.control { highlighted } else { accent }), rect);
                            if value.enabled { hits.push((rect, value.control)); }
                            x = rect.right() + 3;
                        }
                    }
                }
                if !message.is_empty() {
                    frame.render_widget(Paragraph::new(message.as_str()).style(accent).wrap(Wrap { trim: false }), Rect::new(inner.x, if page == 2 { area.height - 4 } else { status_bottom - 2 }, inner.width, 2));
                }
            })?;
            if !event::poll(std::time::Duration::from_secs(2))? {
                if page == 3 { icons = widget_command(&["widget-icons".into()]).unwrap_or(icons); }
                continue;
            }
            let mut activate = false;
            let mut key = match event::read()? {
                Event::Key(key) if key.kind == KeyEventKind::Press => {
                    if key.code == KeyCode::Char('c') && key.modifiers.contains(event::KeyModifiers::CONTROL) { return Ok(None); }
                    if key.code == KeyCode::Char('q') && hot_edit.is_none() { KeyCode::Esc }
                    else if hot_edit.is_some() && key.code == KeyCode::Char('u') && key.modifiers.contains(event::KeyModifiers::CONTROL) { KeyCode::Delete }
                    else { key.code }
                }
                Event::Mouse(mouse) => {
                    if hot_edit.is_some() { continue; }
                    if terminal.size()?.width < 80 || terminal.size()?.height < 24 { continue; }
                    match mouse.kind {
                        event::MouseEventKind::Down(event::MouseButton::Left) => {
                            if let Some((_, index)) = page_hits.iter().find(|(r, _)| r.contains(Position::new(mouse.column, mouse.row))) {
                                if subpage != 0 { subpage = 0; colours = theme_colours(&appearance.themes[appearance.theme]).unwrap_or(colours); }
                                page = *index; default_chooser = None; default_settings = None; message.clear(); pane = false; focus = 0; member = None; placement = None; continue;
                            }
                            if let Some((hit, control)) = hits.iter().rev().find(|(r, _)| r.contains(Position::new(mouse.column, mouse.row))) {
                                pane = true;
                                match *control {
                                    Control::Back if page == 2 => { default_chooser = None; focus = default_row; message.clear(); continue; },
                                    Control::Stack(index) => { stack = index; focus = index; if placement.is_none() { member = None; remembered = widgets.stacks.get(index).and_then(|s| s.modules.first()).copied().unwrap_or(remembered); } if placement.is_some() && index < widgets.stacks.len() { activate = true; } }
                                    Control::Hotkeys => { hot_cursor = hot_scroll + mouse.row.saturating_sub(hit.y) as usize; hot_follow = true; }
                                    Control::Card(module) => {
                                        if placement.is_some() { stack = widgets.location(module).map(|v| v.0).unwrap_or(widgets.stacks.len()); }
                                        else { member = Some(module); remembered = module; stack = widgets.location(module).map(|v| v.0).unwrap_or(widgets.stacks.len()); }
                                        focus = stack; activate = true;
                                    }
                                    _ => { focus = controls.iter().position(|c| c == control).unwrap_or(focus); activate = true; }
                                }
                                KeyCode::Enter
                            } else { continue; }
                        }
                        event::MouseEventKind::ScrollDown | event::MouseEventKind::ScrollUp if page == 4 && mouse.column >= 22 && hot_edit.is_none() => {
                            pane = true;
                            hot_scroll = if mouse.kind == event::MouseEventKind::ScrollDown { (hot_scroll + 1).min(hot_max_scroll) } else { hot_scroll.saturating_sub(1) };
                            hot_cursor = hot_cursor.clamp(hot_scroll, hot_scroll + hot_height.saturating_sub(1));
                            continue;
                        },
                        event::MouseEventKind::ScrollDown => { pane = mouse.column >= 22; KeyCode::Down },
                        event::MouseEventKind::ScrollUp => { pane = mouse.column >= 22; KeyCode::Up },
                        _ => continue,
                    }
                }
                _ => continue,
            };
            if terminal.size()?.width < 80 || terminal.size()?.height < 24 {
                if key == KeyCode::Esc { return Ok(None); } continue;
            }
            if let Some((action, draft)) = &mut hot_edit {
                match key {
                    KeyCode::Esc => { hot_edit = None; message.clear(); hot_follow = true; },
                    KeyCode::Backspace => { draft.pop(); },
                    KeyCode::Delete => draft.clear(),
                    KeyCode::Char(character) if character.is_ascii() && !character.is_ascii_control() && draft.len() < 64 => draft.push(character),
                    KeyCode::Enter => {
                        match hot_settings.save(*action, draft) {
                            Ok(text) => {
                                hot_edit = None;
                                message = text;
                                match HotkeySettings::load() {
                                    Ok(value) => hot_settings = value,
                                    Err(error) => { hot_settings.readonly = true; message = error.to_string(); },
                                }
                            },
                            Err(error) => message = error.to_string(),
                        }
                        hot_follow = true;
                    },
                    _ => (),
                }
                continue;
            }
            if key == KeyCode::Tab || key == KeyCode::BackTab { pane = !pane; continue; }
            if key == KeyCode::Esc {
                if page == 2 && default_chooser.take().is_some() { focus = default_row; message.clear(); continue; }
                if placement.take().is_some() { message.clear(); continue; }
                if page == 3 && member.take().is_some() { continue; }
                if subpage != 0 { subpage = 0; focus = 0; colours = theme_colours(&appearance.themes[appearance.theme]).unwrap_or(colours); continue; }
                return Ok(None);
            }
            if !pane {
                match key {
                    KeyCode::Down | KeyCode::Up => { if subpage == 1 { colours = theme_colours(&appearance.themes[appearance.theme]).unwrap_or(colours); } cycle(&mut page, 5, key == KeyCode::Down); default_chooser = None; default_settings = None; message.clear(); subpage = 0; focus = 0; member = None; placement = None; },
                    KeyCode::Enter | KeyCode::Right | KeyCode::Char(' ') => pane = true, _ => (),
                }
                continue;
            }
            if page == 2 {
                if matches!(key, KeyCode::Up | KeyCode::Down) {
                    if default_chooser.is_some() { focus = if key == KeyCode::Down { (focus + 1).min(controls.len() - 1) } else { focus.saturating_sub(1) }; }
                    else { cycle(&mut focus, controls.len(), key == KeyCode::Down); }
                    continue;
                }
                if activate || matches!(key, KeyCode::Enter | KeyCode::Char(' ')) || (default_chooser.is_none() && key == KeyCode::Right) {
                    if let Some(role) = default_chooser {
                        if let Some(value) = default_settings.as_ref().and_then(|values| values.get(role)) {
                            message = match value.save(role, focus) {
                                Ok(_) => String::new(),
                                Err(error) if error.to_string().contains("Choose a browser first.") => "Choose a browser first.".into(),
                                Err(error) if error.to_string().contains("recovery needs attention") => format!("Couldn’t save default application.\n{}", error.to_string().trim()),
                                Err(_) => "Couldn’t save default application.".into(),
                            };
                        }
                        default_chooser = None; focus = default_row;
                        match DefaultApp::load() { Ok(value) => default_settings = Some(value), Err(error) => { default_settings = Some(Vec::new()); message = error.to_string(); } }
                    } else if let Control::DefaultRole(role) = controls[focus] {
                        match DefaultApp::load() {
                            Ok(values) if !values[role].readonly => {
                                default_row = focus; default_chooser = Some(role); default_start = 0;
                                focus = values[role].choices.iter().position(|pair| pair.0 == values[role].current).unwrap_or(0);
                                default_settings = Some(values); message.clear();
                            },
                            Ok(values) => { default_settings = Some(values); message = "Default application is Read Only".into(); },
                            Err(error) => message = error.to_string(),
                        }
                    }
                }
                continue;
            }
            if page == 4 && subpage == 0 {
                match key {
                    KeyCode::Down => { hot_cursor = (hot_cursor + 1).min(hot_line_count.saturating_sub(1)); hot_follow = true; },
                    KeyCode::Up => { hot_cursor = hot_cursor.saturating_sub(1); hot_follow = true; },
                    KeyCode::PageDown => { hot_cursor = (hot_cursor + hot_height).min(hot_line_count.saturating_sub(1)); hot_follow = true; },
                    KeyCode::PageUp => { hot_cursor = hot_cursor.saturating_sub(hot_height); hot_follow = true; },
                    KeyCode::Enter | KeyCode::Char('r') if !hot_settings.readonly => {
                        if let Some((index, (_, _, action))) = hot_actions.iter().enumerate().find(|(_, (start, end, _))| (*start..*end).contains(&hot_cursor)) {
                            hot_anchor = Some(index);
                            if key == KeyCode::Enter { hot_edit = Some((*action, hotkey_label(&hot_settings.values[*action]))); message.clear(); }
                            else {
                                message = match hot_settings.save(*action, "default") {
                                    Ok(text) => match HotkeySettings::load() {
                                        Ok(value) => { hot_settings = value; text },
                                        Err(error) => { hot_settings.readonly = true; error.to_string() },
                                    }, Err(error) => error.to_string(),
                                };
                            }
                            hot_follow = true;
                        }
                    },
                    _ => (),
                }
                continue;
            }
            if page == 3 && subpage == 0 {
                if let Some(module) = member { remembered = module; }
                if matches!(key, KeyCode::Char('n' | '+' | '-' | '[' | ']') | KeyCode::Delete) && editable(2) {
                    let command = match key { KeyCode::Char('n') => 0, KeyCode::Delete => 1, KeyCode::Char('-') => 3, KeyCode::Char('+') => 4, KeyCode::Char('[') => 5, _ => 6 };
                    focus = controls.iter().position(|c| *c == Control::GridAction(command)).unwrap_or(focus); key = KeyCode::Enter;
                }
                if key == KeyCode::Char('s') { focus = controls.iter().position(|c| *c == Control::Apply).unwrap_or(focus); key = KeyCode::Enter; }
                let action = controls[focus];
                if matches!(key, KeyCode::Left | KeyCode::Right | KeyCode::Up | KeyCode::Down) {
                    if matches!(action, Control::Stack(_)) {
                        if matches!(key, KeyCode::Up | KeyCode::Down) && member.is_some() && placement.is_none() {
                            let inventory = if stack < widgets.stacks.len() { widgets.stacks[stack].modules.clone() } else { (0..CARD_MODULES.len()).filter(|m| widgets.location(*m).is_none()).collect() };
                            if let Some(position) = inventory.iter().position(|m| Some(*m) == member) {
                                let next = if key == KeyCode::Down { (position + 1).min(inventory.len() - 1) } else { position.saturating_sub(1) };
                                member = Some(inventory[next]);
                            }
                        } else {
                            let count = widgets.stacks.len();
                            let next = match key {
                                KeyCode::Left if stack < count && stack % grid_columns > 0 => stack - 1,
                                KeyCode::Right if stack < count && stack % grid_columns + 1 < grid_columns && stack + 1 < count => stack + 1,
                                KeyCode::Up if stack == count => count.saturating_sub(1),
                                KeyCode::Up if stack < grid_columns && placement.is_none() => { if let Some(index) = controls.iter().position(|c| *c == Control::Widget(1)) { focus = index; } stack },
                                KeyCode::Up => stack.saturating_sub(grid_columns),
                                KeyCode::Down if stack < count => (stack + grid_columns).min(count),
                                KeyCode::Down if placement.is_none() => { focus = controls.iter().position(|c| matches!(c, Control::GridAction(_) | Control::Apply)).unwrap_or(focus); stack },
                                _ => stack,
                            };
                            if !(placement.is_some() && next == count) {
                                let changed_stack = stack != next;
                                stack = next;
                                if changed_stack && member.is_none() && placement.is_none() { remembered = widgets.stacks.get(stack).and_then(|s| s.modules.first()).copied().or_else(|| (0..CARD_MODULES.len()).find(|m| widgets.location(*m).is_none())).unwrap_or(remembered); }
                                if focus <= count { focus = stack; }
                                if member.is_some() { member = if stack < count { widgets.stacks[stack].modules.first().copied() } else { (0..CARD_MODULES.len()).find(|m| widgets.location(*m).is_none()) }; }
                            }
                        }
                    } else if action == Control::Widget(1) && key == KeyCode::Down { stack = 0; focus = 0; }
                    else if key == KeyCode::Up { focus = stack; }
                    else if key == KeyCode::Left { focus = focus.saturating_sub(1).max(widgets.stacks.len() + 1).min(controls.len() - 1); }
                    else { focus = (focus + 1).min(controls.len() - 1); }
                    continue;
                }
                if !matches!(key, KeyCode::Enter | KeyCode::Char(' ')) { continue; }
                match action {
                    Control::Stack(index) => {
                        stack = index;
                        if let Some(module) = placement {
                            if editable(2) && index < widgets.stacks.len() {
                                let destination = widgets.stacks[index].id.clone();
                                widgets.remove(module);
                                stack = widgets.stacks.iter().position(|s| s.id == destination).unwrap();
                                widgets.stacks[stack].modules.push(module); placement = None; member = Some(module); remembered = module; focus = stack; message = "Unsaved Widgets changes".into();
                            }
                        } else if let Some(module) = member {
                            if editable(2) {
                                if widgets.location(module).is_some() { widgets.remove(module); stack = widgets.stacks.len(); focus = stack; member = Some(module); }
                                else if !widgets.stacks.is_empty() { placement = Some(module); stack = 0; focus = 0; message = "Select a stack; Enter/Space adds, Escape cancels".into(); }
                                else { message = "Use New stack to enable this entry".into(); }
                            }
                        } else {
                            member = if index < widgets.stacks.len() { widgets.stacks[index].modules.first().copied() } else { (0..CARD_MODULES.len()).find(|m| widgets.location(*m).is_none()) };
                            if let Some(module) = member { remembered = module; }
                        }
                    }
                    Control::GridTools => { grid_tools = !grid_tools; if !grid_tools { focus = stack; } },
                    Control::Widget(1) => widgets.enabled[1] = !widgets.enabled[1],
                    Control::GridAction(index) if editable(2) => {
                        match index {
                            0 => { widgets.new_stack(remembered); stack = widgets.location(remembered).unwrap().0; member = Some(remembered); },
                            1 if stack < widgets.stacks.len() => { widgets.stacks.remove(stack); member = None; },
                            2 => if let Some((s, pos)) = widgets.location(remembered) { let module = widgets.stacks[s].modules.remove(pos); widgets.stacks[s].modules.insert(0, module); },
                            3 | 4 => widgets.reorder_member(remembered, index == 4),
                            5 | 6 if stack < widgets.stacks.len() => { let next = if index == 5 { stack.saturating_sub(1) } else { (stack + 1).min(widgets.stacks.len() - 1) }; widgets.stacks.swap(stack, next); stack = next; },
                            7 => { widgets.remove(remembered); stack = widgets.stacks.len(); member = Some(remembered); }, _ => (),
                        }
                        focus = stack.min(widgets.stacks.len()); message = "Unsaved Widgets changes".into();
                    }
                    Control::Apply => message = match widgets.save_subset(&["windowSwitcher", "cardStacks"]) { Ok(text) => text, Err(error) => error.to_string() },
                    _ => (),
                }
                continue;
            }
            if matches!(key, KeyCode::Up | KeyCode::Down) {
                cycle(&mut focus, controls.len(), key == KeyCode::Down);
                if let Control::Preview(index) = controls[focus] { preview = index; colours = theme_colours(&appearance.themes[preview]).unwrap_or(colours); }
                continue;
            }
            let current = controls[focus];
            let forward = key != KeyCode::Left;
            let change = matches!(key, KeyCode::Left | KeyCode::Right);
            activate |= matches!(key, KeyCode::Enter | KeyCode::Char(' '));
            if !change && !activate { continue; }
            match current {
                Control::Preview(index) => { preview = index; colours = theme_colours(&appearance.themes[index]).unwrap_or(colours); },
                Control::Theme if activate => { subpage = 1; preview = appearance.theme; focus = preview; },
                Control::Taskbar if activate => { taskbar = widgets.clone(); subpage = 2; focus = 0; },
                Control::Back if activate => { subpage = 0; focus = 0; colours = theme_colours(&appearance.themes[appearance.theme]).unwrap_or(colours); },
                Control::Transparency | Control::Layout => {
                    let (choices, index, command) = if current == Control::Transparency { (TRANSPARENCY, appearance.transparency, "transparency") } else { (LAYOUTS, appearance.layout, "layout") };
                    let next = (index + if forward { 1 } else { choices.len() - 1 }) % choices.len();
                    message = appearance_command(&[command, choices[next]]).unwrap_or_else(|error| error.to_string());
                    match Appearance::load() { Ok(value) => appearance = value, Err(error) => message.push_str(&format!(" Could not refresh appearance state: {error}")) }
                }
                Control::Wallpaper if activate => {
                    message = match picker(&mut terminal) { Ok(Some(path)) => appearance_command(&["wallpaper", &path.to_string_lossy()]).unwrap_or_else(|e| e.to_string()), Ok(None) => "".into(), Err(error) => error.to_string() };
                    crossterm::execute!(io::stdout(), event::EnableMouseCapture)?;
                    if let Ok(value) = Appearance::load() { appearance = value; }
                }
                Control::Monitors if activate => {
                    // Re-read permissions immediately before handing terminal ownership over.
                    appearance = Appearance::load()?;
                    if appearance.readonly[3] { message = "Monitors - Read Only".into(); continue; }
                    crossterm::execute!(io::stdout(), event::DisableMouseCapture)?; ratatui::restore();
                    let status = Command::new("hyprmon").status();
                    terminal = ratatui::init(); crossterm::execute!(io::stdout(), event::EnableMouseCapture)?;
                    message = match status { Ok(status) => format!("HyprMon exited {status}; live/save changes remain"), Err(error) => format!("Hyprmon Unavailable: {error}") };
                }
                Control::Bar(index) => { if index == 0 { taskbar.bar[0] = if taskbar.bar[0] == 3 { if forward { 0 } else { 2 } } else { (taskbar.bar[0] + if forward { 1 } else { 2 }) % 3 }; } else { cycle(&mut taskbar.bar[index], BAR_SETTINGS[index].2.len(), forward); } },
                Control::BarWidth => taskbar.width = if forward { (taskbar.width + 1).min(100) } else { taskbar.width.saturating_sub(1).max(50) },
                Control::Widget(0) => { widgets.enabled[0] = !widgets.enabled[0]; message = match widgets.save_subset(&["notificationToasts"]) { Ok(text) => text, Err(error) => { widgets.enabled[0] = !widgets.enabled[0]; error.to_string() } }; },
                Control::Steam => { let previous = *steam; cycle(steam, 3, forward); if previous == 0 { selected.insert("gamescope", true); } if *steam == 0 { selected.insert("gamescope", false); } if !handheld_available(*steam, selected) { selected.insert("handheld", false); } },
                Control::Utility(id) => { selected.insert(id, !selected[id]); if !handheld_available(*steam, selected) { selected.insert("handheld", false); } },
                Control::Overwrite => overwrite = !overwrite,
                Control::Apply if activate && subpage == 1 => {
                    message = appearance_command(&["theme", &appearance.themes[preview]]).unwrap_or_else(|error| error.to_string());
                    match Appearance::load() { Ok(value) => appearance = value, Err(error) => message.push_str(&format!(" Could not refresh appearance state: {error}")) }
                    subpage = 0; focus = 0;
                }
                Control::Apply if activate && subpage == 2 => {
                    taskbar.revision = widgets.revision.clone();
                    message = match taskbar.save_subset(&["barBehaviour", "barLocation", "barStyle", "barWidth", "oskAccess"]) {
                        Ok(text) => { widgets.bar = taskbar.bar; widgets.width = taskbar.width; widgets.revision = taskbar.revision.clone(); subpage = 0; focus = 4; text }, Err(error) => error.to_string(),
                    };
                }
                Control::Apply if activate && page == 0 => return Ok(Some(overwrite)),
                _ => (),
            }
        }
    })();
    let _ = crossterm::execute!(io::stdout(), event::DisableMouseCapture);
    ratatui::restore();
    result
}
fn hotkeys(widgets: &Widgets, settings: &HotkeySettings, screenshot: bool, width: usize, heading: Style) -> (Vec<Line<'static>>, Vec<(usize, usize, usize)>) {
    let taskbar = match widgets.bar[0] { 2 => "toggle on press", 3 => "legacy always visible", _ => "hold to show; release hides" };
    let mut lines = Vec::new();
    let mut actions = Vec::new();
    for title in ["Common", "Applications", "Windows", "Workspaces", "Desktop / session"] {
        if !lines.is_empty() { lines.push(Line::default()); }
        lines.push(Line::from(title).style(heading));
        lines.push(Line::default());
        for (index, action) in settings.actions.iter().enumerate().filter(|(_, a)| a.categories.iter().any(|c| c == title)) {
            let start = lines.len();
            let label = if action.id == "screenshot" && !screenshot { "Screenshot (disabled)".to_owned() }
                else if action.id == "switcher" && !widgets.enabled[1] { format!("{} (disabled)", action.label) }
                else if settings.live && !action.available { format!("{} (unavailable)", action.label) }
                else { action.label.clone() };
            let value = if settings.live && !action.available { "—".to_owned() } else { hotkey_label(&settings.values[index]) };
            lines.extend(columns(&label, &value, 23, width).into_iter().map(Line::from));
            if settings.live { actions.push((start, lines.len(), index)); }
        }
        let note = match title {
            "Windows" => "Scrolling left/right uses columns. Monocle focus cycles; directional swap and resize have no effect.",
            "Desktop / session" => "Cards: Bluetooth, network, audio and layout.", _ => "",
        };
        if !note.is_empty() {
            lines.push(Line::default());
            lines.extend(wrap_cells(note, width).into_iter().map(Line::from));
        }
    }
    lines.push(Line::default());
    let help = format!("Taskbar: {taskbar}. Window switcher requires its preference enabled.\nShipped Icewine bindings. Host/user overrides can change them; optional tools and the active layout affect availability. Up/Down or mouse wheel scrolls.");
    lines.extend(wrap_cells(&help, width).into_iter().map(Line::from));
    (lines, actions)
}

fn executable(name: &str) -> bool {
    use std::os::unix::fs::PermissionsExt;
    std::env::split_paths(&std::env::var_os("PATH").unwrap_or_default()).any(|path| {
        path.join(name).metadata().is_ok_and(|info| info.is_file() && info.permissions().mode() & 0o111 != 0)
    })
}

fn review_utilities(lines: Vec<String>) -> io::Result<bool> {
    let mut terminal = ratatui::init();
    let result = (|| {
        crossterm::execute!(io::stdout(), event::EnableMouseCapture)?;
        let mut scroll = 0u16;
        let mut apply = false; // Review starts on Back.
        loop {
            let mut buttons = [Rect::default(); 2];
            terminal.draw(|frame| {
                if frame.area().width < 80 || frame.area().height < 24 {
                    frame.render_widget(Paragraph::new("Icewine needs an 80 x 24 terminal.\nResize to continue; Esc: cancel."), frame.area()); return;
                }
                let area = frame.area();
                let inner = Rect::new(area.x + 2, area.y + 1, area.width - 4, area.height - 2);
                frame.render_widget(Block::bordered().border_type(BorderType::Rounded), area);
                frame.render_widget(Paragraph::new("Utilities / Review"), Rect::new(inner.x, inner.y, inner.width, 1));
                frame.render_widget(Paragraph::new(format!("├{}┤", "─".repeat(area.width as usize - 2))), Rect::new(area.x, area.y + 2, area.width, 1));
                let body = Rect::new(inner.x, area.y + 4, inner.width, inner.height - 7);
                frame.render_widget(Paragraph::new(lines.join("\n")).wrap(Wrap { trim: false }).scroll((scroll, 0)), body);
                buttons = [Rect::new(inner.x, inner.bottom() - 3, 9, 1), Rect::new(inner.x + 12, inner.bottom() - 3, 8, 1)];
                for (index, label) in ["[ Apply ]", "[ Back ]"].iter().enumerate() {
                    frame.render_widget(Paragraph::new(*label).style(if apply == (index == 0) { Style::default().fg(Color::Black).bg(Color::Cyan) } else { Style::default().fg(Color::Cyan) }), buttons[index]);
                }
                frame.render_widget(Paragraph::new("Up/Down: scroll   Left/Right: action   I: apply   Esc: Back"), Rect::new(inner.x, inner.bottom() - 1, inner.width, 1));
            })?;
            match event::read()? {
                Event::Key(key) if key.kind == KeyEventKind::Press => match key.code {
                    KeyCode::Esc | KeyCode::Char('q') => return Ok(false),
                    KeyCode::Char('c') if key.modifiers.contains(event::KeyModifiers::CONTROL) => return Ok(false),
                    _ if terminal.size()?.width < 80 || terminal.size()?.height < 24 => (),
                    KeyCode::Down => scroll = scroll.saturating_add(1).min(lines.len().saturating_mul(3) as u16),
                    KeyCode::Up => scroll = scroll.saturating_sub(1),
                    KeyCode::Left | KeyCode::Right | KeyCode::Tab | KeyCode::BackTab => apply = !apply,
                    KeyCode::Enter | KeyCode::Char(' ') => return Ok(apply),
                    KeyCode::Char('i') => return Ok(true), _ => (),
                },
                Event::Mouse(mouse) if terminal.size()?.width >= 80 && terminal.size()?.height >= 24 => match mouse.kind {
                    event::MouseEventKind::Down(event::MouseButton::Left) => {
                        if buttons[0].contains(Position::new(mouse.column, mouse.row)) { return Ok(true); }
                        if buttons[1].contains(Position::new(mouse.column, mouse.row)) { return Ok(false); }
                    }
                    event::MouseEventKind::ScrollDown => scroll = scroll.saturating_add(1).min(lines.len().saturating_mul(3) as u16),
                    event::MouseEventKind::ScrollUp => scroll = scroll.saturating_sub(1), _ => (),
                }, _ => (),
            }
        }
    })();
    let _ = crossterm::execute!(io::stdout(), event::DisableMouseCapture);
    ratatui::restore();
    result
}

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
                let area = frame.area();
                let inner = Rect::new(area.x + 2, area.y + 1, area.width - 4, area.height - 2);
                frame.render_widget(Block::bordered().border_type(BorderType::Rounded), area);
                frame.render_widget(Paragraph::new(title.trim()), Rect::new(inner.x, inner.y, inner.width, 1));
                frame.render_widget(Paragraph::new(format!("├{}┤", "─".repeat(area.width as usize - 2))), Rect::new(area.x, area.y + 2, area.width, 1));
                let body = Rect::new(inner.x, area.y + 4, inner.width, inner.height - 6);
                let help = Rect::new(inner.x, inner.bottom() - 2, inner.width, 2);
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
            name.strip_prefix("icewine-")
                .and_then(|name| name.split_once("-x86_64.pkg.tar."))
                .and_then(|(version, extension)| version.rsplit_once('-').filter(|_| !extension.is_empty()))
                .is_some_and(|(version, release)| [version, release].iter().all(|value|
                    value.split('.').all(|part| !part.is_empty() && part.bytes().all(|c| c.is_ascii_digit()))))
                && !name.ends_with(".sig")
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
        "Then review the utility selections in the installed manager before applying them.".into(),
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
        return Err("A terminal is required; run icewine from a TTY".into());
    }
    let args = std::env::args().collect::<Vec<_>>();
    if args.len() == 4 && args[1] == "--bootstrap" { return bootstrap(&args[2], &args[3]); }
    if args.len() != 1 { return Err("Usage: icewine".into()); }
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
        if selected["texteditor"] { plan.push("Terminal Editor: isolated icewine-nvim data; Arch first launch downloads LazyVim plugins. Personal nvim and host EDITOR/VISUAL stay unchanged.".into()); }
        plan.push(if overwrite { "Overwrite selected defaults WITHOUT backups.".into() }
            else { "Preserve existing dotfiles; create missing defaults. btop selects the Icewine theme in regular configs.".into() });
        plan.push(if readonly { "Host services and device permissions remain host policy.".into() }
            else { "Host prerequisites: services/device permissions; Multilib for native Steam; private packages for Handheld.".into() });
        plan.push("Earlier package/file changes can remain after failure or interruption. Retry Apply after resolving the error.".into());
        plan.push("Cancel leaves utility choices unapplied; earlier Appearance changes remain.".into());
        if !review_utilities(plan)? { return Ok(ExitCode::SUCCESS); }
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
