# Spec Delta

## MODIFIED Requirements

### Requirement: Aus-Timer beim Einschalten
Das System SHALL eine Ausschaltzeit setzen, wenn die Ziel-Entität „an“ meldet und ihr letzter erreichbarer Zustand `off` war oder seit dem Start noch keiner bekannt ist, auch wenn dazwischen `unavailable` lag. Ist „aus um“ gesetzt und liegt in der Zukunft, gilt diese Zeit, sonst jetzt + Standarddauer; bei Standarddauer 0 startet dann kein Timer. Ist eine Haltebedingung gesetzt und wahr, startet ebenfalls kein Timer (siehe „Halten nach Bedingung“). War der letzte erreichbare Zustand schon „an“, startet nichts.

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

### Requirement: Neustart von Home Assistant
Das System SHALL Ausschaltzeit und „aus um“ über einen Neustart erhalten. Eine während des Neustarts verpasste Ausschaltzeit SHALL nach dem vollständigen Start ausgeführt werden. Ist das Gerät nach dem Start an oder meldet es erst später an, ohne Ausschaltzeit, SHALL der Aus-Timer wie beim Einschalten beginnen. Ein Lauf, der vor dem Neustart einer Haltebedingung folgte, SHALL ihr stattdessen weiter folgen (siehe „Halten nach Bedingung“). Die Wiederherstellung SHALL erst nach dem vollständigen Start von Home Assistant laufen.

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
- **THEN** folgt ein gehaltener Lauf zuerst der Bedingung: ist sie inzwischen falsch, beginnt der Nachlauf, ist sie wieder wahr, fällt ein gespeicherter Nachlauf weg, ein abgelaufener schaltet bei weiter falscher Bedingung aus; sonst bleibt ein gespeicherter Timer bestehen, und ohne einen startet die Standarddauer
- **Beleg:** pytest `tests/test_restore.py`, `tests/test_hold.py` (`test_restart_unreachable_then_on_follows_hold`, `test_restart_unreachable_grace_dropped_when_true`, `test_restart_unreachable_passed_grace_still_false`)

#### Scenario: Echter Startablauf
- **WHEN** der Eintrag geladen wird, bevor Home Assistant fertig gestartet ist, und eine Ausschaltzeit verpasst wurde
- **THEN** wird erst nach `homeassistant_started` ausgeschaltet
- **Beleg:** pytest `tests/test_restore.py`

## ADDED Requirements

### Requirement: Halten nach Bedingung
Ist ein Template „Halten, solange“ gesetzt, SHALL das System einen Lauf, der mit der Standarddauer beginnt (Einschalten ohne „aus um“), nach der Bedingung führen: ist das Template wahr, gibt es keine Ausschaltzeit; wird es falsch, ist die Ausschaltzeit jetzt + Nachlauf; wird es vorher wieder wahr, fällt sie weg. Ein Rendering-Fehler SHALL als falsch zählen. Nur ein Wechsel gegenüber dem Wert, nach dem der Lauf zuletzt gehandelt hat, SHALL zählen; ein Wechsel, während das Gerät nicht erreichbar ist, SHALL bei seiner Rückkehr nachgeholt werden. `extend`, `off_in`, `off_at`, `cancel` und ein Plan, auch ein offener, SHALL Vorrang haben: bis zum nächsten Einschalten folgt der Lauf der Bedingung nicht mehr. Der Sensor „Nächstes Aus“ SHALL das Attribut `held` zeigen, wahr, solange die Bedingung das Gerät hält.

#### Scenario: Raum verlassen
- **WHEN** die Bedingung wahr ist, das Gerät eingeschaltet wird und die Bedingung 2 h später falsch wird (Nachlauf 15 min)
- **THEN** gibt es bis dahin keine Ausschaltzeit und `held` ist wahr; danach ist die Ausschaltzeit 15 min später, und dann ist das Gerät aus
- **Beleg:** pytest `tests/test_hold.py` (`test_hold_until_condition_false`)

