# off-timer Specification

## Purpose
Schaltet ein verwaltetes Gerät nach einer Laufzeit aus und lässt diese Laufzeit per Dienst und Entität verlängern, verkürzen oder auf eine feste Uhrzeit setzen.

## Requirements

### Requirement: Zustand „an“
Das System SHALL eine Ziel-Entität als „an“ werten, wenn ihr Zustand weder `off` noch `unavailable` noch `unknown` ist. Änderungen nur an Attributen (z. B. Lüfterstufe) zählen nicht als Einschalten.

#### Scenario: Klimagerät im Modus heat
- **WHEN** eine `climate`-Entität den Zustand `heat` hat
- **THEN** gilt sie als „an“
- **Beleg:** pytest `tests/test_off_timer.py`

#### Scenario: Nur Attribut ändert sich
- **WHEN** ein laufender Ventilator die Stufe wechselt
- **THEN** bleibt die Ausschaltzeit unverändert
- **Beleg:** pytest `tests/test_off_timer.py`

### Requirement: Aus-Timer beim Einschalten
Das System SHALL eine Ausschaltzeit setzen, wenn die Ziel-Entität „an“ meldet und ihr letzter erreichbarer Zustand `off` war oder seit dem Start noch keiner bekannt ist, auch wenn dazwischen `unavailable` lag. Ist „aus um“ gesetzt und liegt in der Zukunft, gilt diese Zeit, sonst jetzt + Standarddauer; bei Standarddauer 0 startet dann kein Timer. War der letzte erreichbare Zustand schon „an“, startet nichts.

#### Scenario: Einschalten am Gerät
- **WHEN** der Ventilator mit Standarddauer 240 min um 20:00 am Gerät eingeschaltet wird
- **THEN** zeigt der Sensor Ausschaltzeit 00:00, und um 00:00 schaltet run_timer ihn aus
- **Beleg:** pytest `tests/test_off_timer.py`

#### Scenario: „aus um“ ist gesetzt
- **WHEN** „aus um“ auf 18:00 steht und das Gerät um 12:00 eingeschaltet wird (Standarddauer 240 min)
- **THEN** ist die Ausschaltzeit 18:00
- **Beleg:** pytest `tests/test_off_timer.py`

#### Scenario: Gerät kommt von unavailable zurück
- **WHEN** ein Gerät mit laufendem Timer kurz `unavailable` war und wieder „an“ meldet
- **THEN** bleibt die bisherige Ausschaltzeit bestehen, es startet kein neuer Timer
- **Beleg:** pytest `tests/test_off_timer.py`

#### Scenario: Stromausfall schaltet die Steckdose ein
- **WHEN** ein ausgeschaltetes Gerät `unavailable` wird und danach „an“ meldet
- **THEN** startet die Standarddauer
- **Beleg:** pytest `tests/test_off_timer.py`

#### Scenario: Abgebrochener Timer nach kurzem Ausfall
- **WHEN** der Timer eines laufenden Geräts per `cancel` abgebrochen wurde und das Gerät kurz `unavailable` war
- **THEN** startet kein neuer Timer
- **Beleg:** pytest `tests/test_off_timer.py`

#### Scenario: Ausgeschaltet während Home Assistant nicht lief
- **WHEN** ein gespeicherter Timer bis 14:00 besteht, das Gerät nach dem Start aber `off` meldet und um 12:30 eingeschaltet wird
- **THEN** ist die Ausschaltzeit nach dem Start leer und nach dem Einschalten 16:30
- **Beleg:** pytest `tests/test_restore.py`

### Requirement: Ausschalten zur Ausschaltzeit
Das System SHALL zur Ausschaltzeit `homeassistant.turn_off` auf die Ziel-Entität aufrufen und danach Ausschaltzeit und ein erreichtes „aus um“ leeren. Schlägt der Aufruf fehl, SHALL er alle 5 Minuten wiederholt werden, bis die Entität `off` meldet oder die Ausschaltzeit geändert wird.

#### Scenario: Ausschaltzeit erreicht
- **WHEN** die Ausschaltzeit erreicht ist und das Gerät an ist
- **THEN** ist das Gerät aus, und Ausschaltzeit und „aus um“ sind `unknown`
- **Beleg:** pytest `tests/test_off_timer.py`

#### Scenario: Ausschalten scheitert einmal
- **WHEN** der Ausschaltbefehl zur Ausschaltzeit mit einem Fehler endet
- **THEN** versucht run_timer es 5 Minuten später erneut
- **Beleg:** pytest `tests/test_off_timer.py`

### Requirement: Ausschalten von Hand
Das System SHALL beim Wechsel der Ziel-Entität auf `off` die Ausschaltzeit leeren. „aus um“ und ein geplantes Einschalten SHALL erhalten bleiben.

