# Tasks

## 1. Gerüst und Prüfweg

- [x] 1.1 `custom_components/run_timer/` mit `manifest.json` (domain, version 0.1.0, config_flow, iot_class `calculated`), `const.py`, leerem `__init__.py`; `hacs.json` mit Mindestversion laut D11. Beleg: `hassfest` läuft lokal bzw. in CI ohne Fehler
- [x] 1.2 Testumgebung: `pytest-homeassistant-custom-component` auf die HA-Version der Mindestversion gepinnt, `tests/conftest.py` mit `enable_custom_integrations`. Beleg: `pytest` sammelt und läuft (0 Tests ok)
- [x] 1.3 `.claude/verify.md` mit Testkommando, Mindestversion und Deploy-Weg (Kopie, später HACS); GitHub-Actions-Workflows für hassfest, HACS und pytest. Beleg: das Kommando aus verify.md läuft lokal grün

## 2. Einrichtung (device-setup)

- [x] 2.1 Config Flow: Ziel-Entität (nur Domains mit `turn_on`/`turn_off`), Standarddauer 1–1440, Abbruch bei Duplikat; Options Flow mit Standarddauer und Einschalt-Aktion (`ActionSelector`), wirksam ohne Reload (D6). Beleg: `tests/test_config_flow.py` deckt alle Szenarien aus specs/device-setup zum Config Flow ab
- [x] 2.2 Controller-Gerüst je Eintrag mit Store (D1, D2), Laden in `async_setup_entry`, Löschen in `async_remove_entry`. Beleg: Test, der Zeitpunkte setzt, den Eintrag neu lädt und sie wieder liest
- [x] 2.3 Entitäten `number`, zweimal `sensor` (timestamp: Aus- und Einschaltzeit, D13), zweimal `time` (D12), Symbole per `icons.json`, Device-Zuordnung nach D7, Übersetzungen en/de. Beleg: `tests/test_entities.py` (Gerät vorhanden, ohne Gerät, leere Werte, Bereichsgrenzen der Standarddauer)

## 3. Aus-Timer (off-timer)

- [x] 3.1 Zustandsbeobachtung und Übergänge nach D4: Start bei `off` → an, „aus um“ hat Vorrang, Hand-Aus leert `off_at`, Attributwechsel ignoriert. Beleg: zugehörige Szenarien in `tests/test_off_timer.py`
- [x] 3.2 Ausschalten zur Ausschaltzeit inklusive Nachholen bei nicht erreichbarem Gerät (D5) und Ablauf von „aus um“ bei ausgeschaltetem Gerät. Beleg: `tests/test_off_timer.py` (Ausschaltzeit erreicht, WLAN weg, „aus um“ läuft ab)
- [x] 3.3 Dienste `extend`, `off_in`, `off_at`, `cancel` mit `entity_id` als Adresse (D8), `services.yaml` und Übersetzungen; Setzen der Entität „aus um“ läuft über denselben Pfad wie `off_at`. Beleg: `tests/test_services.py` deckt alle Szenarien aus specs/off-timer zu Diensten ab
- [x] 3.4 Wiederherstellen nach dem Start (D3): Zeitpläne neu setzen, verpasstes Ausschalten nachholen, Gerät an ohne Timer startet die Standarddauer; Reload eines Eintrags behält laufende Timer. Beleg: `tests/test_restore.py` (Off-Szenarien und Reload)

## 4. Geplantes Einschalten (scheduled-on)

- [x] 4.1 Dienste `on_in`/`on_at` mit optionaler Dauer, Entität „ein um“ gleichwertig zu `on_at`, Ersetzen eines Plans. Beleg: Szenarien „Ein um 06:00“ und „Neuer Plan ersetzt alten“ in `tests/test_scheduled_on.py`
- [x] 4.2 Ausführen mit Einschalt-Aktion (D6), Sperre gegen den Standard-Start (D4), Vorrang vor Timer und „aus um“, Plan bleibt bei Hand-Aus. Beleg: übrige Szenarien in `tests/test_scheduled_on.py` und das Szenario „Eigene Einschalt-Aktion“ aus device-setup
- [x] 4.3 Nachholen nach Neustart oder bei nicht erreichbarem Gerät, Verwerfen, wenn zu spät. Beleg: Plan-Szenarien in `tests/test_restore.py`

## 5. Doku und Abnahme

- [x] 5.1 README (englisch): Installation per HACS Custom Repository, Einrichtung, Entitäten, Dienste mit Beispielaufrufen für Dashboard-Knöpfe, Abgrenzung zum Scheduler, Credits. Beleg: jeder Beispielaufruf aus dem README ist in einem Test einmal genauso aufgerufen
- [x] 5.2 Testinstallation auf der Testinstanz nach Migration Plan Schritt 1 (Ablauf im Wiki `run_timer`). Beleg: Prüfprotokoll mit Einschalten, +15, −15, „aus um“, „ein in 2 min“, Ausschalten zur Zeit, Neustart mit laufendem Timer

## 6. Bedienbereich im More-Info-Dialog (more-info-panel)

- [x] 6.1 Skript `www/run-timer-panel.js` per `add_extra_js_url`, WebSocket-Befehl `run_timer/list`, nur mit Frontend (D17). Beleg: `tests/test_entities.py` (`test_websocket_list_managed_entities`, `test_frontend_setup_registers_panel`)
- [x] 6.2 `extend` ohne Timer nach D16, „aus um“ auch beim Einschalten/kurz weg. Beleg: `tests/test_services.py`
- [x] 6.3 Sichtprüfung auf der Testinstanz: Bereich erscheint bei verwalteten Geräten, Knöpfe lösen die Dienste aus, Fehlermeldungen als Hinweis. Beleg: Prüfung 2026-10-16 (Frontend 20260930.4)
