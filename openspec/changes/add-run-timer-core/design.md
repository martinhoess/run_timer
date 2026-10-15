# Design

## Context

Ausgangslage siehe proposal.md. Quick Timer (MIT) liefert verwertbare Muster: Store für Tasks, Planung per `async_track_point_in_utc_time`, Ersetzen eines Tasks mit gleicher ID. Nicht übernehmen: Einzel-Instanz-Flow, monolithische Klasse, Frontend und Notifications, Wiederherstellung schon in `async_setup` (läuft vor den Ziel-Integrationen), den Reload-Fehler (nach dem Reload eines Eintrags laufen keine Timer mehr).

Geprüft gegen Home Assistant Core `2026.9.4`, die Zielversion:
- Die Helfer, die einen Device-Link über `device_info` herstellen (`async_device_info_to_link_from_entity` u. a.), sind seit Juli 2026 veraltet und geben `None` zurück. Neues Muster: `entity.device_entry = async_entity_id_to_device(hass, source_entity_id)`, siehe `derivative/sensor.py`.
- `ActionSelector`, `DurationSelector`, `EntitySelector` gibt es in `helpers/selector.py`, `async_at_started` in `helpers/start.py`.

## Goals / Non-Goals

**Goals:**
- Je Config-Eintrag eine Steuerung, die eine Ziel-Entität beobachtet und schaltet. Eine Quelle der Wahrheit für die Zeitpunkte.
- Logik ohne HA-Objekte testbar halten, sodass Zeitrechnung und Übergänge mit festen Uhrzeiten geprüft werden können.

**Non-Goals:**
- Kompatibilität mit HA-Versionen vor der getesteten Version
- Übernahme von Daten aus Time Off oder Quick Timer

## Decisions

**D1 – Ein Controller je Config-Eintrag.** Er hält drei Zeitpunkte: `off_at` (aktuelle Ausschaltzeit), `off_fixed` („aus um“) und `on_plan` (Zeit plus Dauer). Er abonniert die Ziel-Entität per `async_track_state_change_event` und hält höchstens einen Zeitplan-Callback je Zeitpunkt. Die Entitäten lesen nur vom Controller und rufen ihn auf, eigenen Zustand haben sie nicht.
Alternative: Zustand in den Entitäten per `RestoreEntity`. Verworfen, weil die Logik dann über vier Entitäten verteilt wäre und die Plan-Dauer kein Entitätswert ist.

**D2 – Persistenz per `helpers.storage.Store` je Eintrag** (Schlüssel `run_timer.<entry_id>`). Gespeichert werden die drei Zeitpunkte als ISO-UTC, geschrieben bei jeder Änderung. `async_remove_entry` löscht die Datei.
Alternative: ein Store für alle Einträge wie bei Quick Timer. Verworfen, weil Einträge unabhängig neu geladen werden und ein gemeinsames Dokument Schreibkonflikte zwischen den Einträgen erzeugt.

**D3 – Wiederherstellen erst nach dem Start.** `async_setup_entry` lädt den Store, Zeitpläne und Nachholen laufen aber erst über `async_at_started`. Erst dann sind die Ziel-Integrationen geladen. Beim Reload eines Eintrags läuft dieser Pfad sofort, weil HA schon läuft. Damit ist der Reload-Fehler von Quick Timer ausgeschlossen.

**D4 – Übergänge.** „An“ heißt, der Zustand ist nicht `off`, `unavailable` oder `unknown`. Der Controller merkt sich den letzten erreichbaren Zustand (seit dem Start noch keiner = unbekannt).
- Als Einschalten zählt „an“ nach zuletzt `off` oder nach unbekannt, auch über `unavailable` hinweg. Damit startet die Standarddauer auch nach einem Stromausfall, der eine Steckdose wieder einschaltet, und bei einem Gerät, das sich erst nach dem HA-Start meldet.
- „An“ nach zuletzt „an“ (anderer Modus, kurzer Ausfall) startet nichts. Ein abgebrochener Timer bleibt abgebrochen.
- Eine überfällige Ausschaltzeit wird bei jedem „an“ nachgeholt.
- Ein vorhandenes `off_at` übersteht das Einschalten nur, wenn es vom Plan stammt (Markierung, gesetzt vor dem Einschalten, gelöscht beim nächsten `off`) oder nach dem Start wiederhergestellt wurde; sonst gilt jetzt + Standarddauer bzw. „aus um“.
- `off_in` bei ausgeschaltetem Gerät setzt „aus um“ (jetzt + Minuten), damit `off_at` nur bei laufendem Gerät existiert.

