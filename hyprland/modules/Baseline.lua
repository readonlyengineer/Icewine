-- ~/.config/hypr/modules/Baseline.lua
-- Hardware-agnostic baseline: defaults, env vars,
-- global behaviour fixes, and the (commented) permissions reference.
-- Hardware-specific overrides are supplied by the host configuration.

hl.config({
	general = {
		gaps_in          = 5,
		gaps_out         = 10,
		border_size      = 2,
		resize_on_border = false,
		allow_tearing    = false,
		layout           = "scrolling",
	},

	scrolling = {
		column_width             = 1.0,
		fullscreen_on_one_column = false,
		direction                = "right",
		follow_focus             = true,
		focus_fit_method         = 1,
		wrap_focus               = true,
		wrap_swapcol             = false,
		explicit_column_widths   = "0.5, 1.0",
	},

	dwindle = { force_split = 2 }, -- Native right/down placement, independent of cursor.

	misc = {
		focus_on_activate       = true,
		force_default_wallpaper = -1,
		disable_hyprland_logo   = true,
		-- Icewine's desktop identity is intentionally managed by UWSM.
		disable_xdg_env_checks  = os.getenv("XDG_CURRENT_DESKTOP") == "Icewine:Hyprland",
	},

	ecosystem = {
		no_update_news = true,
	},

	input = {
		kb_layout    = "us",
		kb_variant   = "",
		kb_model     = "",
		kb_options   = "",
		kb_rules     = "",
		follow_mouse = 0,
		sensitivity  = 0,
		touchpad = {
			natural_scroll = true,
			disable_while_typing = true,
			tap_to_click = true,
			scroll_factor = 1.0,
			middle_button_emulation = true,
		},
	},

	render = {
		cm_auto_hdr = 1,
		direct_scanout = 2,
	},
})

-- Per-device example (kept commented in case the epic-mouse comes back)
-- hl.device({ name = "epic-mouse-v1", sensitivity = -0.5 })

local editor = os.getenv("EDITOR") or require("icewine.modules.DefaultApps").editor
hl.env("EDITOR", editor)
hl.env("VISUAL", os.getenv("VISUAL") or editor)

-- Global behaviour fixes (template carryover; kept as part of the baseline).

-- Suppress client-driven maximize events globally so they don't fight the
-- scrolling column-width policy.
hl.window_rule({
	name           = "suppress-maximize-events",
	match          = { class = ".*" },
	suppress_event = "maximize",
})

-- Some XWayland apps spawn a transient classless/titleless floating helper
-- that grabs focus while dragging. Deny it focus so the source stays active.
hl.window_rule({
	name  = "fix-xwayland-drags",
	match = {
		class      = "^$",
		title      = "^$",
		xwayland   = true,
		float      = true,
		fullscreen = false,
		pin        = false,
	},
	no_focus = true,
})
