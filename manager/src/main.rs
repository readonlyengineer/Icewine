use std::{io, process::{Command, ExitCode}};
use crossterm::event::{self, Event, KeyCode, KeyEventKind};
use ratatui::{prelude::*, widgets::{Block, BorderType, Cell, Padding, Paragraph, Row, Table}};

const ROWS: [(&str, &str); 8] = [
    ("Desktop session", "Hyprland + Icewine Quickshell"),
    ("Terminal", "Kitty"), ("Text editor", "Nano"), ("File manager", "Yazi"),
    ("Gaming (allows unfree)", "Steam + Gamescope"),
    ("Flatpak Utility", "Prefer Flatpak Steam if Gaming + Bazaar"),
    ("Login screen", "SDDM"), ("Shell Extras", "Starship + Fastfetch"),
];

fn choose(readonly: bool, selected: &mut [bool; 8]) -> io::Result<Option<bool>> {
    let mut terminal = ratatui::init();
    let result = (|| {
        let mut focus = if readonly { 8 } else { 0 };
        let mut overwrite = false;
        loop {
            terminal.draw(|frame| {
                let accent = Style::default().fg(Color::Cyan).bold();
                let muted = Style::default().fg(Color::DarkGray);
                let focused = Style::default().fg(Color::Black).bg(Color::Cyan).bold();
                let [panel] = Layout::horizontal([Constraint::Max(90)])
                    .flex(Flex::Center).areas(frame.area());
                let [panel] = Layout::vertical([Constraint::Max(24)])
                    .flex(Flex::Center).areas(panel);
                let block = Block::bordered().border_type(BorderType::Rounded)
                    .border_style(muted).title(Line::from(" Icewine Installer ").style(accent))
                    .padding(Padding::uniform(1));
                let inner = block.inner(panel);
                frame.render_widget(block, panel);
                let [intro, utilities, notice, reset, buttons, help] = Layout::vertical([
                    Constraint::Length(3), Constraint::Length(10), Constraint::Length(2),
                    Constraint::Length(2), Constraint::Length(2), Constraint::Length(1),
                ]).areas(inner);
                frame.render_widget(Paragraph::new(vec![
                    Line::from("Optional utilities, configured for Icewine."),
                    Line::from("Selected utilities are installed and configured.").style(muted),
                ]), intro);
                let rows = ROWS.iter().enumerate().map(|(i, (purpose, defaults))| {
                    Row::new(vec![
                        Cell::from(*purpose),
                        Cell::from(*defaults).style(muted),
                        Cell::from(if selected[i] { "[x]" } else { "[ ]" })
                            .style(if readonly { muted } else { accent }),
                    ]).style(if focus == i { focused } else { Style::default() })
                });
                frame.render_widget(Table::new(rows, [
                    Constraint::Length(23), Constraint::Min(20), Constraint::Length(9),
                ]).column_spacing(2).header(Row::new([
                    "Purpose", "Defaults", "Configure",
                ]).style(accent).bottom_margin(1)), utilities);
                frame.render_widget(Paragraph::new(if readonly {
                    "NixOS: utility selections are read-only."
                } else {
                    "Deselecting removes Icewine configuration; packages stay installed."
                }).style(muted), notice);
                frame.render_widget(Paragraph::new(format!("[{}] Overwrite existing dotfiles",
                    if overwrite { "x" } else { " " }))
                    .style(if focus == 8 { focused } else { Style::default() }), reset);
                frame.render_widget(Paragraph::new(Line::from(vec![
                    Span::styled("[ Apply ]", if focus == 9 { focused } else { accent }),
                    Span::raw("   "),
                    Span::styled("[ Cancel ]", if focus == 10 { focused } else { muted }),
                ])), buttons);
                frame.render_widget(Paragraph::new(
                    "Tab / arrows: navigate   Space: select   Enter: act   Esc: cancel"
                ).style(muted), help);
            })?;
            let Event::Key(key) = event::read()? else { continue };
            if key.kind != KeyEventKind::Press { continue; }
            match key.code {
                KeyCode::Esc | KeyCode::Char('q') => return Ok(None),
                KeyCode::Char('c') if key.modifiers.contains(event::KeyModifiers::CONTROL) => return Ok(None),
                KeyCode::Tab | KeyCode::Down | KeyCode::Right => {
                    focus = if focus == 10 { if readonly { 8 } else { 0 } } else { focus + 1 };
                }
                KeyCode::BackTab | KeyCode::Up | KeyCode::Left => {
                    focus = if focus == (if readonly { 8 } else { 0 }) { 10 } else { focus - 1 };
                }
                KeyCode::Char(' ') | KeyCode::Enter => match focus {
                    0..=7 if !readonly => selected[focus] = !selected[focus],
                    8 => overwrite = !overwrite,
                    9 => return Ok(Some(overwrite)),
                    10 => return Ok(None),
                    _ => (),
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
    let bits: Vec<_> = state.split_whitespace().collect();
    if bits.len() != 9 || bits.iter().any(|bit| !["0", "1"].contains(bit)) {
        return Err("Invalid manager state".into());
    }
    let readonly = bits[0] == "1";
    let mut selected = std::array::from_fn(|i| bits[i + 1] == "1");
    if let Some(overwrite) = choose(readonly, &mut selected)? {
        let status = Command::new("icewine-manage-backend").arg("apply")
            .args(selected.map(|bit| if bit { "1" } else { "0" }))
            .arg(if overwrite { "1" } else { "0" }).status()?;
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
