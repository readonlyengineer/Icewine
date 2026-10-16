# Developing cards

`modules/topbar/Card.qml` owns a widget's surface and constrained geometry.
`CardStack.qml` arranges cards without a background, border or padding item.
`Widget.qml` remains the topbar's reveal, engagement, Escape and dismissal host.
These are first-party QML components, not a plugin API or dynamic registry.

This is the implemented card contract. The separate style-guide ticket owns
`widget-plugin-standard.md` and the other draft guides; its draft card guidance
is superseded by this document pending that ticket's link/update. Do not copy
its proposed plugin/service framework into a card.

## Surface and content

Create a `Card`, give it natural `implicitWidth`/`implicitHeight`, and place
content inside it. Cards default to the existing dark background, radius 12,
no border and rectangular clipping. Titles are plain text without hover/selection
fill or a border. Do not add a
decorative card border. There is no mandatory title or content inset.
Content keeps its own established margins and scrolling. Card clipping bounds
children to the card; it does not create a rounded mask.

Set `stack` to the enclosing `CardStack` and list the card in the stack's `cards`
in index order. `index` defaults to zero; set subsequent indices to one/two.
The host supplies the stack's actual width and height. A single card fills it
at (0, 0), with no geometry deduction. The existing two-card presentation uses
34px horizontal and 64px vertical allowance, an 18px/48px front offset, and the
existing 120ms reversible exchange. The stack clips the sweep and draws no
frame or focus underline.

The supported compositions are one, two or three cards. Three cards keep the
same outer allowance and front offset; the next card in cyclic declared order
rests at 9px/24px behind the front and the other at 0px/0px (all inside the
existing 8px inset). Both rear strips are exposed. Each exchange still moves
one front/rear pair for 120ms; the third card interpolates its rear position.
Requesting the outgoing card reverses the sweep. Requesting the third card
during motion queues the latest intent until the current sweep completes,
then exchanges again, without jumping moving surfaces. Arrow/motion-key cycles
advance from the queued intent when present. Content stays inert between sweeps.

Changing membership cancels motion and queued/pending motion-key activation,
closes transient menus through `selectionChanging()`, and resets selection/front
geometry to the first card. Focus returns to its `initialFocus` only if the
available stack already owns focus. Destroy optional cards through their owner
Loader; nonempty content updates retain the same card. Larger decks, reordering
and user-configurable groupings require their own interaction design.

Expose `initialFocus` as a control inside the card, or keep the shared
`selector` default. Set `accessibleName` to identify the card. The stack exposes
`initialFocus` for its selected card, or a stationary target during motion.
Call `selectCard(index)` to exchange cards; do not assign `selectedCard`
directly. Clicking any exposed rear-card surface promotes it, consuming the
gesture
without activating content. The shared card intercepts rear/moving input above
content; front controls keep normal input and front title clicks do nothing.
Keep content below that selection interception (`z: 100`). Hover and
focus alone do not select cards. The shared
`selector` remains a Tab-accessible radio target: Return, Enter and Space select
its card on release. Card selection draws no underline; focused controls retain
their own indicators. The stationary motion target uses the same keys to cycle on
release. Keep a valid focus target even if the card has no enabled controls.
`selectionChanging()` lets an owner close transient menus before motion.

For the supported fixed compositions, unmodified Left selects the previous card and
Right the next in declared `cards` order, wrapping at either end. With two cards
both directions reach the other card; the existing sweep reverses when selecting
the outgoing card during motion. Three-card requests follow the queue above.
Navigation runs after child key handling. Plain stack/card/shared-selector/motion
focus targets and ordinary native buttons/toggles (`AbstractButton` descendants)
can navigate with an unhandled arrow. Menu items, radio buttons and tab buttons
remain reserved contexts. Other focused controls, including text editing,
sliders and scrollbars, retain arrows even when ignoring an endpoint event.
Native nested menus retain their own key routing.

Set a card's `arrowKeyOwners` to custom controls or composite groups that own
Left/Right when their focus target could otherwise navigate. This reserves each
listed item and its descendants, including ignored endpoint keys. For example,
`arrowKeyOwners: [directionalButton, horizontalGroup]` protects a custom button
and a group containing buttons whose arrows move focus. Authors must declare
such owners; an ignored event cannot reveal that a custom control owns a key.
This also applies to native directional containers with focusable button children.
Plain `ButtonGroup` membership alone does not handle arrows in the installed Qt;
unhandled arrows from those buttons navigate without changing their checked state.
No reservation is needed for ordinary non-owning `ActionButton`/`Toggle` callers.
The first press selects immediately; auto-repeat presses are consumed without
further selection and release does nothing. A fresh opposite press during motion
can reverse selection. Focus moves through the stationary target to the selected
card's `initialFocus`. Hidden, disabled and
single-card stacks do not consume or navigate with arrows. Return, Enter and
Space still activate on release; a superseding selection change cancels pending
motion-target activation even when focus stays stationary.

