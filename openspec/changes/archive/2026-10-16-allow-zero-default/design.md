# Design

## Context

Entscheidung im Interview (Q11, 2026-10-15): „Standarddauer 0 – nicht erlaubt“. Am 2026-10-16 umgedreht, weil ein Gerät nur vorgeplant, aber nicht automatisch abgeschaltet werden soll.

## Decisions

**D18 – 0 heißt „kein Auto-Aus“ statt eigener Option.** Ein zusätzlicher Schalter „Auto-Aus an/aus“ wäre ein zweites Feld für dieselbe Aussage; 0 Minuten ist selbsterklärend und braucht keine Migration. `_plan_end()` liefert dann `None` (offenes Ende): kein Verfall-Timer, die Plan-Ausführung schaltet ohne Ausschaltzeit ein. Ein offener Plan wartet bei nicht erreichbarem Gerät unbegrenzt – ohne Ende gibt es keinen Zeitpunkt, ab dem er sinnlos wäre. Läuft beim Planstart schon eine Ausschaltzeit (etwa aus `off_in`), bleibt sie: ein offener Plan hat nichts Ausdrücklicheres zu bieten als „aus in 60 min“.

## Risks / Trade-offs

- [Offener Plan schaltet nach langer Funkstille ein, z. B. Stunden später] → nur bei Standarddauer 0 und Plan ohne Dauer; wer das nicht will, gibt dem Plan eine Dauer.
