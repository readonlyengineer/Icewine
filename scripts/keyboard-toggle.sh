set -eu
systemctl --user start icewine-keyboard.service
case "$(busctl --user --timeout=2 get-property sm.puri.OSK0 /sm/puri/OSK0 sm.puri.OSK0 Visible)" in
  'b true') visible=false ;;
  'b false') visible=true ;;
  *) echo 'Could not read on-screen keyboard visibility' >&2; exit 1 ;;
esac
busctl --user --timeout=2 call sm.puri.OSK0 /sm/puri/OSK0 sm.puri.OSK0 SetVisible b "$visible"
qs ipc call topbar osk "$visible" || true
