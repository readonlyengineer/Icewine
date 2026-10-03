#!/usr/bin/env python3
"""Exercise connector selection with fake sysfs and brightness commands."""
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile

helper = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    drm = root / "class/drm"
    backlights = root / "class/backlight"
    binaries = root / "bin"
    for path in (drm, backlights, binaries):
        path.mkdir(parents=True)
    log = root / "calls"
    for name, body in {
        "brightnessctl": '''if [[ -n ${BRIGHTNESS_STATE:-} ]]; then
    case "${*: -1}" in
    get) value=$(<"$BRIGHTNESS_STATE"); sleep 0.2; echo "$value";;
    max) echo 200;;
    *%) value=${*: -1}; echo $(( ${value%%%} * 2 )) > "$BRIGHTNESS_STATE";;
    esac
else
    case "${*: -1}" in
    get) echo 40;;
    max) echo 200;;
    esac
fi''',
        "ddcutil": '''if [[ " $* " == *" getvcp "* ]]; then
    printf '%s\\n' "${DDC_RESPONSE:-VCP 10 C 80 200}"
fi''',
        "hyprctl": '''[[ "$*" == "monitors -j" ]] || exit 1
printf '%s\\n' "${MONITORS_JSON:-[]}"''',
    }.items():
        path = binaries / name
        path.write_text('#!' + shutil.which('bash') + '\n'
                        'printf "%s\\n" "$0 $*" >> "$CALL_LOG"\n' + body + '\n')
        path.chmod(0o755)
    env = dict(os.environ, ICEWINE_SYSFS_ROOT=str(root), CALL_LOG=str(log),
               XDG_RUNTIME_DIR=str(root),
               PATH=str(binaries) + os.pathsep + os.environ['PATH'])

    def connector(name):
        path = drm / name
        path.mkdir()
        (path / "status").write_text("connected\n")
        return path

    def run(monitor, value=None, ok=True, response=None, monitors=None):
        log.write_text("")
        result = subprocess.run(['bash', str(helper), monitor]
                                + ([] if value is None else [str(value)]),
                                env=env | ({'DDC_RESPONSE': response} if response else {})
                                | ({'MONITORS_JSON': monitors} if monitors else {}),
                                capture_output=True, text=True)
        assert (result.returncode == 0) == ok, (result.stdout, result.stderr)
        return result.stdout.strip(), log.read_text()

    internal = connector('card1-eDP-1')
    panel = internal / 'intel_backlight'
    panel.mkdir()
    (backlights / 'intel_backlight').symlink_to(panel)
    assert run('eDP-1')[0] == '20'
    assert '--device=intel_backlight --min-value=1 set 55%' in run('eDP-1', 55)[1]
    assert '--device=intel_backlight --min-value=1 set 25%' in run('focused', '+5',
        monitors='[{"name":"eDP-1","focused":true}]')[1]
    assert '--device=intel_backlight --min-value=1 set 15%' in run('focused', '-5',
        monitors='[{"name":"eDP-1","focused":true}]')[1]
    state = root / 'brightness-state'
    state.write_text('40\n')
    commands = [['bash', str(helper), 'eDP-1', '+5']] * 2
    processes = [subprocess.Popen(command, env=env | {'BRIGHTNESS_STATE': str(state)},
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for command in commands]
    for process in processes:
        out, err = process.communicate(timeout=10)
        assert process.returncode == 0, (out, err)
    assert state.read_text().strip() == '60', 'overlapping repeat steps were lost'
    assert run('focused', '+5', ok=False)[1].endswith('hyprctl monitors -j\n')
    assert run('focused', '+5', ok=False,
        monitors='[{"name":"eDP-1","focused":true},{"name":"DP-1","focused":true}]')[1].endswith('hyprctl monitors -j\n')

    external = connector('card1-DP-1')
    (external / 'ddc/i2c-dev/i2c-7').mkdir(parents=True)
    assert run('DP-1')[0] == '40'
    value, calls = run('DP-1', 25)
    assert value == '25' and '--bus 7 setvcp 10 50' in calls
    assert '--bus 7 setvcp 10 90' in run('focused', '+5',
        monitors='[{"name":"eDP-1","focused":false},{"name":"DP-1","focused":true}]')[1]
    assert 'brightnessctl' not in calls
    assert run('DP-1', 0)[0] == '0'
    assert run('DP-1', 100)[0] == '100'
    assert 'setvcp' not in run('DP-1', 50, ok=False, response='VCP 10 ERR')[1]
    run('DP-1', ok=False, response='VCP 10 C 4 0')
    run('DP-1', ok=False, response='VCP 10 C 201 200')

    # A second identical monitor uses its connector's bus, not EDID or display order.
    other = connector('card1-DP-2')
    (other / 'i2c-8/i2c-dev/i2c-8').mkdir(parents=True)
    assert '--bus 8 setvcp 10 100' in run('DP-2', 50)[1]
    connector('card2-DP-1')
    assert run('DP-1', 50, ok=False)[1] == ''
    connector('card1-HDMI-A-1')
    assert run('HDMI-A-1', 50, ok=False)[1] == ''
    for name, value in [('missing', None), ('../eDP-1', None), ('eDP-1', 101),
                        ('eDP-1', '-1'), ('eDP-1', '09'), ('eDP-1', '1;id')]:
        assert run(name, value, ok=False)[1] == ''

    # Unassociated ACPI backlights are only inferred for a single internal panel.
    (backlights / 'intel_backlight').unlink()
    (backlights / 'acpi_video0').mkdir()
    assert '--device=acpi_video0' in run('eDP-1')[1]
    connector('card2-eDP-2')
    assert run('eDP-1', 50, ok=False)[1] == ''

print('monitor brightness checks passed')
