# Spec Delta

## Purpose

Legt fest, wie run_timer im More-Info-Dialog eines verwalteten Geräts einen Bedienbereich zeigt, ohne eigene Karte und ohne eigene Logik: jeder Knopf ist einer der Dienste.

## ADDED Requirements

### Requirement: Bereich nur bei verwalteten Geräten
Das System SHALL im More-Info-Dialog einer von run_timer verwalteten Entität einen Bedienbereich unter dem normalen Inhalt anzeigen und bei allen anderen Entitäten keinen. Welche Entitäten zu einem Gerät gehören, SHALL ein WebSocket-Befehl `run_timer/list` liefern.

#### Scenario: Verwaltetes Gerät
- **WHEN** der More-Info-Dialog eines verwalteten Geräts geöffnet wird
- **THEN** erscheint der Bereich mit Nächstes An, Nächstes Aus, Knöpfen −15, +15, aus in 30/60/120 min, Timer weg und den Schaltzeiten an/aus mit Setzen und Löschen
- **Beleg:** Sichtprüfung auf der Testinstanz (2026-10-16, Frontend 20260930.4)

#### Scenario: Nicht verwaltete Entität
- **WHEN** der Dialog einer Entität ohne run_timer-Eintrag geöffnet wird
- **THEN** erscheint kein Bereich
- **Beleg:** Sichtprüfung auf der Testinstanz

#### Scenario: Zuordnung per WebSocket
- **WHEN** das Frontend `run_timer/list` aufruft
- **THEN** bekommt es je verwalteter Entität die Entitäts-IDs ihrer run_timer-Entitäten nach `translation_key`
- **Beleg:** pytest `tests/test_entities.py` (`test_websocket_list_managed_entities`, `test_frontend_setup_registers_panel`)

### Requirement: Laden auf jeder Seite
Das System SHALL das Skript des Bereichs über die Frontend-Liste zusätzlicher Module laden, damit er auch in den Einstellungen erscheint, und nur, wenn das Frontend geladen ist.

#### Scenario: Mit Frontend
- **WHEN** Home Assistant mit Frontend startet
- **THEN** wird das Skript mit der Version im Adressteil ausgeliefert und als Modul eingetragen
- **Beleg:** pytest `tests/test_entities.py` (`test_frontend_setup_registers_panel`); `index.html` der Testinstanz enthält `run_timer_static/run-timer-panel.js?v=<version>`

#### Scenario: Ohne Frontend
- **WHEN** Home Assistant ohne Frontend läuft (z. B. in Tests)
- **THEN** richtet sich run_timer ohne den Bereich ein
- **Beleg:** pytest, alle übrigen Tests laufen ohne Frontend

### Requirement: Nur Dienstaufrufe
Jeder Knopf des Bereichs SHALL genau einen der Dienste `extend`, `off_in`, `cancel` oder `time.set_value` auf einer Schaltzeit-Entität aufrufen. Lehnt der Dienst ab, SHALL die Meldung des Dienstes erscheinen und die Konsole fehlerfrei bleiben.

#### Scenario: Abgelehnter Aufruf
- **WHEN** ein Knopf einen Dienst auslöst, der mit einer Fehlermeldung abbricht
- **THEN** zeigt Home Assistant die Meldung, und es entsteht kein unbehandelter Fehler im Browser
- **Beleg:** Sichtprüfung auf der Testinstanz (Meldung „has no running timer.“ vor D16, 2026-10-16)
