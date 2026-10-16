# more-info-panel Specification

## Purpose
Legt fest, wie run_timer im More-Info-Dialog eines verwalteten Geräts einen Bedienbereich zeigt, ohne eigene Karte und ohne eigene Logik: jeder Knopf ist einer der Dienste.

## Requirements

### Requirement: Bereich nur bei verwalteten Geräten
Das System SHALL im More-Info-Dialog einer von run_timer verwalteten Entität einen Bedienbereich unter dem normalen Inhalt anzeigen und bei allen anderen Entitäten keinen. Welche Entitäten zu einem Gerät gehören, SHALL ein WebSocket-Befehl `run_timer/list` liefern.

#### Scenario: Verwaltetes Gerät
- **WHEN** der More-Info-Dialog eines verwalteten Geräts geöffnet wird
- **THEN** erscheint der Bereich mit den Zeilen Start und Stopp (je ein direkt bearbeitbares Uhrzeitfeld, die relative Zeit und ✕ zum Löschen, wenn etwas gesetzt ist) und den Knöpfen −15, +15, aus in 30/60/120 min; das Stopp-Feld zeigt die nächste Ausschaltzeit, ohne laufenden Timer ein gesetztes „aus um“ (dann ohne relative Zeit)
- **Beleg:** Sichtprüfung auf der Testinstanz (2026-10-16, Fassung 0.1.6, Frontend 20260930.4)

#### Scenario: Uhrzeit eingeben
- **WHEN** im Feld Start oder Stopp eine Uhrzeit wie `715`, `7:15` oder `07.15` (bzw. `7` für 07:00) eingegeben und mit Enter bestätigt oder das Feld verlassen wird
- **THEN** geht genau ein Aufruf `on_at` bzw. `off_at` mit `07:15` raus; steht dieselbe Uhrzeit innerhalb der nächsten 24 h schon dort, geht keiner raus; eine ungültige Eingabe oder Esc ändert nichts und Esc schließt den Dialog nicht
- **Beleg:** pytest `tests/test_panel_js.py` (Zeit-Parser), Sichtprüfung auf der Testinstanz

#### Scenario: Nicht verwaltete Entität
- **WHEN** der Dialog einer Entität ohne run_timer-Eintrag geöffnet wird
- **THEN** erscheint kein Bereich
- **Beleg:** Sichtprüfung auf der Testinstanz

#### Scenario: Zuordnung per WebSocket
- **WHEN** das Frontend `run_timer/list` aufruft
- **THEN** bekommt es je verwalteter Entität die Entitäts-IDs ihrer run_timer-Entitäten nach `translation_key`
- **Beleg:** pytest `tests/test_entities.py` (`test_websocket_list_managed_entities`, `test_frontend_setup_registers_panel`)

### Requirement: Laden auf jeder Seite
Das System SHALL das Skript des Bereichs über die Frontend-Liste zusätzlicher Module laden, damit er auf jeder Seite erscheint, auch auf der Standard-Übersicht und in den Einstellungen, und nur, wenn das Frontend geladen ist. Der Bereich SHALL nur Bausteine nutzen, die der Dialog selbst lädt (`ha-button`, `ha-icon-button`).

#### Scenario: Mit Frontend
- **WHEN** Home Assistant mit Frontend startet
- **THEN** wird das Skript mit der Version im Adressteil ausgeliefert und als Modul eingetragen
- **Beleg:** pytest `tests/test_entities.py` (`test_frontend_setup_registers_panel`); `index.html` der Testinstanz enthält `run_timer_static/run-timer-panel.js?v=<version>`

#### Scenario: Ohne Frontend
- **WHEN** Home Assistant ohne Frontend läuft (z. B. in Tests)
- **THEN** richtet sich run_timer ohne den Bereich ein
- **Beleg:** pytest, alle übrigen Tests laufen ohne Frontend

### Requirement: Nur Dienstaufrufe
Jedes Bedienelement des Bereichs SHALL genau einen der Dienste `extend`, `off_in`, `on_at`, `off_at` oder `cancel` aufrufen. Lehnt der Dienst ab, SHALL die Meldung des Dienstes erscheinen und die Konsole fehlerfrei bleiben.

#### Scenario: Abgelehnter Aufruf
- **WHEN** ein Knopf einen Dienst auslöst, der mit einer Fehlermeldung abbricht
- **THEN** zeigt Home Assistant die Meldung, und es entsteht kein unbehandelter Fehler im Browser
- **Beleg:** Sichtprüfung auf der Testinstanz (Meldung „has no running timer.“ vor D16, 2026-10-16)
