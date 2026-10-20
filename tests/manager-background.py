#!/usr/bin/env python3
"""Non-build ANSI-replay regressions; native candidate PTY checks are separate."""
import ast
from pathlib import Path
import re
import unittest

root = Path(__file__).resolve().parent.parent
# Load only the real replay helper, without starting the PTY command-line suite.
module = ast.parse((root / "tests/manager-tty.py").read_text())
helper = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "rendered_frames")
namespace = {"re": re}
exec(compile(ast.Module(body=[helper], type_ignores=[]), str(root / "tests/manager-tty.py"), "exec"), namespace)
rendered_frames = namespace["rendered_frames"]


class Background(unittest.TestCase):
    def replay(self, ansi, **kwargs):
        return rendered_frames(ansi, (3, 8), check_contrast=True, check_background=True, **kwargs)

    def test_default_canvas_and_highlight_reset(self):
        ansi = (b"\x1b[2J\x1b[2;1H\x1b[38;2;30;30;46;48;2;137;180;250mHi"
                b"\x1b[?25l\x1b[2;1H\x1b[39;49m  \x1b[?25l")
        self.assertEqual(len(self.replay(ansi)), 2)
        # Review's named ANSI colours and indexed equivalents are equivalent.
        for colours in (b"30;46", b"38;5;0;48;5;6"):
            self.replay(b"\x1b[2;1H\x1b["+colours+b"mBack\x1b[?25l")

    def test_ordinary_fill_and_blank_cells_fail(self):
        for text in (b"Text", b"    "):
            with self.assertRaisesRegex(AssertionError, "Non-default ordinary background"):
                self.replay(b"\x1b[2;1H\x1b[38;2;205;214;244;48;2;30;30;46m"+text+b"\x1b[?25l")

    def test_stale_cells_and_clear_background_fail(self):
        # Overwrite only one cell; the other cell must retain its bad background.
        with self.assertRaisesRegex(AssertionError, "Non-default ordinary background"):
            self.replay(b"\x1b[2;1H\x1b[41mXX\x1b[2;1H\x1b[0m \x1b[?25l")
        with self.assertRaisesRegex(AssertionError, "Non-default ordinary background"):
            self.replay(b"\x1b[41m\x1b[2J\x1b[0m\x1b[?25l")

    def test_invisible_highlight_and_opaque_border_fail(self):
        with self.assertRaisesRegex(AssertionError, "Invisible"):
            self.replay(b"\x1b[2;1H\x1b[36;46mX\x1b[?25l")
        with self.assertRaisesRegex(AssertionError, "Opaque canvas border"):
            self.replay(b"\x1b[30;46m \x1b[?25l")

    def test_resize_discards_old_cells(self):
        before = b"\x1b[2;1H\x1b[41mX"
        self.replay(before+b"\x1b[0m\x1b[?25l", resize_events=[(len(before), (4, 10))])


if __name__ == "__main__":
    unittest.main()
