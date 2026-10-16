# Spec Delta

## MODIFIED Requirements

### Requirement: Standarddauer
Das System SHALL je Gerät eine Standarddauer in Minuten führen, von 0 bis 1440; 0 bedeutet kein automatisches Ausschalten, Pläne, „aus um“ und die Dienste wirken trotzdem. Sie ist als `number`-Entität les- und schreibbar. Eine Änderung gilt ab dem nächsten Start eines Aus-Timers; ein laufender Timer bleibt unverändert.

#### Scenario: Standarddauer ändern
- **WHEN** der Nutzer die `number`-Entität von 240 auf 120 setzt, während ein Timer läuft
- **THEN** bleibt die laufende Ausschaltzeit gleich und der nächste Start nach dem Einschalten nutzt 120 min
- **Beleg:** pytest `tests/test_entities.py`

#### Scenario: Wert außerhalb des Bereichs
- **WHEN** jemand die Standarddauer auf −1 oder 1441 setzen will
- **THEN** lehnt Home Assistant den Wert ab und die Standarddauer bleibt unverändert
- **Beleg:** pytest `tests/test_entities.py`

#### Scenario: Standarddauer 0
- **WHEN** die Standarddauer 0 ist und das Gerät eingeschaltet wird
- **THEN** startet kein Timer und das Gerät bleibt an, bis es ausgeschaltet wird; ein gesetztes „aus um“ gilt weiter
- **Beleg:** pytest `tests/test_off_timer.py` (`test_default_zero_switch_on_starts_no_timer`, `test_default_zero_fixed_off_still_applies`)
