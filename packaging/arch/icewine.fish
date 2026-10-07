# Only the optional CachyOS package installs this; config.fish runs afterwards.
status is-interactive; or return
if not set -q STARSHIP_CONFIG
    set -l config_home "$HOME/.config"
    set -q XDG_CONFIG_HOME; and set config_home "$XDG_CONFIG_HOME"
    set -gx STARSHIP_CONFIG "$config_home/starship.toml"
end

# Defer until host/user configuration has selected its prompt. Preserve it.
function _icewine_prompt_init --on-event fish_prompt
    functions -e _icewine_prompt_init
    set -l location (functions --details fish_prompt)
    if test "$location" = embedded:functions/fish_prompt.fish; or test "$location" = "$__fish_data_dir/functions/fish_prompt.fish"
        starship init fish | source
    end
end
