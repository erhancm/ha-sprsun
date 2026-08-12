"""Power switch — RMW bit0 of parameter marker (addr 50)."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ADDR_POWER_MARKER, DOMAIN
from .coordinator import SprsunCoordinator


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    coordinator: SprsunCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([SprsunPowerSwitch(coordinator)])


class SprsunPowerSwitch(CoordinatorEntity[SprsunCoordinator], SwitchEntity):
    _attr_name = "SPRSUN Power"
    _attr_unique_id = "sprsun_power_switch"

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        if ADDR_POWER_MARKER not in data:
            return None
        return bool(data[ADDR_POWER_MARKER] & 0x0001)

    async def async_turn_on(self, **kwargs) -> None:
        data = self.coordinator.data or {}
        current = int(data.get(ADDR_POWER_MARKER, 0))
        await self.coordinator.async_write_register(ADDR_POWER_MARKER, (current | 0x0001) & 0xFFFF)

    async def async_turn_off(self, **kwargs) -> None:
        data = self.coordinator.data or {}
        current = int(data.get(ADDR_POWER_MARKER, 0))
        await self.coordinator.async_write_register(ADDR_POWER_MARKER, (current & ~0x0001) & 0xFFFF)
