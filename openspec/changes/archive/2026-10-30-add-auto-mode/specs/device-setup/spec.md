## ADDED Requirements

### Requirement: Modus und Uhrzeit
Die Optionen eines Geräts SHALL den Modus `off` (Vorgabe) oder `on` und eine optionale Uhrzeit anbieten. Bestehende Einträge ohne diese Optionen MUST sich wie `off` ohne Uhrzeit verhalten. Eine geänderte Option SHALL ab dem nächsten Schaltvorgang gelten; wird ein ausgeschaltetes Gerät auf `on` gestellt, plant es sofort.

#### Scenario: Modus setzen
- **WHEN** in den Optionen Modus `on` und Uhrzeit 04:00 gespeichert werden
- **THEN** stehen beide in den Optionen des Eintrags, und eine leere Uhrzeit löscht die Uhrzeit wieder
- **Beleg:** pytest `tests/test_auto_mode.py`

#### Scenario: Andere Änderung im Modus on
- **WHEN** im Modus `on` ein Plan per `cancel` verworfen und danach eine Option geändert wird
- **THEN** entsteht kein neuer Plan
- **Beleg:** pytest `tests/test_auto_mode.py`

#### Scenario: Ausgeschaltetes Gerät wechselt auf on
- **WHEN** ein ausgeschaltetes Gerät in den Optionen auf Modus `on` gestellt wird
- **THEN** steht sofort ein geplantes Einschalten
- **Beleg:** pytest `tests/test_auto_mode.py`
