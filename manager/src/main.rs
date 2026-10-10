use std::{collections::BTreeMap, io, process::{Command, ExitCode}};
use crossterm::event::{self, Event, KeyCode, KeyEventKind};
use ratatui::{layout::Flex, prelude::*, widgets::{Block, BorderType, Cell, Padding, Paragraph, Row, Table}};

const ROWS: &[(&str, &str, &str)] = &[
    ("desktop", "Desktop session", "Hyprland + Icewine Quickshell"),
    ("terminal", "Terminal", "Kitty"),
    ("filemanager", "File manager", "Yazi"),
    ("steam", "Steam (unfree)", ""),
    ("gamescope", " +- Gamescope", ""), ("handheld", " \u{005c}- Handheld", "Requires Desktop Session, Steam native, and Gamescope"),
    ("login", "Login screen", "SDDM"), ("shellExtras", "Shell Extras", "Starship + Fastfetch"),
];

#[derive(Clone, Copy, PartialEq)]
enum Control { Utility(&'static str), Steam, Overwrite, Apply, Cancel }

const STEAM: &[&str] = &["none", "native", "flatpak"];

fn handheld_available(steam: usize, selected: &BTreeMap<&str, bool>) -> bool {
    steam == 1 && selected["desktop"] && selected["gamescope"]
}

fn choose(readonly: bool, selected: &mut BTreeMap<&str, bool>, steam: &mut usize) -> io::Result<Option<bool>> {
    let mut terminal = ratatui::init();
    let result = (|| {
        let mut focus = 0;
        let mut overwrite = false;
        loop {
            let rows: Vec<_> = ROWS.iter().filter(|(id, _, _)|
                *steam != 0 || !matches!(*id, "gamescope" | "handheld")).collect();
            let controls: Vec<_> = rows.iter().filter(|(id, _, _)| !readonly
                && (*id != "handheld" || handheld_available(*steam, selected)))
                .map(|(id, _, _)| if *id == "steam" { Control::Steam } else { Control::Utility(*id) })
                .chain([Control::Overwrite, Control::Apply, Control::Cancel]).collect();
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
                    .border_style(muted).title(Line::from(" Icewine Installer ").style(accent))
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
                frame.render_widget(Paragraph::new(Line::from(vec![
                    Span::styled("[ Apply ]", if controls[focus] == Control::Apply { focused } else { accent }),
                    Span::raw("   "),
                    Span::styled("[ Cancel ]", if controls[focus] == Control::Cancel { focused } else { muted }),
                ])), buttons);
                frame.render_widget(Paragraph::new(
                    "Tab / up/down: move   Left/right: Steam   Space: select   Enter: act   Esc: cancel"
                ).style(muted), help);
            })?;
            let Event::Key(key) = event::read()? else { continue };
            if key.kind != KeyEventKind::Press { continue; }
            match key.code {
                KeyCode::Esc | KeyCode::Char('q') => return Ok(None),
                KeyCode::Char('c') if key.modifiers.contains(event::KeyModifiers::CONTROL) => return Ok(None),
                KeyCode::Left | KeyCode::Right if controls[focus] == Control::Steam => {
                    let previous = *steam;
                    *steam = (*steam + if key.code == KeyCode::Right { 1 } else { STEAM.len() - 1 }) % STEAM.len();
                    if previous == 0 { selected.insert("gamescope", true); }
                    if *steam == 0 { selected.insert("gamescope", false); }
                    if !handheld_available(*steam, selected) { selected.insert("handheld", false); }
                }
                KeyCode::Tab | KeyCode::Down | KeyCode::Right => {
                    focus = (focus + 1) % controls.len();
                }
                KeyCode::BackTab | KeyCode::Up | KeyCode::Left => {
                    focus = (focus + controls.len() - 1) % controls.len();
                }
                KeyCode::Char(' ') | KeyCode::Enter => match controls[focus] {
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
                    Control::Overwrite => overwrite = !overwrite,
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
