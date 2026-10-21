# Tasks

## 1. Haltebedingung

- [x] 1.1 Optionen `hold_template` und `hold_minutes` (Syntaxprüfung durch den `TemplateSelector`). Beleg: `tests/test_config_flow.py` (`test_options_hold_template`, `test_options_invalid_hold_template`)
- [x] 1.2 Controller: Template-Tracking, `hold_run`, Nachlauf, Vorrang der Eingriffe, Neustart. Beleg: `tests/test_hold.py`
- [x] 1.3 Attribut `held` am Sensor „Nächstes Aus“. Beleg: `tests/test_hold.py` (`test_hold_until_condition_false`)
- [x] 1.4 Übersetzungen en/de, README, Version 0.1.8, `verify.md` (Testanzahl). Beleg: Sichtprüfung der Texte, hassfest „Invalid integrations: 0“
