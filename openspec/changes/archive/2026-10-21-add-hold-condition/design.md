# Design

## Context

Anwendungsfall: Licht an, bis man den Raum verlässt, mit 10–15 min Nachlauf, damit kurzes Rausgehen nicht zählt; nicht nur „Entität ist an“, auch umgekehrte Fälle wie Licht draußen, solange niemand zuhause ist.

## Decisions

**D19 – Template statt Entität oder Bedingungsblock.** Eine Entität deckt nur „ist an“ ab; umgekehrte Fälle bräuchten einen Hilfssensor. Der Bedingungs-Baustein aus dem Automations-Editor (`ConditionSelector`) meldet keine Änderungen, Home Assistant prüft Bedingungen nur, wenn ein Auslöser feuert. Ein Template mit `async_track_template_result` ist der Weg der Template-Entitäten selbst: neu gerechnet bei jeder Änderung der genannten Entitäten, Templates mit `now()` jede Minute. Auswertung mit `result_as_boolean`; ein Fehler beim Rendern zählt als falsch. Text ohne Template-Syntax (`is_static`) lehnt der Optionsdialog ab, weil er nie wahr ergäbe.

**D20 – Die Bedingung hält nur Läufe mit Standarddauer.** Sie gilt für einen Lauf, der mit `_start_auto` beginnt (Einschalten von außen) und kein „aus um“ hat. Jeder ausdrückliche Eingriff beendet das für diesen Lauf (Merker `hold_run`, gespeichert für den Neustart), ebenso ein Plan, auch ein offener. So bleibt „aus in 30 min“ ein Versprechen, das die Bedingung nicht aushebelt. Eine geänderte Bedingung in den Optionen gilt ab dem nächsten Einschalten; folgt der Lauf schon einer Bedingung, wechselt er sofort auf die neue.

**D21 – Nachlauf nur am Übergang.** Der Lauf merkt sich den Wert, nach dem er zuletzt gehandelt hat (`hold_applied`, gespeichert). Nur ein Wechsel davon zählt: wahr → keine Ausschaltzeit; falsch nach wahr → jetzt + Nachlauf, aber nur, wenn gerade keine läuft. Ist die Bedingung schon beim Einschalten falsch, läuft die Standarddauer (bei 0 keine); wird sie später wahr, hält sie, und danach gilt der Nachlauf. Neu tracken, Options-Updates (auch über die `number`-Entität) und Neustarts lösen deshalb keinen Nachlauf aus, solange die Bedingung nie gehalten hat. Ein Wechsel, während das Gerät nicht erreichbar ist, wird bei seiner Rückkehr nachgeholt.

**D22 – Neustart.** Beim Start gleicht der Lauf `hold_applied` mit der Bedingung ab: wahr fällt ein gespeicherter Nachlauf weg; hielt sie vorher und ist jetzt falsch, beginnt der Nachlauf beim Start, der genaue Moment des Wechsels während der Ausfallzeit ist nicht bekannt. Ist das Gerät beim Start aus, ist der Lauf vorbei.

## Risks / Trade-offs

- [Bedingung bleibt dauernd wahr, z. B. hängender Präsenzsensor] → Gerät bleibt an; sichtbar am Attribut `held`, ein Knopf (`off_in`, `extend`) übersteuert.
- [Bedingung entfernt, während sie hält] → der Nachlauf beginnt, nicht die Standarddauer; der Lauf hatte keine Standarddauer mehr.