**D5 – Ausschalten mit Nachholen.** Zur Ausschaltzeit wird `homeassistant.turn_off` aufgerufen, wenn das Gerät an ist. Ist das Gerät nicht erreichbar, bleibt `off_at` als „überfällig“ stehen; das nächste „an“ löst das Ausschalten aus, ein `off` leert den Zeitpunkt. Schlägt der Aufruf bei erreichbarem Gerät fehl (z. B. Cloud-Zeitüberschreitung), folgt alle 5 Minuten ein neuer Versuch, bis das Gerät `off` meldet oder die Ausschaltzeit geändert wird. Scheitert die Einschalt-Aktion eines Plans und ist das Gerät aus, wird die Plan-Ausschaltzeit verworfen.

**D6 – Einschalt-Aktion** als `ActionSelector` in den Optionen des Eintrags. Ausgeführt wird sie per `script.Script` mit der Ziel-Entität als Variable `entity_id`. Ist sie leer, gilt `homeassistant.turn_on`. Optionen werden bei Gebrauch gelesen; der Update-Listener verwirft nur das zwischengespeicherte Skript und aktualisiert die Entitäten. Kein Reload, sonst würde jedes Setzen der Standarddauer alle Timer neu aufbauen.

**D7 – Device-Zuordnung.** `device_entry = async_entity_id_to_device(hass, target)`. Liefert das `None`, bekommen die Entitäten ein eigenes Gerät mit `DeviceInfo(identifiers={(DOMAIN, entry_id)})` und dem Namen der Ziel-Entität.

**D7a – Umbenannte Ziel-Entität.** `async_handle_source_entity_changes` (wie bei `derivative`) schreibt eine neue `entity_id` in den Eintrag samt `unique_id` und lädt ihn neu; Timer bleiben über den Store erhalten.

**D8 – Dienste mit der Ziel-Entität als Adresse.** Alle Dienste nehmen `entity_id` (die verwaltete Ziel-Entität) und lösen sie auf den Eintrag auf. Ist die Entität nicht verwaltet, gibt es einen `ServiceValidationError`. Dashboard-Knöpfe kennen so nur die Entität des Geräts.
Alternative: `config_entry_id` als Adresse. Verworfen, weil die ID unlesbar ist und es in Bubble-Knöpfen keinen Selektor dafür gibt.

**D9 – Zeiten.** Intern wird alles in UTC gerechnet. Reine Uhrzeiten aus `off_at`/`on_at` werden in der lokalen Zeitzone von HA ausgelegt. Liegt die Uhrzeit nicht in der Zukunft, gilt der Folgetag. Minuten sind ganzzahlig.

**D10 – Tests** mit `pytest-homeassistant-custom-component`, dessen HA-Version zur Mindestversion passt. Die Zeit wird per `freezer`/`async_fire_time_changed` gesteuert. Als Ziel-Entitäten dienen `input_boolean` und `climate`/`fan` aus den Demo- oder Test-Plattformen. Dazu kommen `hassfest` und die HACS-Action in GitHub Actions.

**D11 – Mindestversion** = die HA-Version, gegen die die Tests laufen. Sie wird in `hacs.json` (`homeassistant`) eingetragen. Ältere Versionen werden nicht behauptet.

