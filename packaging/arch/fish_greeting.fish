# Autoload only when the host/user has not already supplied a greeting.
function fish_greeting
    if set -q fish_greeting
        printf '%s\n' $fish_greeting
    else
        fastfetch
    end
end
