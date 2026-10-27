"""Sensor platform — one entity per CG248075 holding in the active limit."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ADDR_SETPOINT_COOL,
    ADDR_SETPOINT_DHW,
    ADDR_SETPOINT_HEAT,
    DOMAIN,
    LIGHT_ADDRS,
    LIVE_LOG_UI_LINES,
)
from .coordinator import SprsunCoordinator
from .register_map import decode_value, setpoint_c, slug

SETPOINT_ADDRS = {ADDR_SETPOINT_DHW, ADDR_SETPOINT_COOL, ADDR_SETPOINT_HEAT}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    data = hass.data[DOMAIN]
    coordinator: SprsunCoordinator = data["coordinator"]
    registers = data["registers"]
    entities = [SprsunRegisterSensor(coordinator, reg) for reg in registers]
    entities.append(SprsunRefreshMsSensor(coordinator))
    entities.append(SprsunLiveLogSensor(coordinator))
    async_add_entities(entities)


class SprsunRegisterSensor(CoordinatorEntity[SprsunCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SprsunCoordinator, reg) -> None:
        super().__init__(coordinator)
        self._reg = reg
        self._attr_name = f"SPRSUN [{reg.group}] {reg.name}"
        self._attr_unique_id = f"sprsun_pdf_{reg.addr:04d}_{slug(reg.name)}"
        # No force_update and no per-poll timestamp attribute: an unchanged
        # value must not create a recorder row on every poll. The state machine
        # still refreshes each scan; history records real changes only.
        if reg.unit:
            self._attr_native_unit_of_measurement = reg.unit
        if reg.device_class == "temperature":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif reg.device_class == "pressure":
            self._attr_device_class = SensorDeviceClass.PRESSURE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif reg.effective_scale() is not None:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        if self._reg.addr not in data:
            return None
        raw = data[self._reg.addr]
        if self._reg.addr in SETPOINT_ADDRS:
            self._attr_native_unit_of_measurement = "°C"
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            return setpoint_c(raw)
        return decode_value(self._reg, raw)

    @property
    def extra_state_attributes(self):
        # Keep these constant: a timestamp here would make every poll look like
        # a state change and defeat the recorder's change detection.
        return {
            "register": self._reg.addr,
            "poll_group": "light" if self._reg.addr in LIGHT_ADDRS else "full",
        }

class SprsunRefreshMsSensor(CoordinatorEntity[SprsunCoordinator], SensorEntity):
    _attr_name = "SPRSUN Modbus refresh"
    _attr_unique_id = "sprsun_modbus_refresh_ms"
    _attr_native_unit_of_measurement = "ms"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return self.coordinator.last_refresh_ms

    @property
    def extra_state_attributes(self):
        import time

        full_age = None
        if self.coordinator.last_full_at is not None:
            full_age = round(time.monotonic() - self.coordinator.last_full_at, 1)
        until = self.coordinator.seconds_until_full
        return {
            "kind": self.coordinator.last_kind,
            "blocks": len(
                self.coordinator.blocks
                if self.coordinator.last_kind == "full"
                else self.coordinator.light_blocks
            ),
            "registers": len(self.coordinator.registers),
            "cached": len(self.coordinator.data or {}),
            "retries": self.coordinator.last_retries,
            "errors": self.coordinator.last_errors,
            "full_interval_s": self.coordinator.full_interval,
            "last_full_ms": self.coordinator.last_full_ms,
            "last_full_regs": self.coordinator.last_full_regs,
            "last_full_errors": self.coordinator.last_full_errors,
            "seconds_since_full": full_age,
            "seconds_until_full": None if until is None else round(until, 1),
            "force_full_pending": self.coordinator.force_full_pending,
            "last_poll_at": (
                self.coordinator.last_poll_at.isoformat()
                if self.coordinator.last_poll_at
                else None
            ),
            "last_poll_kind": self.coordinator.last_poll_kind,
        }


class SprsunLiveLogSensor(CoordinatorEntity[SprsunCoordinator], SensorEntity):
    """Expose circular live-log size + a short UI tail (full buffer via dump service)."""

    _attr_name = "SPRSUN Live log"
    _attr_unique_id = "sprsun_live_log"
    _attr_icon = "mdi:text-box-outline"
    _attr_native_unit_of_measurement = "lines"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    # Once the ring is full, size stays at capacity — force refresh so `tail` moves.
    _attr_force_update = True

    @property
    def native_value(self):
        return self.coordinator.live_log.size

    @property
    def extra_state_attributes(self):
        log = self.coordinator.live_log
        lines = log.tail(LIVE_LOG_UI_LINES)
        return {
            "capacity": log.capacity,
            "ui_lines": LIVE_LOG_UI_LINES,
            "generation": log.generation,
            "lines": lines,
            "tail": "\n".join(lines),
            "last": lines[-1] if lines else None,
        }
