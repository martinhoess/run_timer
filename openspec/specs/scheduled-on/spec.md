# scheduled-on Specification

## Purpose
Schaltet ein verwaltetes Gerät einmalig zu einem geplanten Zeitpunkt ein und legt fest, wie lange es danach läuft. Wiederkehrende Pläne gehören nicht dazu.

## Requirements

### Requirement: Einschalten planen
Das System SHALL je Gerät höchstens ein geplantes Einschalten führen. Die Dienste `on_in` (Minuten, > 0) und `on_at` (Uhrzeit oder Datum mit Uhrzeit) setzen es, jeweils mit optionaler Dauer in Minuten (Vorgabe: Standarddauer). Das Setzen der Entität „ein um“ ist gleichwertig zu `on_at` ohne Dauer. Ein neuer Plan ersetzt den alten; eine reine Uhrzeit in der Vergangenheit bedeutet den Folgetag.

#### Scenario: Ein um 06:00
- **WHEN** um 23:00 `on_at` mit 06:00 ohne Dauer aufgerufen wird (Standarddauer 240 min)
- **THEN** steht „ein um“ auf 06:00 des Folgetags
- **Beleg:** pytest `tests/test_scheduled_on.py`

#### Scenario: Neuer Plan ersetzt alten
- **WHEN** „ein um“ auf 06:00 steht und `on_in` mit 30 aufgerufen wird
- **THEN** steht „ein um“ auf jetzt + 30 min, der Plan für 06:00 ist weg
- **Beleg:** pytest `tests/test_scheduled_on.py`

### Requirement: Ausführen des Plans
Das System SHALL zur geplanten Zeit die Einschalt-Aktion ausführen, die Ausschaltzeit auf das Planende setzen und „ein um“ leeren. Planende ist Planzeit + Dauer; hat der Plan keine eigene Dauer und liegt ein gesetztes „aus um“ nach der Planzeit, ist es „aus um“, das dann stehen bleibt, sonst Planzeit + Standarddauer. Der Plan SHALL Vorrang vor einem laufenden Timer haben; ein Plan mit eigener Dauer auch vor „aus um“, das dabei geleert wird. Das Einschalten durch den Plan SHALL NOT zusätzlich die Standarddauer starten.

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

### Requirement: Gescheiterte Einschalt-Aktion
Das System SHALL die Ausschaltzeit eines Plans verwerfen, wenn die Einschalt-Aktion fehlschlägt und das Gerät aus bleibt.

#### Scenario: Aktion schlägt fehl
- **WHEN** ein Plan „ein um 13:00 für 30 min“ fällig wird und die Einschalt-Aktion fehlschlägt
- **THEN** bleibt das Gerät aus ohne Ausschaltzeit, und ein späteres Einschalten von Hand startet die Standarddauer
- **Beleg:** pytest `tests/test_scheduled_on.py`

### Requirement: Plan bleibt bei Hand-Aus
Das System SHALL ein geplantes Einschalten erhalten, wenn das Gerät vorher von Hand ein- oder ausgeschaltet wird.

#### Scenario: Ausgeschaltet vor dem Plan
- **WHEN** „ein um“ auf 06:00 steht und das Gerät um 23:00 von Hand ausgeschaltet wird
- **THEN** schaltet run_timer es um 06:00 ein
- **Beleg:** pytest `tests/test_scheduled_on.py`

### Requirement: Verpasster oder gescheiterter Plan
Das System SHALL ein geplantes Einschalten über einen Neustart erhalten. War es während des Neustarts fällig oder war das Gerät zur Planzeit nicht erreichbar, SHALL es nachgeholt werden, sobald Home Assistant gestartet bzw. das Gerät erreichbar ist, mit Ausschaltzeit Planzeit + Dauer. Liegt Planzeit + Dauer bereits zurück, SHALL der Plan ohne Schalten verworfen werden, auch wenn das Gerät bis dahin nicht erreichbar war.

#### Scenario: Nachholen mit Restdauer
- **WHEN** „ein um 06:00“ mit Standarddauer 240 min fällig war und Home Assistant erst um 06:40 wieder läuft
- **THEN** schaltet run_timer das Gerät ein, Ausschaltzeit 10:00
- **Beleg:** pytest `tests/test_restore.py`

#### Scenario: Zu spät
- **WHEN** „ein um 06:00 für 30 min“ verpasst wurde und Home Assistant erst um 07:00 wieder läuft
- **THEN** bleibt das Gerät aus und „ein um“ ist `unknown`
- **Beleg:** pytest `tests/test_restore.py`

#### Scenario: Gerät bleibt über das Planende weg
- **WHEN** „ein in 1 min für 30 min“ fällig wird, das Gerät aber bis über Planzeit + Dauer hinaus nicht erreichbar ist (auch beim Start von Home Assistant)
- **THEN** verfällt der Plan zu diesem Zeitpunkt: „ein um“ und Einschaltzeit sind `unknown`, und meldet sich das Gerät danach zurück, wird nicht eingeschaltet
- **Beleg:** pytest `tests/test_restore.py` (`test_unreachable_plan_expires_at_end`, `test_expired_plan_dropped_at_start_while_unreachable`, `test_due_plan_at_start_waits_until_end`, `test_default_change_moves_plan_end`)
