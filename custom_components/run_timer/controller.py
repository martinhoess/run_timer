"""Run timer logic for one managed entity."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, time, timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.helpers.script import Script, async_validate_actions_config
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import CONF_DEFAULT_MINUTES, CONF_ON_ACTION, DOMAIN, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)

_UNREACHABLE = {STATE_UNAVAILABLE, STATE_UNKNOWN}
RETRY = timedelta(minutes=5)


def is_on(state: State | None) -> bool:
    """Return True if the state counts as switched on."""
    return state is not None and state.state not in _UNREACHABLE | {STATE_OFF}


def is_reachable(state: State | None) -> bool:
    """Return True if the entity reports a real state."""
    return state is not None and state.state not in _UNREACHABLE


def resolve_at(value: datetime | time, now: datetime) -> datetime:
    """Turn a time of day or a datetime into an aware UTC datetime.

    A bare time of day that is not in the future means the next day.
    A naive datetime is read in the Home Assistant time zone.
    """
    tz = dt_util.get_default_time_zone()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=tz)
        return dt_util.as_utc(value)
    local_now = dt_util.as_local(now)
    target = datetime.combine(local_now.date(), value, tzinfo=tz)
    if target <= local_now:
        target = datetime.combine(local_now.date() + timedelta(days=1), value, tzinfo=tz)
    return dt_util.as_utc(target)


def _parse(value: str | None) -> datetime | None:
    return dt_util.parse_datetime(value) if value else None


def _dump(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class RunTimerController:
    """Keeps off time, fixed off time and planned switch-on for one entity."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.target: str = entry.data[CONF_ENTITY_ID]
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self.off_at: datetime | None = None
        self.off_fixed: datetime | None = None
        self.on_at: datetime | None = None
        self.on_minutes: int | None = None
        self._timers: dict[str, CALLBACK_TYPE] = {}
        self._unsubs: list[CALLBACK_TYPE] = []
        self._listeners: list[Callable[[], None]] = []
        self._script: Script | None = None
        # Last reachable state seen; None until the entity reported one.
        self._last_known: str | None = None
        # off_at was set by a plan that is switching the entity on.
        self._off_from_plan = False

    # ----- lifecycle ---------------------------------------------------

    @property
    def default_minutes(self) -> int:
        """Return the default run time in minutes."""
        return int(self.entry.options[CONF_DEFAULT_MINUTES])

    async def async_load(self) -> None:
        """Load stored times and start once Home Assistant runs."""
        data = await self._store.async_load() or {}
        self.off_at = _parse(data.get("off_at"))
        self.off_fixed = _parse(data.get("off_fixed"))
        self.on_at = _parse(data.get("on_at"))
        self.on_minutes = data.get("on_minutes")
        self._unsubs.append(async_at_started(self.hass, self._async_started))

    async def async_unload(self) -> None:
        """Stop all timers and listeners and write the current state."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        for cancel in self._timers.values():
            cancel()
        self._timers.clear()
        await self._store.async_save(self._data())

    async def _async_started(self, _hass: HomeAssistant) -> None:
        self._unsubs.append(
            async_track_state_change_event(
                self.hass, self.target, self._async_state_changed
            )
        )
        await self._async_catch_up()

    async def _async_catch_up(self) -> None:
        """Reschedule stored times and handle what was missed."""
        now = dt_util.utcnow()
        state = self.hass.states.get(self.target)
        if is_reachable(state):
            assert state is not None
            self._last_known = state.state
        if state is not None and state.state == STATE_OFF and (
            self.off_at is not None and self.off_at > now
        ):
            # Switched off while Home Assistant was down.
            self.off_at = None
        if self.on_at is not None and self._plan_end() <= now:
            # Decide before a passed fixed off time is dropped; it may be the plan's end.
            self._set_on(None, None)
        self._set_fixed(
            self.off_fixed if self.off_fixed and self.off_fixed > now else None
        )
        if self.on_at is not None:
            if self.on_at > now:
                self._set_on(self.on_at, self.on_minutes)
            elif is_reachable(self.hass.states.get(self.target)):
                await self._async_run_plan()
            else:
                # Due, entity unreachable: wait, but not past the plan's end.
                self._reschedule_plan()
        if self.off_at is not None:
            if self.off_at > now:
                self._set_off_at(self.off_at)
            else:
                await self._async_off_due()
        elif is_on(self.hass.states.get(self.target)):
            self._start_auto(now)
        self._changed()

    # ----- listeners and persistence ----------------------------------

    @callback
    def async_add_listener(self, update: Callable[[], None]) -> CALLBACK_TYPE:
        """Register a callback that runs after every change."""
        self._listeners.append(update)
        return lambda: self._listeners.remove(update)

    @callback
    def async_options_updated(self) -> None:
        """React to changed options."""
        self._script = None
        self._reschedule_plan()
        self._changed()

    def _data(self) -> dict[str, Any]:
        return {
            "off_at": _dump(self.off_at),
            "off_fixed": _dump(self.off_fixed),
            "on_at": _dump(self.on_at),
            "on_minutes": self.on_minutes,
        }

    @callback
    def _changed(self) -> None:
        self._store.async_delay_save(self._data, 1)
        for update in list(self._listeners):
            update()

    # ----- scheduling --------------------------------------------------

    @callback
    def _schedule(
        self,
        key: str,
        when: datetime | None,
        action: Callable[[datetime], Awaitable[None]],
    ) -> None:
        if (cancel := self._timers.pop(key, None)) is not None:
            cancel()
        if when is not None and when > dt_util.utcnow():
            self._timers[key] = async_track_point_in_utc_time(self.hass, action, when)

    @callback
    def _set_off_at(self, when: datetime | None) -> None:
        self.off_at = when
        self._schedule("retry", None, self._async_off_timer)
        self._schedule("off", when, self._async_off_timer)

    @callback
    def _set_fixed(self, when: datetime | None) -> None:
        self.off_fixed = when
        self._schedule("fixed", when, self._async_fixed_timer)
        self._reschedule_plan()

    @callback
    def _set_on(self, when: datetime | None, minutes: int | None) -> None:
        self.on_at = when
        self.on_minutes = minutes if when is not None else None
        self._schedule("on", when, self._async_on_timer)
        self._schedule_expire()

    @callback
    def _schedule_expire(self) -> None:
        self._schedule(
            "expire",
            self._plan_end() if self.on_at is not None else None,
            self._async_plan_expired,
        )

    def _plan_end(self) -> datetime:
        """End of the plan: its own duration, else a later fixed off time, else the default."""
        assert self.on_at is not None
        if self.on_minutes is None and self.off_fixed is not None and self.off_fixed > self.on_at:
            return self.off_fixed
        return self.on_at + timedelta(minutes=self.on_minutes or self.default_minutes)

    @callback
    def _reschedule_plan(self) -> None:
        """Recompute the plan's end after the default run time or fixed off time changed."""
        if self.on_at is None:
            return
        if self._plan_end() <= dt_util.utcnow():
            self._set_on(None, None)
        else:
            self._schedule_expire()

    @callback
    def _start_auto(self, now: datetime) -> None:
        if self.off_fixed is not None and self.off_fixed > now:
            self._set_off_at(self.off_fixed)
        else:
            self._set_off_at(now + timedelta(minutes=self.default_minutes))

    # ----- timer callbacks ---------------------------------------------

    async def _async_off_timer(self, _now: datetime) -> None:
        for key in ("off", "retry"):
            if (cancel := self._timers.pop(key, None)) is not None:
                cancel()
        await self._async_off_due()

    async def _async_fixed_timer(self, _now: datetime) -> None:
        self._timers.pop("fixed", None)
        if self.on_at is not None and self._plan_end() == self.off_fixed:
            # The plan ended at this fixed off time without having run.
            self._set_on(None, None)
        self._set_fixed(None)
        self._changed()

    async def _async_on_timer(self, _now: datetime) -> None:
        self._timers.pop("on", None)
        if is_reachable(self.hass.states.get(self.target)):
            await self._async_run_plan()
        # Otherwise the plan stays due and runs when the entity is back,
        # until its end passes (_async_plan_expired).

    async def _async_plan_expired(self, _now: datetime) -> None:
        self._timers.pop("expire", None)
        if self.on_at is not None:
            self._set_on(None, None)
            self._changed()

    async def _async_off_due(self) -> None:
        """Switch off now; keep the off time while the entity is unreachable."""
        state = self.hass.states.get(self.target)
        if not is_reachable(state):
            return
        if not is_on(state):
            self._set_off_at(None)
            self._changed()
            return
        try:
            await self.hass.services.async_call(
                "homeassistant",
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: self.target},
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning(
                "Switching off %s failed, retrying in %s: %s", self.target, RETRY, err
            )
            self._schedule("retry", dt_util.utcnow() + RETRY, self._async_off_timer)
        # The state change to off clears the off time.

    async def _async_run_plan(self) -> None:
        """Run the planned switch-on."""
        end = self._plan_end()
        keeps_fixed = end == self.off_fixed
        self._set_on(None, None)
        if end <= dt_util.utcnow():
            self._changed()
            return
        await self._async_switch_on_until(end, keep_fixed=keeps_fixed)

    async def _async_switch_on_until(self, end: datetime, *, keep_fixed: bool) -> None:
        """Switch on with the given off time; drop it again if switching on failed."""
        if not keep_fixed:
            self._set_fixed(None)
        # Set the off time before switching on; the state change keeps it.
        self._set_off_at(end)
        self._off_from_plan = True
        self._changed()
        if not await self._async_turn_on() and not is_on(
            self.hass.states.get(self.target)
        ):
            self._off_from_plan = False
            self._set_off_at(None)
            self._changed()

    async def _async_turn_on(self) -> bool:
        """Run the switch-on action; return False if it failed."""
        actions = self.entry.options.get(CONF_ON_ACTION) or []
        try:
            if not actions:
                await self.hass.services.async_call(
                    "homeassistant",
                    SERVICE_TURN_ON,
                    {ATTR_ENTITY_ID: self.target},
                    blocking=True,
                )
                return True
            if self._script is None:
                sequence = await async_validate_actions_config(
                    self.hass, cv.SCRIPT_SCHEMA(actions)
                )
                self._script = Script(
                    self.hass, sequence, f"{self.entry.title} on action", DOMAIN
                )
            await self._script.async_run(
                run_variables={"entity_id": self.target}, context=Context()
            )
        except (HomeAssistantError, vol.Invalid) as err:
            _LOGGER.warning("Switching on %s failed: %s", self.target, err)
            return False
        return True

    # ----- state changes ------------------------------------------------

    async def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        old = event.data["old_state"]
        new = event.data["new_state"]
        if new is None or (old is not None and old.state == new.state):
            return
        previous = self._last_known
        if is_reachable(new):
            self._last_known = new.state
        now = dt_util.utcnow()
        if (
            self.on_at is not None
            and self.on_at <= now
            and "on" not in self._timers
            and is_reachable(new)
        ):
            await self._async_run_plan()
            return
        if new.state == STATE_OFF:
            self._off_from_plan = False
            if self.off_at is not None:
                self._set_off_at(None)
                self._changed()
            return
        if not is_on(new):
            return
        if self.off_at is not None and self.off_at <= now:
            await self._async_off_due()
            return
        if previous is not None and previous != STATE_OFF:
            # Still on, e.g. another climate mode or back from unavailable.
            return
        # Switched on: from off, or first real state since start.
        from_plan, self._off_from_plan = self._off_from_plan, False
        if self.off_at is not None and (from_plan or previous is None):
            return
        self._start_auto(now)
        self._changed()

    # ----- actions from services and entities ---------------------------

    def _running(self) -> bool:
        """On, or switching on / briefly unavailable with a timer: an off device has no off time."""
        return is_on(self.hass.states.get(self.target)) or self.off_at is not None

    def _no_timer(self) -> ServiceValidationError:
        return ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_timer",
            translation_placeholders={"entity_id": self.target},
        )

    def _require_future(self, when: datetime) -> None:
        if when <= dt_util.utcnow():
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="in_past",
                translation_placeholders={"entity_id": self.target},
            )

    async def async_extend(self, minutes: int) -> None:
        """Move the off time by minutes; switch off if it is not ahead.

        Without a timer an entity that is on counts from now; one that is off is
        switched on for the minutes (negative minutes do nothing then).
        """
        delta = timedelta(minutes=minutes)
        now = dt_util.utcnow()
        base = self.off_at
        if base is None:
            state = self.hass.states.get(self.target)
            if not is_reachable(state):
                raise self._no_timer()
            if not is_on(state):
                if minutes > 0:
                    await self._async_switch_on_until(now + delta, keep_fixed=False)
                    if self.off_at is None:
                        raise ServiceValidationError(
                            translation_domain=DOMAIN,
                            translation_key="switch_on_failed",
                            translation_placeholders={"entity_id": self.target},
                        )
                return
            base = now
        new = base + delta
        if new <= now:
            self._set_fixed(None)
            self._set_off_at(now)
            self._changed()
            await self._async_off_due()
            return
        if self.off_fixed is not None:
            self._set_fixed(self.off_fixed + delta)
        self._set_off_at(new)
        self._changed()

    async def async_off_in(self, minutes: int) -> None:
        """Switch off in minutes from now; while off, this is a fixed off time."""
        when = dt_util.utcnow() + timedelta(minutes=minutes)
        if self._running():
            self._set_fixed(None)
            self._set_off_at(when)
        else:
            self._set_fixed(when)
        self._changed()

    async def async_off_at(self, at: datetime | time) -> None:
        """Set the fixed off time."""
        when = resolve_at(at, dt_util.utcnow())
        self._require_future(when)
        self._set_fixed(when)
        if self._running():
            self._set_off_at(when)
        self._changed()

    async def async_on_at(self, at: datetime | time, minutes: int | None) -> None:
        """Plan a switch-on."""
        when = resolve_at(at, dt_util.utcnow())
        self._require_future(when)
        self._set_on(when, minutes)
        self._changed()

    async def async_on_in(self, minutes: int, duration: int | None) -> None:
        """Plan a switch-on in minutes from now."""
        await self.async_on_at(
            dt_util.utcnow() + timedelta(minutes=minutes), duration
        )

    async def async_cancel(self, what: str) -> None:
        """Drop off time and fixed off time, the plan, or both."""
        if what in ("off", "all"):
            self._set_off_at(None)
            self._set_fixed(None)
        if what in ("on", "all"):
            self._set_on(None, None)
        self._changed()

    async def async_set_default_minutes(self, minutes: int) -> None:
        """Store a new default run time."""
        self.hass.config_entries.async_update_entry(
            self.entry,
            options={**self.entry.options, CONF_DEFAULT_MINUTES: minutes},
        )
