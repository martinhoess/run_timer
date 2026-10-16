# device-setup Specification

## Purpose
Legt fest, wie ein Gerät unter run_timer kommt und welche Entitäten run_timer je Gerät bereitstellt, damit Dashboards ohne Helfer darauf aufbauen können.

## Requirements

### Requirement: Ein Config-Eintrag je Gerät
Das System SHALL je verwaltetem Gerät einen eigenen Config-Eintrag anlegen. Ziel ist eine Entität einer Domain, die `turn_on` und `turn_off` anbietet. Dieselbe Ziel-Entität MUST NOT zweimal verwaltet werden.

#### Scenario: Gerät hinzufügen
- **WHEN** der Nutzer die Integration hinzufügt, eine Ziel-Entität wählt und eine Standarddauer angibt
- **THEN** entsteht ein Config-Eintrag mit dem Namen der Ziel-Entität und ihre Entitäten erscheinen
- **Beleg:** pytest `tests/test_config_flow.py`

#### Scenario: Doppelte Ziel-Entität
- **WHEN** der Nutzer eine Ziel-Entität wählt, die schon verwaltet wird
- **THEN** bricht der Config Flow mit dem Grund „bereits eingerichtet“ ab
- **Beleg:** pytest `tests/test_config_flow.py`

#### Scenario: Domain ohne an/aus
- **WHEN** der Nutzer eine Entität ohne `turn_on`/`turn_off` wählt (z. B. `sensor`)
- **THEN** lehnt der Config Flow sie mit einer Fehlermeldung ab
- **Beleg:** pytest `tests/test_config_flow.py`

### Requirement: Standarddauer
Das System SHALL je Gerät eine Standarddauer in Minuten führen, mindestens 1 und höchstens 1440. Sie ist als `number`-Entität les- und schreibbar. Eine Änderung gilt ab dem nächsten Start eines Aus-Timers; ein laufender Timer bleibt unverändert.

#### Scenario: Standarddauer ändern
- **WHEN** der Nutzer die `number`-Entität von 240 auf 120 setzt, während ein Timer läuft
- **THEN** bleibt die laufende Ausschaltzeit gleich und der nächste Start nach dem Einschalten nutzt 120 min
- **Beleg:** pytest `tests/test_entities.py`

#### Scenario: Wert außerhalb des Bereichs
- **WHEN** jemand die Standarddauer auf 0 oder 1441 setzen will
- **THEN** lehnt Home Assistant den Wert ab und die Standarddauer bleibt unverändert
- **Beleg:** pytest `tests/test_entities.py`

### Requirement: Einschalt-Aktion
Das System SHALL zum Einschalten `homeassistant.turn_on` auf die Ziel-Entität nutzen, sofern im Config-Eintrag keine eigene Einschalt-Aktion hinterlegt ist. Eine hinterlegte Einschalt-Aktion SHALL stattdessen ausgeführt werden. Ausschalten nutzt immer `homeassistant.turn_off`.

#### Scenario: Eigene Einschalt-Aktion
- **WHEN** für ein Klimagerät die Einschalt-Aktion `climate.set_hvac_mode` mit `hvac_mode: cool` hinterlegt ist und ein geplantes Einschalten fällig wird
- **THEN** wird genau diese Aktion ausgeführt, nicht `homeassistant.turn_on`
- **Beleg:** pytest `tests/test_scheduled_on.py`

#### Scenario: Einschalt-Aktion später ändern
- **WHEN** der Nutzer die Einschalt-Aktion in den Optionen des Eintrags ändert
- **THEN** gilt die neue Aktion ab dem nächsten Einschalten durch run_timer, ohne Neustart von Home Assistant
- **Beleg:** pytest `tests/test_config_flow.py`

### Requirement: Entitäten je Gerät
Das System SHALL je Gerät fünf Entitäten bereitstellen: Standarddauer (`number`), Ausschaltzeit und Einschaltzeit (je `sensor` mit Geräteklasse `timestamp`), „ein um“ (`time`) und „aus um“ (`time`). Die beiden Uhrzeit-Entitäten zeigen die lokale Uhrzeit des Zeitpunkts; gesetzt bedeuten sie das nächste Vorkommen dieser Uhrzeit. Gehört die Ziel-Entität zu einem Gerät, SHALL das System die Entitäten diesem Gerät zuordnen, sonst einem eigenen Gerät.

#### Scenario: Ziel-Entität mit Gerät
- **WHEN** ein Gerät eingerichtet wird, dessen Ziel-Entität zu einem vorhandenen Gerät gehört
- **THEN** erscheinen die fünf Entitäten auf der Geräteseite dieses Geräts
- **Beleg:** pytest `tests/test_entities.py`

#### Scenario: Ziel-Entität ohne Gerät
- **WHEN** die Ziel-Entität zu keinem Gerät gehört (z. B. `input_boolean`)
- **THEN** legt run_timer ein eigenes Gerät an und ordnet die Entitäten ihm zu
- **Beleg:** pytest `tests/test_entities.py`

#### Scenario: „Aus um“ per Entität auf vergangene Uhrzeit
- **WHEN** um 12:00 die Entität „aus um“ auf 08:00 gesetzt wird
- **THEN** gilt 08:00 am Folgetag
- **Beleg:** pytest `tests/test_entities.py`

#### Scenario: Leere Werte
- **WHEN** weder ein Aus-Timer läuft noch „aus um“ oder „ein um“ gesetzt ist
- **THEN** haben Ausschaltzeit, Einschaltzeit, „aus um“ und „ein um“ den Zustand `unknown`
- **Beleg:** pytest `tests/test_entities.py`

#### Scenario: Einschaltzeit zeigt den genauen Plan
- **WHEN** ein Einschalten geplant ist, auch mehr als 24 h voraus oder mit Sekunden
- **THEN** zeigt die Einschaltzeit den vollen Zeitpunkt mit Datum und Sekunden, während „ein um“ nur die Uhrzeit in vollen Minuten zeigt; nach dem Einschalten oder `cancel` ist sie `unknown`
- **Beleg:** pytest `tests/test_entities.py` (`test_on_time_shows_exact_plan`)

### Requirement: Umbenannte Ziel-Entität
Das System SHALL einer umbenannten Ziel-Entität folgen: Timer, Pläne und Dienste gelten danach für die neue `entity_id`.

#### Scenario: Ventilator umbenannt
- **WHEN** die Ziel-Entität in der Entitätsverwaltung eine neue `entity_id` bekommt
- **THEN** startet das Einschalten unter der neuen ID den Timer, und Dienste mit der neuen ID wirken
- **Beleg:** pytest `tests/test_off_timer.py`

### Requirement: Eintrag entfernen
Das System SHALL beim Entfernen eines Config-Eintrags alle Timer und Pläne dieses Geräts verwerfen, ohne das Gerät zu schalten.

#### Scenario: Entfernen bei laufendem Timer
- **WHEN** der Eintrag eines eingeschalteten Geräts mit laufendem Timer entfernt wird
- **THEN** bleibt das Gerät an, und zur früheren Ausschaltzeit passiert nichts
- **Beleg:** pytest `tests/test_off_timer.py`
