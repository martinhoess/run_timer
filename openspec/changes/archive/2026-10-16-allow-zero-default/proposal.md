# Proposal

## Why

Manche Geräte, etwa ein Heizgerät mit eigener Frostschutz-Steuerung, sollen sich nur vorplanen lassen („an um 06:00“, „an in 30 min“), ohne dass ein Einschalten von Hand nach einer Standarddauer wieder ausschaltet. Bisher war die Standarddauer mindestens 1 min.

## What Changes

- Standarddauer 0 erlaubt: kein automatisches Ausschalten beim Einschalten.
- Ein Plan ohne eigene Dauer und ohne späteres „aus um“ hat bei Standarddauer 0 kein Ende: er schaltet ein und setzt keine Ausschaltzeit; er verfällt nicht.
- „Aus um“, Pläne mit Dauer, `extend` und `off_in` wirken unverändert.

## Capabilities

### New Capabilities

### Modified Capabilities
- `device-setup`: Wertebereich der Standarddauer 0–1440, 0 = kein automatisches Aus.
- `scheduled-on`: Plan ohne Ende bei Standarddauer 0; verfällt nicht.
- `off-timer`: Einschalten startet bei Standarddauer 0 keinen Timer.

## Impact

`controller.py` (`_plan_end` darf offen sein, `_start_auto`), `const.py`, Übersetzungen, README; Version 0.1.7.
