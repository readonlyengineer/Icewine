# Gamescope patches

These resources are archived. Icewine no longer applies Gamescope patches or
exports the `gamescope-focus` check. The descriptions and verification records
below document the former integration, not the current configuration.

Icewine owns the keyboard-focus patch and applies it in `modules/default.nix`
whenever `services.icewine.enable` is enabled, including laptops and handhelds.
The experimental upstream touch patches remain in `modules/handheld.nix` and
apply only to handhelds. Host configurations do not carry the patches.

## Preserve keyboard focus state

`preserve-keyboard-focus-state.patch` targets Gamescope 3.16.28, upstream commit
`fa0b4d3342078f01eadff0193e09c3b561f40c03`, as pinned by Icewine's `flake.lock`.
Its declaration hunk also applies to 3.16.29, which downstream configurations
can select when Icewine follows their newer Nixpkgs input. There is no upstream
issue or PR for this local patch yet.

Reproduction reported on the Deck:

1. Put Steam inside Gamescope and Kitty in the same workspace, with no other windows.
2. Focus Kitty and press Super+Q.
3. Press Enter (or the controller button mapped to Enter) on Kitty's close prompt.
4. Kitty closes and Gamescope gains focus; Steam also acts on Enter.

Gamescope's host Wayland keyboard-enter handler previously sent each inherited
held key through the ordinary keypress/hotkey path. The patch supplies the
snapshot through the nested seat's enter event instead. It also propagates the
matching keymap and modifiers, clears seat focus on host leave, maintains the
forwarded held-key state, and pairs shortcut releases with their original
presses. The selected internal surface is retained while host focus is absent;
existing surface-destruction handling clears it if the window disappears.

This is a keyboard fix, including controller buttons mapped to keyboard events.
It does not change native gamepad or pointer focus policy. The other backend
entry points retain their existing input path. A failed Wayland initialization
still permits SDL fallback.

The pinned wlroots keyboard state holds at most 32 keys. An oversized entry
snapshot is rejected with a log message and leaves keyboard focus disabled until
a valid subsequent entry, rather than restoring partial state. Supporting larger
snapshots would require extending wlroots' keyboard-state capacity.

Background:

- Original state-replay change: <https://github.com/ValveSoftware/gamescope/commit/cd03b2607c86d9c50bb2bc8631fd83baf7e31e85>
- Keyboard enter/leave protocol: <https://wayland.freedesktop.org/docs/html/apa.html#protocol-spec-wl_keyboard>

## Check

From the Icewine checkout:

```sh
nix build --no-write-lock-file --no-link path:.#checks.x86_64-linux.gamescope-focus
```

Verified locally: the patched package builds and this check passes. A separate
code-review agent's findings were addressed: consumed hotkeys entering client
state, unmatched shortcut releases leaving held keys behind, focus on an
initially unfocused launch, and the focus gate leaking into SDL fallback after
failed Wayland initialization. The final review found no remaining actionable
blockers.

The check requires the focus patch exactly once in both desktop/laptop and
handheld package variants, applies each complete patch stack, compiles both
Gamescope variants, and runs `check-focus.py` against each. That script extracts the
changed production handlers and compiles them into an assert-based C++ check
with an in-memory seat. It covers inherited Enter, subsequent real presses,
modifier snapshots, internal focus changes, missing selected surfaces, hotkey
consumption, Meta release ordering, and oversized snapshots. A structural check
keeps the initial focus gate after the Wayland initialization failure paths.

The handler test can also be run on an already-patched source tree:

```sh
CXX=c++ python3 patches/gamescope/check-focus.py /path/to/patched/gamescope
```

The test doubles do not verify wlroots wire delivery, actual XKB interpretation,
or Xwayland/Steam behaviour. The original reproduction and before/after Wayland
traces remain to be checked in the VM once Gamescope startup and Steam setup are
working. The VM network policy is not changed by this patch.

Before removing or rebasing the patch after an upstream update, repeat the check
and the original reproduction, plus held Shift/Ctrl, held movement keys, and
closing/changing the selected game while Gamescope lacks host focus.