**D17 – Bedienbereich im More-Info-Dialog (0.1.5).** Anregung: Quick Timer hängt sich in den Dialog. HA hat dafür keine Schnittstelle. Laden per `frontend.add_extra_js_url` (offiziell, wirkt auf jeder Seite, anders als eine Lovelace-Ressource, die erst ein Dashboard lädt); welche Entitäten zu einem Gerät gehören, liefert der WebSocket-Befehl `run_timer/list`, statt Zustände zu durchsuchen. Inoffiziell bleibt nur das Einhängen: Pfad `home-assistant > ha-more-info-dialog > ha-adaptive-dialog > ha-more-info-info > .content`, geprüft gegen Frontend 20260930.4; ändert das Frontend den Aufbau, fehlt der Bereich ohne Fehler, die Dienste bleiben. Prüfen alle 500 ms statt MutationObserver über mehrere Shadow-Roots (einfacher, Kosten vernachlässigbar). Der Bereich hat keine eigene Logik, jeder Knopf ist ein Dienstaufruf, dieselben wie für Dashboard-Knöpfe. Offen: Uhrzeitfelder nutzen den Browser-Picker statt `ha-time-input`.

**D16 – `extend` ohne Timer (0.1.5).** Rückmeldung aus dem Panel-Versuch: „+15“ an einem ausgeschalteten Gerät brach mit „kein Timer“ ab. Entschieden 2026-10-16: eingeschaltet ohne Timer zählt ab jetzt; ausgeschaltet schaltet +X für X min ein (wie ein Plan mit eigener Dauer, also „aus um“ geleert), −X tut nichts; ein gesetztes geplantes Einschalten bleibt, verliert aber ein „aus um“ als Ende (es ist durch das +X verbraucht; sonst stünde bei laufendem Gerät „aus um“ neben einer anderen Ausschaltzeit). „Aus um“ und `off_in` gelten auch, solange das Gerät einschaltet oder kurz nicht erreichbar ist und schon eine Ausschaltzeit hat (`_running`); damit ist bei laufendem Gerät „aus um“ gesetzt ⇒ Ausschaltzeit = „aus um“, und „Löschen“ neben Schaltzeit aus ist im Panel derselbe Aufruf wie „Timer weg“. Verworfen: ab Standarddauer zählen, „aus um“ verschieben.

**D15 – Namen so, dass Ein vor Aus steht (0.1.4).** Die Geräteseite sortiert die Entitäten jeder Karte alphabetisch nach dem Namen (Frontend `ha-config-device-page.ts`, `stringCompare`), eine Reihenfolge kann die Integration nicht vorgeben. Mit „Switch off/on at“ bzw. „Aus/Ein um“ stand Aus immer zuerst, entgegen der gewohnten Folge an → aus; das lädt zum Verwechseln ein (Rückmeldung 2026-10-16). Englisch kann mit on/off nicht helfen („off“ < „on“), daher ein gemeinsamer Anfang plus ein Paar, das in beiden Sprachen richtig sortiert: „Schedule start/stop“, „Next start/stop“, „Schaltzeit an/aus“, „Nächstes An/Aus“. Verworfen: Ziffern als Vorsatz (sagt nichts), „Run from/until“. Die `translation_key`s bleiben, damit vorhandene Entitäts-IDs und Dashboards weiter gelten; neue Einträge bekommen IDs aus den Namen in der Systemsprache (en: `time.<gerät>_schedule_start`, de: `time.<gerät>_schaltzeit_an`; HA 2026.9.4 `entity_platform.py`, `NATIVE_ENTITY_IDS`). Specs und Design behalten die Begriffe „ein um“, „aus um“, Einschaltzeit und Ausschaltzeit als Konzeptnamen; auf der Geräteseite heißen sie Schaltzeit an/aus bzw. Nächstes An/Aus. Die Aktionen (`on_at`, `off_in` …) heißen weiter nach dem Verb („Ein um“, „Aus in“), denn dort sortiert nichts, und „Schaltzeit aus in 30 min“ läse sich schlechter.

