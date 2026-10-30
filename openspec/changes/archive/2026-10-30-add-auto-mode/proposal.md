# Proposal: add-auto-mode

## Warum
Run Timer kann nur „an → nach Laufzeit aus“. Manche Entitäten stehen normalerweise auf an und sollen nach dem
Ausschalten von selbst zurückkommen, zum Beispiel ein Hauptschalter. Das braucht heute eine eigene Automation. Eine
Laufzeit reicht dafür nicht: „am nächsten Morgen wieder an“ ist eine Uhrzeit. Dashboards wollen außerdem einen
Fortschrittsbalken zeigen, dafür fehlt die Startzeit des Timers.

## Was sich ändert
- Option **Modus**: `off` (Vorgabe, wie bisher) oder `on` (Ausschalten plant das Einschalten).
- Option **Uhrzeit**: ist sie gesetzt, zählt in beiden Modi die nächste Uhrzeit statt der Standarddauer.
- Attribut `started_at` am Sensor „Next stop“: seit wann der laufende Timer läuft.

## Nicht Teil
Wiederkehrende Pläne, die Haltebedingung im Modus `on`, ein Neuberechnen laufender Zeiten bei geänderter Option.