## Visibility, services and host ownership

`Card.active` means selected and in an available, settled stack (or visible
and enabled when used without a stack). Bind interactive content's `enabled`
and recurring polling/scanning to this state. An unselected card may remain
painted; existence and visibility alone do not authorize work or focus.
`CardStack.available` normally follows its visibility and enabled state;
a modal owner can additionally disable it. Unavailability settles motion.
Do not call focus-entry methods when a card is inactive.

Pass existing services through explicit QML properties. Keep asynchronous
mutation ownership outside disposable content loaders when feedback must
survive selection or page changes. Cancel recurring work on inactivity;
do not cancel an intended in-flight mutation just because its card is hidden.
Network remains a retained operation owner in `StatusPopout`: its password,
connection feedback and Tailscale process ownership stay local, scanning and
polling stop when unavailable, and its content is not recreated by exchange.

For disposable pages, enable the content only while active and use an active
Loader to stop page-local work. Retain state/services outside that loader when
needed. `StatusPopout` wraps its ordinary pages in one shared card, preserves
page dependency injection, and retains its existing focused-control scroll
reveal. Pages retain responsibility for their constrained Flickable/ListView.

`LauncherCard` owns application search, `initialFocus`, `focusInitial()` and
`excludeSteamApps`. Set `engaged` from the host. Its `handoffRequested()` must
reach the existing host handoff before application execution; rear/inactive
launch requests are ignored. `Launcher.qml` owns the existing tray model and
exposes `backgroundCount`/`backgroundAttention`. It adds a Background Apps card
only for nonempty tray contents. Layout joins when `layoutsEnabled`, reusing
`LayoutPicker` and the supplied compositor in a constrained ScrollView. Declared
order is Launcher → Background Apps (if any) → Layout (if enabled). The single
card remains 400×424; two/three cards add the shared 34×64 allowance, constrained
by the panel. Layout's initial focus is Autofullscreen when available, otherwise
its selector. Its ScrollView reserves content arrows and reveals focused controls
when constrained; use the card selector to navigate the stack. Selection alone
never changes a layout. `Launcher.layoutActive`
follows the settled card; Topbar aggregates only the owning monitor and passes
activity to the existing Desktop/Handheld compositor adapter. Feature disablement
removes Layout, repairs selection, and routes an explicit Layout page back to
Launcher. No new backend, poller or service is involved.

Ordinary `Launcher.focusInitial()` follows the selected card, including its
active menu. Explicit launcher requests call `openLauncher()`: this uses
`CardStack.resetSelection()` to cancel motion, close the tray menu and focus
search. Explicit Layout entry uses `openLayout()` in the same host; Topbar carries
the requested page through deferred focus routing. Hidden monitor instances do
not take focus. Do not use opening intent for generic focus restoration. Background
Apps keeps app selection and active menus by item identity through nonempty
updates, closes menus on inactivity/removal and cancels deferred menu focus
when inactive.

## Register and compose

There is no registry: import the topbar QML directory and explicitly instantiate
a card. To add a production status page, add its component and page-name branch
to `StatusPopout.qml`, pass dependencies there, and add its existing topbar entry.
A standalone host forwards Widget engagement/dismissal/handoff to the existing
shell controller. Do not create a second reveal animation or service owner in
the card.

A minimal one-card composition (with a service supplied by its owner):

```qml
Bar.CardStack {
    id: stack
    width: 380; height: 240
    cards: [card]
    Bar.Card {
        id: card
        stack: stack
        implicitWidth: 380
        implicitHeight: page.item?.implicitHeight ?? 0
        initialFocus: page.item?.initialFocus ?? null
        Loader {
            id: page
            anchors.fill: parent
            active: card.active
            sourceComponent: Popouts.Media { player: suppliedPlayer }
        }
    }
}
```

For a pair, use `cards: [launcher, companion]`, set both cards' `stack`, and set
`companion.index: 1`. `tests/controls.py` contains an executable composition of
`LauncherCard` and a companion card: it verifies one-card geometry at two sizes,
shared exchange, selected focus/activity and launcher handoff through a mocked
`uwsm`. The same check exercises the production launcher's optional tray card,
identity-preserving updates, removal during motion and explicit-open focus routing.
It also checks the production Layout grouping, all three rear/front orders,
queued third-card motion, optional removal, current-workspace controls and
pending/unavailable focus. Use these fixtures when extending composition.

Run `python3 tests/controls.py .` with the installed `qs` on PATH. This exercises
real QML geometry, exchange/reversal, keyboard/touch selection, scrolling,
retained operations and inactive network work with synthetic services. It does
not establish native application activation, compositor focus restoration,
real pointer/touch feel, theme appearance or device/network backend behavior;
check these in the desktop session after authorized application.