**D14 – Plan ohne Dauer übernimmt „aus um“ (0.1.3).** Erst galt: Der Plan leert „aus um“ immer und setzt Planzeit + Standarddauer. Auf der Testinstanz hieß das: Licht an, „aus um 22:35“, „ein um 19:12“, Standarddauer 5 min → aus um 19:17. Eine ausdrücklich gesetzte Uhrzeit wiegt aber schwerer als die Standarddauer (Entscheidung 2026-10-16). Ein Plan mit eigener Dauer bleibt die ausdrücklichere Angabe und gewinnt weiter. Das Planende rechnet eine Stelle (`_plan_end`), auch für den Verfall eines wartenden Plans; ändern sich Standarddauer oder „aus um“, wird nur der Verfall neu geplant, der Einschalt-Timer bleibt.

**D13 – Einschaltzeit als eigener Sensor (0.1.2).** Gegenstück zur Ausschaltzeit: „ein um“ ist die Eingabe (Uhrzeit, volle Minuten), der Sensor das Ergebnis als Zeitstempel. Nur er zeigt Datum und Sekunden, liefert die relative Anzeige („in 2 h“) ohne Jinja und taugt als Trigger. Ein `binary_sensor` „Timer aktiv“ wie bei Time Off entfällt: leer oder gesetzt sagt dasselbe. Symbole je Entität über `icons.json` (Sichtprüfung 2026-10-16: Ein um/Aus um sahen gleich aus).

**D12 – „Ein um“/„Aus um“ als `time`-Entitäten.** Erst als `datetime` gebaut. Das HA-Frontend zeichnet `datetime` als Datums- und Uhrzeitfeld nebeneinander; auf der Geräteseite ragte die Zeile über die Karte hinaus (Sichtprüfung auf der Testinstanz 2026-10-15). `time` hat ein Feld und passt zur Bedeutung der Dienste: eine Uhrzeit meint das nächste Vorkommen. Pläne weiter als 24 h voraus gehen weiter per `on_at`/`off_at` mit Datum; die Entität zeigt dann nur die Uhrzeit.
Alternative: `datetime` behalten und den Darstellungsfehler im Frontend melden. Verworfen, weil die Uhrzeit-Bedeutung ohnehin die gebräuchliche ist und der Fehler sonst auf jeder Geräteseite sichtbar bliebe.

## Risks / Trade-offs

- [Integrationen melden „an“ verzögert oder zwischendurch `unknown`] → D4 startet nur bei `off` → an. Ein Gerät, das von `unknown` direkt auf an springt (z. B. nach seinem eigenen Neustart), bekommt keinen neuen Timer, sein bestehender bleibt.
- [Gerät eingeschaltet, während HA lief, aber vor dem Laden des Eintrags] → Nach `async_at_started` gilt: an, ohne `off_at` und ohne `off_fixed`, dann startet die Standarddauer (Spec off-timer, Neustart).
- [Einschalt-Aktion schaltet ein anderes Gerät oder gar nicht] → Das ist die Verantwortung des Nutzers. Der Plan gilt mit dem Aufruf als ausgeführt, die Ausschaltzeit wird trotzdem gesetzt.
- [`homeassistant.turn_off` passt bei manchen Domains nicht (z. B. `cover` = schließen)] → So gewollt, eine eigene Aus-Aktion gibt es erst bei Bedarf.
- [Öffentliches Repo] → Beispiele und Tests verwenden nur neutrale Entitäts-IDs.

## Migration Plan

1. Testinstallation per Kopie nach `/config/custom_components/run_timer` auf einer Testinstanz, Szenarien von Hand prüfen.
2. Danach auf der Produktivinstanz die bisher von Time Off verwalteten Geräte einzeln umziehen: Time Off für das Gerät abschalten, run_timer-Eintrag mit derselben Standarddauer anlegen; zuletzt Time Off entfernen.
3. Erstes GitHub-Release und Umstellung auf HACS Custom Repository.

Rückweg: run_timer-Eintrag entfernen und Time Off für das Gerät wieder aktivieren. Daten müssen dafür nicht übertragen werden. Konkrete Instanzen und Geräte stehen im Wiki `run_timer`, nicht im öffentlichen Repo.

## Open Questions

- Kann Time Off für ein einzelnes Gerät abgeschaltet werden, ohne den Eintrag zu löschen? Das wird beim Test nachgesehen, es ändert weder Specs noch Aufbau.
