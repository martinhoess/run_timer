# Design: add-auto-mode

- **D1 Modus nutzt den vorhandenen Plan.** Im Modus `on` setzt das Ausschalten `on_at` ohne Dauer. Anzeige, Abbruch,
  Neustart und Nachholen kommen damit vom geplanten Einschalten, es gibt keinen zweiten Timer.
- **D2 Kein Auto-Aus im Modus `on`.** Ein Plan ohne eigene Dauer hat dort kein Ende, sonst schaltete er das Gerät nach
  der Standarddauer wieder aus. Die Standarddauer ist in diesem Modus die Zeit bis zum Einschalten.
- **D3 Ein vorhandener Plan bleibt.** Ausschalten überschreibt einen schon gesetzten Plan nicht; von Hand Geplantes hat
  Vorrang. Einschalten von Hand leert den Plan im Modus `on`, er ist dann gegenstandslos.
- **D4 Nur ein echtes Ausschalten plant.** Von `unavailable` zurück auf `off` plant nichts, wenn das Gerät vorher schon
  aus war: Ein per `cancel` verworfener Plan bleibt so verworfen. Nach einem Neustart ist der letzte Zustand unbekannt, ein ausgeschaltetes
  Gerät bekommt dann wieder einen Plan. Das ist Absicht: Der Modus soll das Gerät im Zweifel zurückbringen.
- **D5 Uhrzeit statt Dauer.** `_auto_time(start)` liefert die nächste Uhrzeit, sonst Start + Standarddauer, sonst nichts.
  Das gilt für das Aus nach dem Einschalten, das Planende und das Einschalten im Modus `on`.
- **D6 Startzeit.** `off_started` setzt sich beim ersten `_set_off_at` eines Laufs und leert sich mit ihm. Spätere
  Verschiebungen (`extend`) lassen sie stehen, der Balken rechnet also über die ganze Laufzeit. Gespeichert wie die
  übrigen Zeiten.
- **D8 Hand-Ein leert den Plan nur bei einem echten Wechsel.** Das Leeren steht im Zustandswechsel `off` → an, nicht in
  `_start_auto`: Ein Neustart behält damit jeden Plan. Geht das Gerät an, während Home Assistant aus ist, läuft ein alter Plan einmal
  leer und führt die Einschalt-Aktion aus. Das ist hinnehmbar und seltener als ein verlorener Plan.
- **D9 Scheitert das Einschalten,** plant der Modus `on` neu, sonst bliebe das Gerät ohne Übergang nach `off` ohne Rückweg.
- **D7 Geänderte Optionen** wirken ab dem nächsten Schaltvorgang. Einzige Ausnahme: Wird ein ausgeschaltetes Gerät auf
  `on` gestellt, plant es sofort, sonst bliebe es bis zum nächsten Umschalten aus. Der Controller merkt sich dafür den
  letzten Modus: Jede andere Änderung darf einen verworfenen Plan nicht zurückholen.
