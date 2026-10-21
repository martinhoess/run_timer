# Proposal

## Why

Ein Gerät soll nicht nur eine feste Laufzeit haben, sondern an bleiben, solange eine Bedingung gilt, und erst einen Nachlauf später ausgehen: Licht im Wohnzimmer, solange jemand im Raum ist (kurz aufs Klo zählt nicht als Verlassen), oder Licht draußen, solange niemand zuhause ist. Bisher geht das nur mit einer eigenen Automation neben run_timer.

## What Changes

- Neue Option je Gerät „Halten, solange“: ein Template, wahr heißt halten. Damit gehen auch umgekehrte Fälle (`not …`, `!=`).
- Neue Option „Nachlauf“ in Minuten (0–1440, Vorgabe 15).
- Läuft das Gerät nach einem Einschalten mit Standarddauer, setzt run_timer bei wahrer Bedingung keine Ausschaltzeit; wird sie falsch, gilt jetzt + Nachlauf; wird sie im Nachlauf wieder wahr, fällt die Ausschaltzeit weg.
- Ausdrückliche Eingriffe (`extend`, `off_in`, `off_at`, `cancel`, Pläne, „aus um“ beim Einschalten) haben Vorrang: bis zum nächsten Einschalten greift die Bedingung nicht mehr.
- Sensor „Nächstes Aus“ bekommt das Attribut `held`, solange die Bedingung das Gerät hält.

## Capabilities

### New Capabilities

### Modified Capabilities
- `device-setup`: Optionen „Halten, solange“ und „Nachlauf“.
- `off-timer`: Halten nach Bedingung.

## Impact

`controller.py` (Template-Tracking, `_start_auto`, Neustart), `config_flow.py`, `const.py`, `sensor.py`, Übersetzungen, README; Version 0.1.8.
