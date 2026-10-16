# Proposal

## Why

Für das automatische Ausschalten von Geräten nach einer Laufzeit gibt es heute nur Time Off. Dessen Repo ist verschwunden, Updates kommen also keine mehr. Quick Timer wird gepflegt, startet aber nicht von selbst beim Einschalten, kann die Restzeit nicht verlängern und liefert keine Entitäten je Gerät. Zieldarstellung sind Dashboards mit Bubble-Card-Knöpfen ohne Helfer, und die brauchen pro Gerät abfragbare Entitäten und Dienste mit Parametern.

## What Changes

- Neue Custom-Integration `run_timer`, installierbar als HACS Custom Repository.
- Ein Config-Eintrag je verwaltetem Gerät, mit Ziel-Entität, Standarddauer (≥ 1 min) und optionaler Einschalt-Aktion. Jede Domain mit an/aus ist erlaubt.
- Entitäten je Gerät, angehängt an das vorhandene Gerät der Ziel-Entität (gibt es keins, ein eigenes): `number` Standarddauer, `sensor` Ausschaltzeit und `sensor` Einschaltzeit (Zeitstempel), `time` „ein um“, `time` „aus um“ (Uhrzeit, nächstes Vorkommen).
- Automatischer Aus-Timer bei jedem Einschalten, gleich von wo.
- Dienste `extend`, `off_in`, `off_at`, `on_in`, `on_at`, `cancel`.
- Zeitpunkte übersteht einen Neustart; Verpasstes wird nachgeholt, ebenso ein Ausschalten, das an einem nicht erreichbaren Gerät gescheitert ist.
- Ein Bedienbereich im More-Info-Dialog verwalteter Geräte (Nächstes An/Aus, ±15, aus in, Schaltzeiten), der nur die Dienste aufruft (D17).
- Nicht enthalten: Lovelace-Karte, Events, Benachrichtigungen, Presets/Verlauf, wiederkehrende Pläne (bleiben bei scheduler-component), eigene Aus-Aktion, Dashboard-Knöpfe (eigener Change im Dashboard-Generator), Umzug von Time Off (Betriebsschritt nach dem Test).

## Capabilities

### New Capabilities
- `device-setup`: Einrichten eines Geräts (Config-Eintrag, Standarddauer, Einschalt-Aktion) und die Entitäten, die run_timer je Gerät bereitstellt.
- `more-info-panel`: Bedienbereich im More-Info-Dialog verwalteter Geräte; ruft nur die Dienste auf.
- `off-timer`: Ausschalten nach Laufzeit: Start beim Einschalten, Verlängern/Verkürzen, „aus in/um“, Verhalten bei Hand-Aus, Neustart und nicht erreichbarem Gerät.
- `scheduled-on`: Einmaliges geplantes Einschalten „ein in/um“ mit optionaler Dauer, Vorrang vor laufendem Timer, Nachholen nach Neustart.

### Modified Capabilities

(keine)

## Impact

- Neues Repo `run_timer` (öffentlich auf GitHub, MIT mit Copyright-Hinweis von Quick Timer).
- Home Assistant: neue Integration unter `custom_components/run_timer`; Mindestversion wird im Design festgelegt.
- Betrieb: ersetzt später Time Off an drei Ventilatoren; der Dashboard-Generator bekommt in einem eigenen Change Knöpfe, die die Dienste aufrufen.
- Abhängigkeiten: keine Python-Pakete außer Home Assistant; Tests mit `pytest-homeassistant-custom-component`.
