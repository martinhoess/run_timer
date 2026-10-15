# Run Timer

Home Assistant custom integration that gives a device a run time. Switch it on, however that
happens, and it is switched off again after a default duration. You can extend or shorten the
running timer, set a fixed off time, or plan a one-time switch-on.

There is no custom card and nothing to set up as helpers. Each managed device gets five
entities, and six services do the rest, so any dashboard button (Bubble Card, tile, button
card) can drive it. The more-info dialog of a managed device also shows a small panel with
next start/stop, ±15, off in and the schedule times; it only calls the same services.
Home Assistant has no extension point for that dialog, so the panel relies on the frontend's
internal layout; if a frontend update changes it, the panel stays away and everything else
keeps working.

Recurring weekly schedules are out of scope. Use
[Scheduler](https://github.com/nielsfaber/scheduler-component) for those; when it switches a
managed device on, Run Timer's default duration applies like for any other switch-on.

## Installation

HACS → Integrations → ⋮ → Custom repositories → add `https://github.com/martinhoess/run_timer`
as *Integration* → install **Run Timer** → restart Home Assistant.

Requires Home Assistant 2026.9.4 or newer (the version the tests run against).

## Setup

Settings → Devices & services → Add integration → **Run Timer**. Pick the entity and the
default run time (1–1440 minutes). Add one entry per device. Any entity that has `turn_on` and
`turn_off` works: fans, lights, switches, climate, input_boolean, …

Options (⋮ → Configure) change the default run time and an optional **switch-on action**.
Planned switch-ons run this action instead of `homeassistant.turn_on`, for example to set a
climate mode. The variable `entity_id` holds the managed entity:

```yaml
- action: climate.set_hvac_mode
  target:
    entity_id: "{{ entity_id }}"
  data:
    hvac_mode: cool
```

## Entities

They are added to the device of the managed entity, or to an own device if it has none. The
names are chosen so that the start entity sorts before the stop entity on the device page, in
English and German.

| Entity | Meaning |
|---|---|
| `number` Default run time | Minutes until switch-off after switching on. Changes apply from the next switch-on. |
| `sensor` Next stop | When the device will be switched off (`unknown` if no timer runs). |
| `sensor` Next start | When the plan switches the device on, with date and seconds (`unknown` if nothing is planned). |
| `time` Schedule start | Planned switch-on (time of day). Setting it plans the next occurrence with the default run time. |
| `time` Schedule stop | Fixed switch-off time (time of day, next occurrence). Survives switching off and on until it is reached. |

## Behaviour

- Switching on starts the timer: the fixed switch-off time if one is set, otherwise now + default
  run time. This also applies when the device comes back on after being unavailable while it was
  off, e.g. a smart plug after a power cut.
- Switching off by hand drops the running timer. A fixed switch-off time and a planned switch-on
  stay.
- A planned switch-on wins over a running timer. With its own `duration` it also wins over a fixed
  switch-off time; without one, a fixed switch-off time later than the plan is kept as the off time.
- Times survive restarts. A switch-off or switch-on that was missed while Home Assistant was down
  is caught up after start; a switch-on is dropped if its run time has already ended.
- If the device is unavailable when it should be switched off or on, Run Timer waits until it is
  back. A failing switch-off is retried every 5 minutes.

## Services

All services take `entity_id` of the **managed** entity, e.g. the fan itself.

| Service | Fields | Effect |
|---|---|---|
| `run_timer.extend` | `minutes` (negative shortens) | Moves the off time; switches off now if nothing is left. Without a timer: counts from now if on, switches on for the minutes if off. |
| `run_timer.off_in` | `minutes` | Switch off in X minutes. |
| `run_timer.off_at` | `at` (`"18:00"` or date and time) | Fixed switch-off time; a passed time of day means tomorrow. |
| `run_timer.on_in` | `minutes`, optional `duration` | Plan a switch-on in X minutes. |
| `run_timer.on_at` | `at`, optional `duration` | Plan a switch-on; a passed time of day means tomorrow. |
| `run_timer.cancel` | `what`: `off`, `on` or `all` (default) | Drop timers and plans without switching. |

Examples for dashboard buttons:

```yaml
# +15 minutes
action: run_timer.extend
data:
  entity_id: fan.living_room
  minutes: 15

# run until 18:00
action: run_timer.off_at
data:
  entity_id: fan.living_room
  at: "18:00"

# off in 30 minutes
action: run_timer.off_in
data:
  entity_id: fan.living_room
  minutes: 30

# on at 06:00 for 90 minutes
action: run_timer.on_at
data:
  entity_id: fan.living_room
  at: "06:00"
  duration: 90

# drop the planned switch-on
action: run_timer.cancel
data:
  entity_id: fan.living_room
  what: "on"
```

## Credits

Based on ideas and code patterns from
[Quick Timer](https://github.com/jozefnad/homeassistant-quick_timer) by jozefnad (MIT).
See `LICENSE`.

## License

MIT, see `LICENSE`.
