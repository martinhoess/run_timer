## ADDED Requirements

### Requirement: Modus on plant das Einschalten
Im Modus `on` SHALL das Ausschalten ein Einschalten ohne eigene Dauer planen: zum nächsten Vorkommen der Uhrzeit, ohne Uhrzeit nach der Standarddauer, bei Standarddauer 0 ohne Uhrzeit gar nicht. Ein vorhandener Plan MUST bestehen bleiben.

#### Scenario: Wieder an nach der Standarddauer
- **WHEN** das Gerät um 12:00 ausgeschaltet wird (Modus `on`, Standarddauer 60)
- **THEN** ist es um 13:00 wieder an und bleibt an
- **Beleg:** pytest `tests/test_auto_mode.py`

#### Scenario: Wieder an zur Uhrzeit
- **WHEN** das Gerät um 12:00 ausgeschaltet wird (Modus `on`, Uhrzeit 04:00)
- **THEN** steht „ein um“ auf 04:00 des Folgetags
- **Beleg:** pytest `tests/test_auto_mode.py`

### Requirement: Plan im Modus on
Ein Plan ohne eigene Dauer SHALL im Modus `on` nur an einem späteren „aus um“ enden, sonst bleibt das Gerät danach an. Einschalten von Hand SHALL den Plan leeren, ein Neustart nicht. Scheitert das Einschalten, SHALL ein neuer Plan entstehen.

#### Scenario: Von Hand früher eingeschaltet
- **WHEN** das Gerät vor der Planzeit von Hand eingeschaltet wird
- **THEN** ist „ein um“ `unknown`
- **Beleg:** pytest `tests/test_auto_mode.py`

#### Scenario: Plan von Hand bleibt
- **WHEN** ein Plan in 10 min für 20 min steht und das Gerät ausgeschaltet wird
- **THEN** bleibt der Plan und das Gerät geht nach 20 min Laufzeit aus
- **Beleg:** pytest `tests/test_auto_mode.py`

#### Scenario: Verworfener Plan bleibt verworfen
- **WHEN** der Plan per `cancel` verworfen wird und das Gerät über `unavailable` auf `off` zurückkommt
- **THEN** entsteht kein neuer Plan
- **Beleg:** pytest `tests/test_auto_mode.py`

#### Scenario: Einschalten scheitert
- **WHEN** die Einschalt-Aktion zur Planzeit fehlschlägt
- **THEN** steht ein neuer Plan, das Gerät bleibt nicht ohne Rückweg aus
- **Beleg:** pytest `tests/test_auto_mode.py`

#### Scenario: Neustart bei laufendem Gerät
- **WHEN** das Gerät läuft, ein Plan steht und Home Assistant neu startet
- **THEN** bleibt der Plan
- **Beleg:** pytest `tests/test_auto_mode.py`

#### Scenario: Ausgeschaltet während Home Assistant aus war
- **WHEN** das Gerät beim Start aus ist und kein Plan steht
- **THEN** steht danach ein Plan
- **Beleg:** pytest `tests/test_auto_mode.py`

## MODIFIED Requirements

### Requirement: Ausführen des Plans
Das System SHALL zur geplanten Zeit die Einschalt-Aktion ausführen, die Ausschaltzeit auf das Planende setzen und „ein um“ leeren. Planende ist Planzeit + Dauer; hat der Plan keine eigene Dauer und liegt ein gesetztes „aus um“ nach der Planzeit, ist es „aus um“, das dann stehen bleibt, sonst das nächste Vorkommen der Uhrzeit nach der Planzeit, falls gesetzt, sonst Planzeit + Standarddauer (im Modus `on` keins von beiden); bei Standarddauer 0 hat ein solcher Plan kein Ende und lässt eine schon laufende Ausschaltzeit stehen. Der Plan SHALL Vorrang vor einem laufenden Timer haben; ein Plan mit eigener Dauer auch vor „aus um“, das dabei geleert wird. Das Einschalten durch den Plan SHALL NOT zusätzlich die Standarddauer starten.

#### Scenario: Plan mit Dauer
- **WHEN** „ein um“ 06:00 mit Dauer 90 min fällig wird und das Gerät aus ist
- **THEN** ist das Gerät an, die Ausschaltzeit 07:30 und „ein um“ `unknown`
- **Beleg:** pytest `tests/test_scheduled_on.py`

#### Scenario: Gerät läuft schon
- **WHEN** das Gerät läuft, Ausschaltzeit 08:00, und ein Plan „ein um 06:00 für 30 min“ fällig wird
- **THEN** ist die Ausschaltzeit 06:30
- **Beleg:** pytest `tests/test_scheduled_on.py`

#### Scenario: Plan ohne Dauer bei gesetztem „aus um“
- **WHEN** „aus um 22:35“ gesetzt ist, die Standarddauer 5 min beträgt und „ein um 19:12“ ohne Dauer fällig wird
- **THEN** ist die Ausschaltzeit 22:35 und „aus um“ bleibt gesetzt; liegt „aus um“ vor der Planzeit, ist es bis dahin abgelaufen und die Ausschaltzeit ist Planzeit + Standarddauer
- **Beleg:** pytest `tests/test_scheduled_on.py` (`test_plan_without_duration_keeps_fixed_off`, `test_fixed_off_before_plan_does_not_count`, `test_waiting_plan_lasts_until_fixed_off`, `test_waiting_plan_ends_with_fixed_off`; Neustart: `tests/test_restore.py` `test_plan_ended_by_passed_fixed_off_at_start`)

#### Scenario: Plan ohne Ende bei Standarddauer 0
- **WHEN** die Standarddauer 0 ist und ein Plan ohne eigene Dauer und ohne späteres „aus um“ fällig wird
- **THEN** schaltet run_timer ein und setzt keine Ausschaltzeit; ein solcher Plan verfällt nicht und wartet bei nicht erreichbarem Gerät, bis es zurück ist
- **Beleg:** pytest `tests/test_scheduled_on.py` (`test_default_zero_plan_without_duration_stays_on`, `test_default_zero_plan_with_duration_ends`, `test_default_zero_open_plan_waits_for_unreachable`)

#### Scenario: Offener Plan und laufende Ausschaltzeit
- **WHEN** bei Standarddauer 0 das Gerät mit „aus in 60 min“ läuft und ein offener Plan fällig wird
- **THEN** bleibt die Ausschaltzeit stehen; lief sie ab, während das Gerät nicht erreichbar war, schaltet run_timer bei dessen Rückkehr aus und verwirft den Plan
- **Beleg:** pytest `tests/test_scheduled_on.py` (`test_default_zero_open_plan_keeps_running_off_time`, `test_default_zero_open_plan_with_passed_off_time`)

### Requirement: Plan bleibt bei Hand-Aus
Das System SHALL ein geplantes Einschalten erhalten, wenn das Gerät vorher von Hand ein- oder ausgeschaltet wird; im Modus `on` leert Einschalten von Hand den Plan.

#### Scenario: Ausgeschaltet vor dem Plan
- **WHEN** „ein um“ auf 06:00 steht und das Gerät um 23:00 von Hand ausgeschaltet wird
- **THEN** schaltet run_timer es um 06:00 ein
- **Beleg:** pytest `tests/test_scheduled_on.py`