#### Scenario: Von Hand aus mit Plan
- **WHEN** das Gerät mit laufendem Timer von Hand ausgeschaltet wird und „ein um“ auf 06:00 steht
- **THEN** ist die Ausschaltzeit `unknown`, „ein um“ steht weiter auf 06:00
- **Beleg:** pytest `tests/test_off_timer.py`

#### Scenario: „aus um“ übersteht Aus und An
- **WHEN** „aus um“ auf 18:00 steht, das Gerät um 13:00 aus- und um 14:00 wieder eingeschaltet wird
- **THEN** ist die Ausschaltzeit wieder 18:00
- **Beleg:** pytest `tests/test_off_timer.py`

#### Scenario: „aus um“ läuft ab, während das Gerät aus ist
- **WHEN** „aus um“ auf 18:00 steht und das Gerät um 18:00 aus ist
- **THEN** wird „aus um“ geleert, ohne zu schalten
- **Beleg:** pytest `tests/test_off_timer.py`

### Requirement: Restzeit verlängern und verkürzen
Das System SHALL einen Dienst `extend` mit ganzzahligen Minuten (positiv oder negativ) anbieten, der die aktuelle Ausschaltzeit verschiebt; ist „aus um“ gesetzt, wird es mit verschoben. Läge die neue Ausschaltzeit nicht in der Zukunft, SHALL das Gerät sofort ausgeschaltet werden. Ohne laufende Ausschaltzeit SHALL ein eingeschaltetes Gerät ab jetzt zählen (positiv: aus in X, negativ: sofort aus) und ein ausgeschaltetes Gerät bei positiven Minuten für diese Dauer eingeschaltet werden, wie ein Plan mit eigener Dauer; negative Minuten tun dann nichts; „aus um“ wird dabei verbraucht (geleert), ein geplantes Einschalten bleibt gesetzt und endet ohne eigene Dauer dann nach der Standarddauer. Scheitert das Einschalten, SHALL der Dienst mit einer Fehlermeldung abbrechen. Ist das Gerät nicht erreichbar, SHALL der Dienst mit einer Fehlermeldung abbrechen.

#### Scenario: Viermal +15
- **WHEN** um 20:00 eingeschaltet (Standarddauer 240 min) und danach viermal `extend` mit 15 aufgerufen wird
- **THEN** ist die Ausschaltzeit 01:00
- **Beleg:** pytest `tests/test_services.py`

#### Scenario: Minus über die Restzeit hinaus
- **WHEN** die Restzeit 10 min beträgt und `extend` mit −15 aufgerufen wird
- **THEN** wird das Gerät sofort ausgeschaltet
- **Beleg:** pytest `tests/test_services.py`

#### Scenario: Gerät ist aus
- **WHEN** `extend` mit 15 für ein ausgeschaltetes Gerät aufgerufen wird
- **THEN** ist es an, die Ausschaltzeit jetzt + 15 min, „aus um“ geleert und ein geplantes Einschalten noch gesetzt; mit −15 bleibt es aus
- **Beleg:** pytest `tests/test_services.py` (`test_extend_off_device_switches_on`, `test_extend_negative_off_device_does_nothing`)

#### Scenario: Gerät an, kein Timer
- **WHEN** der Timer eines eingeschalteten Geräts per `cancel` entfernt wurde und danach `extend` mit 15 bzw. −15 kommt
- **THEN** ist die Ausschaltzeit jetzt + 15 min bzw. wird sofort ausgeschaltet
- **Beleg:** pytest `tests/test_services.py` (`test_extend_on_device_without_timer_counts_from_now`)

#### Scenario: Nicht erreichbar, kein Timer
- **WHEN** `extend` für ein nicht erreichbares Gerät ohne Ausschaltzeit aufgerufen wird
- **THEN** schlägt der Aufruf mit einer verständlichen Fehlermeldung fehl
- **Beleg:** pytest `tests/test_services.py` (`test_extend_unreachable_without_timer_fails`)

### Requirement: Aus in X und aus um T
Das System SHALL die Dienste `off_in` (Minuten, > 0) und `off_at` (Uhrzeit oder Datum mit Uhrzeit) anbieten. Für eine Uhrzeit sind `off_at` und das Setzen der Entität „aus um“ gleichwertig (nächstes Vorkommen); ein Datum geht nur per `off_at`. `off_in` setzt bei eingeschaltetem Gerät die Ausschaltzeit auf jetzt + Minuten und leert „aus um“; bei ausgeschaltetem Gerät setzt es „aus um“ auf jetzt + Minuten. `off_at` setzt „aus um“; eine reine Uhrzeit in der Vergangenheit bedeutet denselben Zeitpunkt am Folgetag. Ist das Gerät an, wird „aus um“ sofort zur Ausschaltzeit, auch wenn sie länger als die Standarddauer ist.

