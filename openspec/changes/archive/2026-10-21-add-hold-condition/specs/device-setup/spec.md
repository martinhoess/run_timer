# Spec Delta

## ADDED Requirements

### Requirement: Haltebedingung in den Optionen
Das System SHALL in den Optionen je Gerät ein optionales Template „Halten, solange“ und einen Nachlauf in Minuten (0–1440, Vorgabe 15) anbieten. Ein Template mit Syntaxfehler und Text ohne Template-Syntax SHALL der Optionsdialog ablehnen. Eine Änderung SHALL ohne Neustart gelten: ab dem nächsten Einschalten, bei einem Lauf, der schon einer Bedingung folgt, sofort.

#### Scenario: Haltebedingung setzen
- **WHEN** der Nutzer in den Optionen ein Template und einen Nachlauf von 10 min speichert
- **THEN** stehen beide in den Optionen des Eintrags und das nächste Einschalten folgt der Bedingung
- **Beleg:** pytest `tests/test_config_flow.py` (`test_options_hold_template`), `tests/test_hold.py` (`test_options_change_starts_tracking`)

#### Scenario: Ungültiges Template
- **WHEN** der Nutzer `{{ is_state(` speichern will
- **THEN** lehnt der Dialog die Eingabe am Feld „Halten, solange“ ab und die Optionen bleiben unverändert
- **Beleg:** pytest `tests/test_config_flow.py` (`test_options_invalid_hold_template`)

#### Scenario: Text ohne Template-Klammern
- **WHEN** der Nutzer `is_state('binary_sensor.room', 'on')` ohne `{{ }}` speichern will
- **THEN** zeigt der Dialog am Feld den Hinweis, dass es kein Template ist
- **Beleg:** pytest `tests/test_config_flow.py` (`test_options_static_hold_template`)

#### Scenario: Bedingung ändern, während sie hält
- **WHEN** ein Gerät gehalten wird und der Nutzer ein Template speichert, das gerade falsch ist
- **THEN** beginnt sofort der Nachlauf
- **Beleg:** pytest `tests/test_hold.py` (`test_options_change_while_held_applies_now`)
