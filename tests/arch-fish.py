#!/usr/bin/env python3
"""Exercise optional Fish integration against host/user startup overrides."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

package = Path(sys.argv[1]).resolve()
startup = package / "usr/share/fish/vendor_conf.d/icewine.fish"
greeting = package / "usr/share/fish/vendor_functions.d/fish_greeting.fish"
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    binary = root / "bin"
    binary.mkdir()
    log = root / "calls"
    for name, body in {
        "starship": '''printf 'starship\\n' >> "$ICEWINE_TEST_LOG"
cat "$STARSHIP_CONFIG" >> "$ICEWINE_TEST_LOG"
printf 'function fish_prompt; echo starship; end\\n'
''',
        "fastfetch": '''printf 'fastfetch\\n' >> "$ICEWINE_TEST_LOG"\n''',
    }.items():
        file = binary / name
        file.write_text("#!" + shutil.which("sh") + "\n" + body)
        file.chmod(0o755)
    env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(root / "config"),
               PATH=str(binary) + ":" + os.environ["PATH"], ICEWINE_TEST_LOG=str(log))
    env.pop("STARSHIP_CONFIG", None)
    config = root / "config/starship.toml"
    config.parent.mkdir()
    config.write_text("preserved canonical Starship config\n")
    def run(body, interactive=True, **extra):
        log.unlink(missing_ok=True)
        result = subprocess.run(["fish", "--no-config", *( ["-i"] if interactive else [] ),
                                 "-c", f"source '{startup}'; {body}"],
                                env=dict(env, **extra), capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return result, log.read_text().splitlines() if log.exists() else []
    result, calls = run(f"source '{greeting}'; fish_greeting; emit fish_prompt; emit fish_prompt; echo $STARSHIP_CONFIG")
    assert calls == ["fastfetch", "starship", "preserved canonical Starship config"], calls
    assert str(config) in result.stdout
    result, calls = run("emit fish_prompt; if set -q STARSHIP_CONFIG; exit 1; end; true", interactive=False)
    assert calls == []
    result, calls = run("function fish_prompt; echo user; end; function fish_greeting; fastfetch; end; fish_greeting; emit fish_prompt; fish_prompt; echo $STARSHIP_CONFIG", STARSHIP_CONFIG="/custom/prompt.toml")
    assert calls == ["fastfetch"] and "user" in result.stdout and "/custom/prompt.toml" in result.stdout
    result, calls = run(f"set -g fish_greeting ''; source '{greeting}'; fish_greeting; function fish_prompt; echo user; end; emit fish_prompt")
    assert calls == [], calls
    user_prompt = root / "config/fish/functions/fish_prompt.fish"
    user_prompt.parent.mkdir(parents=True, exist_ok=True)
    user_prompt.write_text("function fish_prompt; echo autoloaded-user; end\n")
    result, calls = run(f"source '{user_prompt}'; emit fish_prompt; fish_prompt")
    assert calls == [] and "autoloaded-user" in result.stdout
print("PASS: interactive-only prompt, one greeting/init, and host/user overrides")
