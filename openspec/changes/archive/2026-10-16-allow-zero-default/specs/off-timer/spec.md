# Spec Delta

## MODIFIED Requirements

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
