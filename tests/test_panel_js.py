"""Spec more-info-panel: Zeit-Parser des Panel-Skripts (läuft mit Node, sonst übersprungen)."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

SCRIPT = Path(__file__).parent.parent / "custom_components/run_timer/www/run-timer-panel.js"
CASES = {
    "7": "07:00", "715": "07:15", "0715": "07:15", "7:15": "07:15", "07.15": "07:15",
    " 23:59 ": "23:59", "24:00": None, "7:60": None, "7:5": None, "abc": None, "": None,
}


@pytest.mark.skipif(shutil.which("node") is None, reason="node fehlt")
def test_parse_time() -> None:
    """Eingaben im Uhrzeitfeld werden zu HH:MM oder abgelehnt."""
    source = SCRIPT.read_text(encoding="utf-8")
    function = re.search(r"function parseTime[\s\S]*?\n  \}\n", source).group(0)
    program = f"{function}\nconsole.log(JSON.stringify(Object.fromEntries({json.dumps(list(CASES))}.map((v) => [v, parseTime(v)]))));"
    result = subprocess.run(["node", "-e", program], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == CASES
