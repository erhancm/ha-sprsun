"""Setpoint number entities — P04/P02/P01 packed lower-8 × 0.5 °C."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ADDR_SETPOINT_COOL,
    ADDR_SETPOINT_DHW,
    ADDR_SETPOINT_HEAT,
    DOMAIN,
)
from .coordinator import SprsunCoordinator
from .register_map import pack_setpoint_c, setpoint_c

_SPECS = (
    (ADDR_SETPOINT_HEAT, "SPRSUN Heating setpoint", 10, 55, "sprsun_setpoint_heat"),
    (ADDR_SETPOINT_COOL, "SPRSUN Cooling setpoint", 12, 30, "sprsun_setpoint_cool"),
    (ADDR_SETPOINT_DHW, "SPRSUN Hot water setpoint", 10, 55, "sprsun_setpoint_dhw"),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    coordinator: SprsunCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities(
        [
            SprsunSetpointNumber(coordinator, addr, name, lo, hi, uid)
            for addr, name, lo, hi, uid in _SPECS
        ]
    )


class SprsunSetpointNumber(CoordinatorEntity[SprsunCoordinator], NumberEntity):
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX
    _attr_native_step = 0.5

    def __init__(
        self,
        coordinator: SprsunCoordinator,
        addr: int,
        name: str,
        minimum: float,
        maximum: float,
        unique_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._addr = addr
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        if self._addr not in data:
            return None
        return setpoint_c(data[self._addr])

    async def async_set_native_value(self, value: float) -> None:
        data = self.coordinator.data or {}
        existing = int(data.get(self._addr, 0))
        packed = pack_setpoint_c(value, existing)
        await self.coordinator.async_write_register(self._addr, packed)