#### Scenario: Bis 18:00 bei längerer Laufzeit
- **WHEN** das Gerät um 12:00 läuft (Standarddauer 240 min) und `off_at` mit 18:00 aufgerufen wird
- **THEN** ist die Ausschaltzeit 18:00
- **Beleg:** pytest `tests/test_services.py`

#### Scenario: Uhrzeit liegt zurück
- **WHEN** um 23:00 `off_at` mit 01:00 aufgerufen wird
- **THEN** steht „aus um“ auf 01:00 des Folgetags
- **Beleg:** pytest `tests/test_services.py`

#### Scenario: Aus in 30 Minuten bei ausgeschaltetem Gerät
- **WHEN** das Gerät aus ist und um 12:00 `off_in` mit 30 aufgerufen wird
- **THEN** steht „aus um“ auf 12:30, die Ausschaltzeit ist `unknown`
- **Beleg:** pytest `tests/test_services.py`

#### Scenario: Aus in 30 Minuten
- **WHEN** „aus um“ auf 18:00 steht, das Gerät läuft und um 12:00 `off_in` mit 30 aufgerufen wird
- **THEN** ist die Ausschaltzeit 12:30 und „aus um“ ist `unknown`
- **Beleg:** pytest `tests/test_services.py`

### Requirement: Abbrechen
Das System SHALL einen Dienst `cancel` mit Auswahl `off`, `on` oder `all` (Vorgabe `all`) anbieten. `off` leert Ausschaltzeit und „aus um“, `on` leert „ein um“, ohne das Gerät zu schalten.

#### Scenario: Alles abbrechen
- **WHEN** das Gerät läuft, „ein um“ gesetzt ist und `cancel` ohne Auswahl aufgerufen wird
- **THEN** sind Ausschaltzeit, „aus um“ und „ein um“ `unknown`, und das Gerät bleibt an
- **Beleg:** pytest `tests/test_services.py`

### Requirement: Nicht erreichbares Gerät
Das System SHALL eine fällige Ausschaltzeit nicht verwerfen, wenn die Ziel-Entität zu diesem Zeitpunkt `unavailable` oder `unknown` ist oder der Ausschaltbefehl fehlschlägt. Meldet sie danach „an“, SHALL sofort ausgeschaltet werden; meldet sie `off`, wird die Ausschaltzeit geleert.

#### Scenario: WLAN weg zur Ausschaltzeit
- **WHEN** um 00:00 ausgeschaltet werden soll, das Gerät aber `unavailable` ist, und es um 00:20 als „an“ zurückkommt
- **THEN** schaltet run_timer es um 00:20 aus
- **Beleg:** pytest `tests/test_off_timer.py`

### Requirement: Neustart von Home Assistant
Das System SHALL Ausschaltzeit und „aus um“ über einen Neustart erhalten. Eine während des Neustarts verpasste Ausschaltzeit SHALL nach dem vollständigen Start ausgeführt werden. Ist das Gerät nach dem Start an oder meldet es erst später an, ohne Ausschaltzeit, SHALL der Aus-Timer wie beim Einschalten beginnen. Die Wiederherstellung SHALL erst nach dem vollständigen Start von Home Assistant laufen.

#### Scenario: Neustart mit laufendem Timer
- **WHEN** die Ausschaltzeit 00:00 ist und Home Assistant von 22:00 bis 22:05 neu startet
- **THEN** ist die Ausschaltzeit danach weiter 00:00
- **Beleg:** pytest `tests/test_restore.py`

#### Scenario: Ausschaltzeit während Neustart verpasst
- **WHEN** die Ausschaltzeit 00:00 ist und Home Assistant von 23:55 bis 00:10 nicht läuft
- **THEN** schaltet run_timer das Gerät nach dem Start aus
- **Beleg:** pytest `tests/test_restore.py`

#### Scenario: Gerät an ohne Timer nach Start
- **WHEN** das Gerät eingeschaltet wurde, während Home Assistant nicht lief
- **THEN** startet nach dem Start ein Aus-Timer mit der Standarddauer
- **Beleg:** pytest `tests/test_restore.py`

#### Scenario: Gerät meldet sich erst nach dem Start
- **WHEN** das Gerät beim Start `unavailable` ist und danach „an“ meldet
- **THEN** startet die Standarddauer; ein gespeicherter Timer bleibt stattdessen bestehen, wenn es einen gibt
- **Beleg:** pytest `tests/test_restore.py`

#### Scenario: Echter Startablauf
- **WHEN** der Eintrag geladen wird, bevor Home Assistant fertig gestartet ist, und eine Ausschaltzeit verpasst wurde
- **THEN** wird erst nach `homeassistant_started` ausgeschaltet
- **Beleg:** pytest `tests/test_restore.py`
