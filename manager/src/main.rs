use std::{io, process::{Command, ExitCode}};
use crossterm::event::{self, Event, KeyCode, KeyEventKind};
use ratatui::{prelude::*, widgets::Paragraph};

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
                let mut lines = vec![Line::from("Icewine Installer").bold(), Line::from(""),
                    Line::from("Icewine is a quickshell that offers optional configured utilities."),
                    Line::from("Selected utilities are installed and configured."),
                    Line::from("Deselecting utilities removes Icewine configuration"),
                    Line::from("(uninstallation is left to the user)."), Line::from(""),
                    Line::from("Purpose / Defaults / Install & Configure")];
                for (i, (purpose, defaults)) in ROWS.iter().enumerate() {
                    let line = Line::from(format!("{:23} {:39} [{}]", purpose, defaults,
                        if selected[i] { "x" } else { " " }));
                    lines.push(if focus == i { line.reversed() } else { line });
                }
                lines.push(Line::from(if readonly { "NixOS: utility selections are read-only." } else { "" }));
                let line = Line::from(format!("[{}] Overwrite existing dotfiles", if overwrite { "x" } else { " " }));
                lines.push(if focus == 8 { line.reversed() } else { line });
                lines.push(Line::from(""));
                lines.push(Line::from(vec![
                    if focus == 9 { Span::raw("[ Apply ]").reversed() } else { Span::raw("[ Apply ]") },
                    Span::raw(" "),
                    if focus == 10 { Span::raw("[ Cancel ]").reversed() } else { Span::raw("[ Cancel ]") },
                ]));
                lines.push(Line::from("Tab / arrows: navigate   Space: select   Enter: act   Esc: cancel"));
                frame.render_widget(Paragraph::new(lines), frame.area());
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