#### Scenario: Kurz raus und zurück
- **WHEN** die Bedingung im Nachlauf wieder wahr wird
- **THEN** ist die Ausschaltzeit leer und das Gerät bleibt an
- **Beleg:** pytest `tests/test_hold.py` (`test_back_within_grace`)

#### Scenario: Umgekehrte Bedingung
- **WHEN** das Template `{{ not is_state('input_boolean.home', 'on') }}` lautet und `input_boolean.home` von `off` auf `on` wechselt
- **THEN** beginnt der Nachlauf
- **Beleg:** pytest `tests/test_hold.py` (`test_negated_condition`)

#### Scenario: Bedingung beim Einschalten falsch
- **WHEN** die Bedingung beim Einschalten falsch ist und später wahr und wieder falsch wird
- **THEN** gilt zuerst die Standarddauer, solange sie wahr ist keine Ausschaltzeit, danach der Nachlauf
- **Beleg:** pytest `tests/test_hold.py` (`test_false_at_switch_on_uses_default`)

#### Scenario: Eingriff von Hand
- **WHEN** die Bedingung das Gerät hält und `off_in` 30 min aufgerufen wird
- **THEN** geht das Gerät nach 30 min aus, auch wenn die Bedingung wahr bleibt; ein `cancel` lässt es an, auch wenn sie danach falsch wird
- **Beleg:** pytest `tests/test_hold.py` (`test_manual_off_in_wins`, `test_cancel_ends_hold`, `test_extend_ends_hold`, `test_failed_extend_keeps_hold`, `test_fixed_off_at_switch_on_is_not_held`)

#### Scenario: Plan
- **WHEN** ein Plan ein gehaltenes Gerät mit Dauer 30 min übernimmt oder ein offener Plan (Standarddauer 0) einschaltet
- **THEN** gilt das Planende bzw. keine Ausschaltzeit, und ein Wechsel der Bedingung ändert nichts
- **Beleg:** pytest `tests/test_hold.py` (`test_plan_on_held_device_wins`, `test_open_plan_is_not_held`)

#### Scenario: Bedingung nie wahr
- **WHEN** die Standarddauer 0 ist, die Bedingung beim Einschalten falsch ist und danach die Standarddauer geändert oder Home Assistant neu gestartet wird
- **THEN** bleibt das Gerät ohne Ausschaltzeit an
- **Beleg:** pytest `tests/test_hold.py` (`test_default_zero_never_held_gets_no_grace`, `test_restart_never_held_gets_no_grace`)

#### Scenario: Gerät nicht erreichbar beim Wechsel
- **WHEN** die Bedingung falsch wird, während das gehaltene Gerät `unavailable` ist, und es danach wieder „an“ meldet
- **THEN** beginnt der Nachlauf bei der Rückkehr
- **Beleg:** pytest `tests/test_hold.py` (`test_change_while_unavailable`)

#### Scenario: Nachlauf 0 und Rendering-Fehler
- **WHEN** der Nachlauf 0 ist und das Template einen Fehler wirft
- **THEN** zählt die Bedingung als falsch und das Gerät geht sofort aus
- **Beleg:** pytest `tests/test_hold.py` (`test_render_error_counts_false`)

#### Scenario: Neustart
- **WHEN** die Bedingung vor einem Neustart hielt und beim Start wahr bzw. falsch ist
- **THEN** hält sie weiter ohne Ausschaltzeit bzw. beginnt der Nachlauf beim Start; ein gespeicherter Nachlauf fällt bei wahrer Bedingung weg; ist das Gerät beim Start aus oder wird es von Hand ausgeschaltet, ist `held` falsch
- **Beleg:** pytest `tests/test_hold.py` (`test_restart_keeps_hold`, `test_restart_condition_false_starts_grace`, `test_restart_drops_grace_when_true`, `test_restart_device_off_not_held`, `test_switch_off_clears_held`)
