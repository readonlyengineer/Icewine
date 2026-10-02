k=$(uname -r)
if [ "$(readlink /run/booted-system/kernel)" = "$(readlink /run/current-system/kernel)" ]; then
  printf 'Linux %s' "$k"
else
  printf 'Linux %s  \033[33m⚠ Restart Required\033[0m' "$k"
fi
