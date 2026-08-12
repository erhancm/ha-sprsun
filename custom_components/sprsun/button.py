"""Button platform — force a full Modbus map sweep."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SprsunCoordinator


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    coordinator: SprsunCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([SprsunRefreshFullButton(coordinator)])


class SprsunRefreshFullButton(CoordinatorEntity[SprsunCoordinator], ButtonEntity):
    _attr_name = "SPRSUN Refresh full map"
    _attr_unique_id = "sprsun_refresh_full_button"
    _attr_icon = "mdi:refresh"

    async def async_press(self) -> None:
        await self.coordinator.async_refresh_full()
