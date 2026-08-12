"""Unit mode select — P06 holding register 54."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ADDR_MODE, DOMAIN, MODE_OPTIONS
from .coordinator import SprsunCoordinator

_INV = {v: k for k, v in MODE_OPTIONS.items()}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    coordinator: SprsunCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([SprsunModeSelect(coordinator)])


class SprsunModeSelect(CoordinatorEntity[SprsunCoordinator], SelectEntity):
    _attr_name = "SPRSUN Mode"
    _attr_unique_id = "sprsun_mode_select"
    _attr_options = list(MODE_OPTIONS.values())

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data or {}
        if ADDR_MODE not in data:
            return None
        return MODE_OPTIONS.get(int(data[ADDR_MODE]))

    async def async_select_option(self, option: str) -> None:
        if option not in _INV:
            raise ValueError(option)
        await self.coordinator.async_write_register(ADDR_MODE, _INV[option])
