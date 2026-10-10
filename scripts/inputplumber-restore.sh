# Called after normal stops and failed starts; never leave raw input on a failed restore.
set -u
if id=$(icewine-inputplumber-intercept device); then
  inputplumber device "$id" intercept set always || exit 1
  inputplumber device "$id" targets set xbox-elite mouse keyboard touchpad || exit 1
  inputplumber device "$id" profile load "${ICEWINE_INPUTPLUMBER_DEFAULT_PROFILE:-/usr/share/inputplumber/profiles/default.yaml}" || exit 1
  inputplumber device "$id" intercept set pass
fi
