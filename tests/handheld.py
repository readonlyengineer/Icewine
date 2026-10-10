#!/usr/bin/env python3
"""Exercise shared userspace helper lifecycle with explicit fake host commands."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    log = root / 'calls'
    fake = root / 'fake'
    fake.write_text('#!' + sys.executable + '\n' + '''import json, os, sys
name = os.path.basename(sys.argv[0])
args = sys.argv[1:]
with open(os.environ['LOG'], 'a') as log: log.write(json.dumps([name, *args])+'\\n')
if name == 'icewine-inputplumber-intercept' and args == ['device']: print('7')
if name == 'busctl' and 'get-property' in args: print(os.environ.get('VISIBLE', 'b false'))
if os.environ.get('FAIL_MATCH') and os.environ['FAIL_MATCH'] in ' '.join(args): sys.exit(1)
''')
    fake.chmod(0o755)
    for name in ('inputplumber', 'icewine-inputplumber-intercept', 'systemctl', 'busctl', 'qs'):
        (root / name).symlink_to(fake)
    env = dict(os.environ, PATH=str(root)+':'+os.environ['PATH'], LOG=str(log),
               ICEWINE_INPUTPLUMBER_PROFILE_DIR=str(root/'profiles'),
               ICEWINE_INPUTPLUMBER_DEFAULT_PROFILE=str(root/'default.yaml'))
    (root/'default.yaml').write_text('unrelated host profile\n')
    def run(name, **extra):
        log.unlink(missing_ok=True)
        result = subprocess.run(['bash', str(source/'scripts'/name)], env=env|extra, capture_output=True, text=True)
        return result, [json.loads(line) for line in log.read_text().splitlines()]
    result, calls = run('inputplumber-hyprland.sh')
    assert result.returncode == 0, result.stderr
    assert calls[-2:] == [['inputplumber', 'device', '7', 'profile', 'load', str(root/'profiles/icewine-hyprland.yaml')], ['icewine-inputplumber-intercept', 'overlay']]
    result, calls = run('inputplumber-hyprland.sh', FAIL_MATCH='profile load')
    assert result.returncode != 0 and calls[-1][0] == 'inputplumber'
    # The unit runs this even when bootstrap failed. Restoration fails closed.
    result, calls = run('inputplumber-restore.sh')
    assert result.returncode == 0, result.stderr
    assert calls[-2:] == [['inputplumber', 'device', '7', 'profile', 'load', str(root/'default.yaml')], ['inputplumber', 'device', '7', 'intercept', 'set', 'pass']]
    assert (root/'default.yaml').read_text() == 'unrelated host profile\n'
    result, calls = run('inputplumber-restore.sh', FAIL_MATCH='profile load')
    assert result.returncode != 0 and not any(call[-1] == 'pass' for call in calls)
    result, calls = run('keyboard-toggle.sh')
    assert result.returncode == 0 and calls[-1] == ['qs', 'ipc', 'call', 'topbar', 'osk', 'true']
    result, calls = run('keyboard-toggle.sh', VISIBLE='unexpected')
    assert result.returncode != 0 and not any('SetVisible' in call for call in calls)
print('PASS: shared Handheld bootstrap, failed-start restore and keyboard visibility validation')
