"""Beleg zu Task 5.1: jeder Beispielaufruf aus dem README läuft so durch."""

from __future__ import annotations

from pathlib import Path
import re

import pytest
import yaml

from homeassistant.core import HomeAssistant

from .conftest import FAN, add_entry, dt_state, local, off_time, switch

pytestmark = pytest.mark.usefixtures("base")

README = Path(__file__).parent.parent / "README.md"


def readme_examples() -> list[dict]:
    """Return the service calls from the README's dashboard example block."""
    text = README.read_text(encoding="utf-8")
    block = text.split("Examples for dashboard buttons:", 1)[1]
    block = re.search(r"```yaml\n(.*?)```", block, re.S).group(1)
    parts = [p for p in re.split(r"\n\s*\n", block) if p.strip()]
    return [yaml.safe_load(p) for p in parts]


async def test_readme_examples(hass: HomeAssistant) -> None:
    """Alle Beispiele nacheinander gegen einen laufenden Ventilator."""
    examples = readme_examples()
    assert [e["action"] for e in examples] == [
        "run_timer.extend",
        "run_timer.off_at",
        "run_timer.off_in",
        "run_timer.on_at",
        "run_timer.cancel",
    ]
    entry = await add_entry(hass)
    await switch(hass, True)
    for example in examples:
        domain, service = example["action"].split(".")
        data = {**example["data"], "entity_id": FAN}
        await hass.services.async_call(domain, service, data, blocking=True)
        await hass.async_block_till_done()
    assert off_time(hass, entry) == local("2026-10-15 12:30")
    assert dt_state(hass, entry, "switch_on_at") is None
