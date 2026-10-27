"""SPRSUN CG248075 Home Assistant integration (block-read Modbus TCP)."""
from __future__ import annotations

import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from .const import (
    ADDR_MODE,
    ADDR_POWER_MARKER,
    CONF_FULL_INTERVAL,
    CONF_FULL_WAIT_MS,
    CONF_MAX_BLOCK,
    CONF_MESSAGE_WAIT_MS,
    CONF_REGISTER_LIMIT,
    CONF_SLAVE,
    DEFAULT_FULL_INTERVAL,
    DEFAULT_FULL_WAIT_MS,
    DEFAULT_MAX_BLOCK,
    DEFAULT_MESSAGE_WAIT_MS,
    DEFAULT_PORT,
    DEFAULT_REGISTER_LIMIT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DOMAIN,
    MODE_OPTIONS,
)
from .coordinator import SprsunCoordinator
from .http_api import async_handle_download_live_log, async_setup_http
from .register_map import load_registers, registers_for_limit

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_SLAVE, default=DEFAULT_SLAVE): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=247)
                ),
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=3, max=3600)
                ),
                vol.Optional(CONF_FULL_INTERVAL, default=DEFAULT_FULL_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=10, max=3600)
                ),
                vol.Optional(CONF_MESSAGE_WAIT_MS, default=DEFAULT_MESSAGE_WAIT_MS): vol.All(
                    vol.Coerce(int), vol.Range(min=50, max=2000)
                ),
                vol.Optional(CONF_FULL_WAIT_MS, default=DEFAULT_FULL_WAIT_MS): vol.All(
                    vol.Coerce(int), vol.Range(min=50, max=2000)
                ),
                vol.Optional(CONF_MAX_BLOCK, default=DEFAULT_MAX_BLOCK): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=125)
                ),
                vol.Optional(CONF_REGISTER_LIMIT, default=DEFAULT_REGISTER_LIMIT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=413)
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    conf = config.get(DOMAIN)
    if conf is None:
        return True

    all_regs = await hass.async_add_executor_job(load_registers)
    limit = conf[CONF_REGISTER_LIMIT]
    registers = registers_for_limit(all_regs, limit)
    _LOGGER.info(
        "SPRSUN setup: %s registers (limit=%s) light_every=%ss full_every=%ss",
        len(registers),
        limit,
        conf[CONF_SCAN_INTERVAL],
        conf[CONF_FULL_INTERVAL],
    )

    coordinator = SprsunCoordinator(
        hass,
        host=conf[CONF_HOST],
        port=conf[CONF_PORT],
        slave=conf[CONF_SLAVE],
        registers=registers,
        scan_interval=conf[CONF_SCAN_INTERVAL],
        message_wait_ms=conf[CONF_MESSAGE_WAIT_MS],
        max_block=conf[CONF_MAX_BLOCK],
        full_interval=conf[CONF_FULL_INTERVAL],
        full_wait_ms=conf[CONF_FULL_WAIT_MS],
    )
    # Never abort setup because the gateway is unreachable at boot (HA starting
    # before the EW11 has a lease, a switch reboot, a moved DHCP address...).
    # If setup raised, HA creates no entities at all and only a restart brings
    # them back — that is exactly what happened after the 2026-10-23 reboot.
    # Instead: create the entities unavailable and let the coordinator retry
    # every scan_interval until the gateway answers again.
    try:
        await coordinator.async_connect()
        await coordinator.async_refresh()
        if coordinator.last_update_success is False and coordinator.last_exception:
            _LOGGER.warning(
                "Initial SPRSUN poll failed: %s — retrying every %ss",
                coordinator.last_exception,
                conf[CONF_SCAN_INTERVAL],
            )
    except Exception as exc:  # noqa: BLE001 - UpdateFailed, OSError, pymodbus
        # Mark the very first cycle failed so entities start "unavailable"
        # rather than showing a half-built blank state until the next poll.
        set_error = getattr(coordinator, "async_set_update_error", None)
        if set_error is not None:
            set_error(exc)
        _LOGGER.warning(
            "SPRSUN gateway %s:%s unreachable at startup (%s) — entities created "
            "unavailable, retrying every %ss",
            conf[CONF_HOST],
            conf[CONF_PORT],
            exc,
            conf[CONF_SCAN_INTERVAL],
        )

    hass.data[DOMAIN] = {
        "coordinator": coordinator,
        "registers": registers,
        "config": conf,
    }

    for platform in ("sensor", "binary_sensor", "switch", "select", "number", "button"):
        hass.async_create_task(async_load_platform(hass, platform, DOMAIN, {}, config))

    async def handle_write_register(call: ServiceCall) -> None:
        await coordinator.async_write_register(int(call.data["address"]), int(call.data["value"]))

    async def handle_set_mode(call: ServiceCall) -> None:
        mode = call.data["mode"]
        if isinstance(mode, str):
            inv = {v: k for k, v in MODE_OPTIONS.items()}
            if mode not in inv:
                raise ValueError(f"Unknown mode {mode}")
            raw = inv[mode]
        else:
            raw = int(mode)
        await coordinator.async_write_register(ADDR_MODE, raw)

    async def handle_set_power(call: ServiceCall) -> None:
        on = bool(call.data["on"])
        data = coordinator.data or {}
        current = int(data.get(ADDR_POWER_MARKER, 0))
        new = (current | 0x0001) if on else (current & ~0x0001)
        await coordinator.async_write_register(ADDR_POWER_MARKER, new & 0xFFFF)

    async def handle_refresh_full(call: ServiceCall) -> None:
        await coordinator.async_refresh_full()

    async def handle_dump_live_log(call: ServiceCall) -> None:
        filename = str(call.data.get("filename") or "sprsun_live.log")
        # Prevent path traversal — basename only under config dir.
        filename = filename.replace("\\", "/").split("/")[-1] or "sprsun_live.log"
        path = hass.config.path(filename)

        def _write() -> int:
            text = coordinator.live_log.dump()
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
                if text and not text.endswith("\n"):
                    fh.write("\n")
            return coordinator.live_log.size

        n = await hass.async_add_executor_job(_write)
        coordinator.live_log.info(f"dumped {n} lines → {filename}")
        await coordinator.async_request_refresh()

    async def handle_clear_live_log(call: ServiceCall) -> None:
        coordinator.live_log.clear()
        coordinator.live_log.info("live log cleared")
        await coordinator.async_request_refresh()

    async def handle_download_live_log(call: ServiceCall) -> None:
        await async_handle_download_live_log(hass, call)

    hass.services.async_register(DOMAIN, "write_register", handle_write_register)
    hass.services.async_register(DOMAIN, "set_mode", handle_set_mode)
    hass.services.async_register(DOMAIN, "set_power", handle_set_power)
    hass.services.async_register(DOMAIN, "refresh_full", handle_refresh_full)
    hass.services.async_register(DOMAIN, "dump_live_log", handle_dump_live_log)
    hass.services.async_register(DOMAIN, "download_live_log", handle_download_live_log)
    hass.services.async_register(DOMAIN, "clear_live_log", handle_clear_live_log)

    try:
        await async_setup_http(hass)
    except Exception:  # noqa: BLE001
        _LOGGER.exception(
            "SPRSUN HTTP download helpers failed; Modbus entities still available"
        )

    return True
