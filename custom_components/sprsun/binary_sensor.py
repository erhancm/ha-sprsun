"""Binary sensors from CG248075 bitfield map (status / outputs / failures)."""
from __future__ import annotations

import re

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_CLASS_PROBLEM, DEVICE_CLASS_RUNNING, DOMAIN, LIGHT_ADDRS
from .coordinator import SprsunCoordinator
from .register_map import load_bitfields, slug


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    data = hass.data[DOMAIN]
    coordinator: SprsunCoordinator = data["coordinator"]
    active_addrs = {r.addr for r in data["registers"]}
    bitfields = await hass.async_add_executor_job(load_bitfields)
    entities: list[SprsunBitBinarySensor] = []
    for bf in bitfields:
        addr = int(bf["addr"])
        if addr not in active_addrs:
            continue
        for bit in bf.get("bits") or []:
            entities.append(
                SprsunBitBinarySensor(
                    coordinator,
                    addr=addr,
                    bit=int(bit["bit"]),
                    mask=int(bit["mask"]),
                    label=bit["label"],
                    register_name=bf.get("register_name", ""),
                )
            )
    async_add_entities(entities)


def _clean_label(label: str, bit: int) -> str:
    if bit == 0 and "OFF" in label and "ON" in label:
        label = re.sub(r"0-OFF.*", "Power ON", label, flags=re.I)
    if "：" in label or (":" in label and re.search(r"0-|1-", label)):
        label = re.split(r"[：:]", label)[0]
    return label.strip()


class SprsunBitBinarySensor(CoordinatorEntity[SprsunCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SprsunCoordinator,
        *,
        addr: int,
        bit: int,
        mask: int,
        label: str,
        register_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._addr = addr
        self._mask = mask
        clean = _clean_label(label, bit)
        self._attr_name = f"SPRSUN {clean}"
        self._attr_unique_id = f"sprsun_bit_{addr:04d}_{bit}_{slug(clean)}"
        self._attr_force_update = addr in LIGHT_ADDRS
        key = (addr, bit)
        if key in DEVICE_CLASS_RUNNING:
            self._attr_device_class = BinarySensorDeviceClass.RUNNING
        elif key in DEVICE_CLASS_PROBLEM:
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        if self._addr not in data:
            return None
        return bool(data[self._addr] & self._mask)

    @property
    def extra_state_attributes(self):
        polled = self.coordinator.addr_polled_at.get(self._addr)
        return {
            "register": self._addr,
            "poll_group": "light" if self._addr in LIGHT_ADDRS else "full",
            "last_polled": polled.isoformat() if polled else None,
        }