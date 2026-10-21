# run_timer — Verify-Kontrakt

Diese Datei sagt Prüf-Agents (`mother`, `jones`, `ash`), was in diesem Repo gilt.
Was hier nicht steht, wird nicht geraten.

## Prüfen (führt `mother` aus)

```bash
uv run -q --python 3.14 --no-project --with-requirements requirements_test.txt python -m pytest -q -p no:cacheprovider
```

- `requirements_test.txt` pinnt `pytest-homeassistant-custom-component==0.13.367`, das bringt
  Home Assistant `2026.9.4` mit, also dieselbe Version wie `hacs.json` → `homeassistant`.
  Ändert sich die Mindestversion, ziehen beide im selben Commit mit.
- Python 3.14 (Vorgabe des Testpakets), `uv` baut eine Wegwerf-Umgebung, das System-Python bleibt unberührt.
- Stand 2026-10-21: 127 grün, nichts übersprungen. `tests/test_panel_js.py` braucht `node` (in GitHub Actions vorhanden), ohne `node` wird er übersprungen.
- `hassfest` lokal (Beleg 2026-10-15: „Invalid integrations: 0“), Core-Skripte im Tag der Mindestversion:

  ```bash
  git clone -q --depth 1 --branch 2026.9.4 --filter=blob:none --sparse https://github.com/home-assistant/core.git <tmp>/core
  git -C <tmp>/core sparse-checkout set script
  cd <tmp>/core && uv run -q --python 3.14 --no-project --with-requirements <repo>/requirements_test.txt \
    --with infrared-protocols --with ruff python -m script.hassfest --integration-path <repo>/custom_components/run_timer
  ```

- Die HACS-Prüfung läuft nur in GitHub Actions (`.github/workflows/validate.yml`), dort auch hassfest und pytest.

## Deploy (liest `jones`, führt niemand automatisch aus)

- Version: `custom_components/run_timer/manifest.json` → `version`; vor jedem Ausrollen hochzählen.
- Zielinstanzen, Zugangswege und Ablauf der Testinstallation stehen im Wiki `run_timer`
  (öffentliches Repo: hier nur das Allgemeine).
- Weg bis zum ersten Release: Ordner `custom_components/run_timer` (ohne `__pycache__`) nach
  `/config/custom_components/run_timer` kopieren, HA neu starten. Danach: GitHub-Release mit
  Tag = Version, Installation als HACS Custom Repository.
- Beleg, dass der Stand läuft: `GET /api/config` → `components` enthält `run_timer`, und
  `/config/custom_components/run_timer/manifest.json` hat die erwartete `version`.
- Zusätzlich jeder run_timer-Eintrag im Zustand `loaded` (Config-Entries-API bzw. Oberfläche); `components` enthält
  `run_timer` schon, wenn nur `async_setup` lief und ein Eintrag mit `setup_error` hängt.
