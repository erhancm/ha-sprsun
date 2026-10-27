"""DataUpdateCoordinator — dual-rate FC3 reads for CG248075 / EW11."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_FULL_INTERVAL,
    DEFAULT_FULL_WAIT_MS,
    DEFAULT_MODBUS_TIMEOUT,
    DOMAIN,
    LIGHT_ADDRS,
    LIVE_LOG_CAPACITY,
    LIVE_LOG_WATCH_BITS,
    MAX_BLOCK_RETRIES,
    MODBUS_CLIENT_RETRIES,
    MODBUS_RECONNECT_DELAY,
)
from .live_log import LiveLog
from .register_map import RegisterDef, pack_blocks

_LOGGER = logging.getLogger(__name__)


def _is_dead_bus_error(msg: str) -> bool:
    m = msg.lower()
    return (
        "closing connection" in m
        or "not connected" in m
        or "connection unexpectedly closed" in m
        or "no response received of the last requests" in m
    )


class SprsunCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """Poll EW11 with light overview often and full map less often."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
        port: int,
        slave: int,
        registers: list[RegisterDef],
        scan_interval: int,
        message_wait_ms: int,
        max_block: int,
        full_interval: int = DEFAULT_FULL_INTERVAL,
        full_wait_ms: int = DEFAULT_FULL_WAIT_MS,
    ) -> None:
        self.host = host
        self.port = port
        self.slave = slave
        self.registers = registers
        self.message_wait_s = message_wait_ms / 1000.0
        self.full_wait_s = full_wait_ms / 1000.0
        self.max_block = max_block
        self.full_interval = full_interval
        self.blocks = pack_blocks([r.addr for r in registers], max_block=max_block)
        # Overview + controls — always polled on the light path (matches PC panel).
        self.light_blocks = pack_blocks(sorted(LIGHT_ADDRS), max_block=max_block)
        self.last_refresh_ms: float | None = None
        self.last_retries = 0
        self.last_errors = 0
        self.last_kind: str = "full"
        self.last_full_ms: float | None = None
        self.last_full_regs: int = 0
        self.last_full_errors: int = 0
        self.last_full_at: float | None = None  # monotonic
        self.last_poll_at: datetime | None = None  # wall clock UTC
        self.last_poll_kind: str = "full"
        self.addr_polled_at: dict[int, datetime] = {}
        self._cache: dict[int, int] = {}
        self._next_full_at = 0.0  # monotonic; first update does a full map
        self._force_full = True  # first cycle + manual refresh_full service
        self._need_prime = True
        self._client: Any = None
        self.live_log = LiveLog(LIVE_LOG_CAPACITY)
        self._watch_prev: dict[tuple[int, int], bool | None] = {
            (addr, bit): None for addr, bit, _ in LIVE_LOG_WATCH_BITS
        }
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.live_log.info(
            f"coordinator start host={host}:{port} slave={slave} "
            f"regs={len(registers)} light_blocks={len(self.light_blocks)} "
            f"full_blocks={len(self.blocks)} capacity={LIVE_LOG_CAPACITY}"
        )

    def request_full_refresh(self) -> None:
        """Force the next coordinator update to run a full map sweep."""
        self._force_full = True
        self._next_full_at = 0.0
        _LOGGER.info("SPRSUN full refresh requested")
        self.live_log.info("full refresh requested")

    @property
    def force_full_pending(self) -> bool:
        return self._force_full

    @property
    def seconds_until_full(self) -> float | None:
        if self._next_full_at <= 0:
            return 0.0
        return max(0.0, self._next_full_at - time.monotonic())

    def _log_watch_edges(self, values: dict[int, int]) -> None:
        for addr, bit, label in LIVE_LOG_WATCH_BITS:
            if addr not in values:
                continue
            on = bool(values[addr] & (1 << bit))
            prev = self._watch_prev[(addr, bit)]
            self._watch_prev[(addr, bit)] = on
            if prev is None or prev == on:
                continue
            self.live_log.info(f"{label} {'ON' if on else 'OFF'}")

    async def async_connect(self) -> None:
        await self.hass.async_add_executor_job(self._connect_sync)

    def _connect_sync(self) -> None:
        from pymodbus.client import ModbusTcpClient

        if self._client:
            try:
                self._client.close()
            except Exception:  # noqa: BLE001
                pass
            self._client = None

        self._client = ModbusTcpClient(
            self.host,
            port=self.port,
            timeout=DEFAULT_MODBUS_TIMEOUT,
            retries=MODBUS_CLIENT_RETRIES,
            reconnect_delay=MODBUS_RECONNECT_DELAY,
        )
        if not self._client.connect():
            self._client = None
            self.live_log.error(f"connect failed {self.host}:{self.port}")
            raise UpdateFailed(f"Cannot connect to {self.host}:{self.port}")
        self._need_prime = True
        self.live_log.info(f"connected {self.host}:{self.port}")

    async def _async_update_data(self) -> dict[int, int]:
        try:
            return await self.hass.async_add_executor_job(self._update_sync)
        except UpdateFailed as exc:
            self.live_log.error(f"update failed: {exc}")
            raise
        except Exception as exc:  # noqa: BLE001
            self.live_log.error(f"update failed: {exc}")
            raise UpdateFailed(str(exc)) from exc

    def _read_block(self, start: int, count: int) -> list[int]:
        assert self._client is not None
        rr = self._client.read_holding_registers(
            address=start, count=count, device_id=self.slave
        )
        if rr.isError():
            raise RuntimeError(str(rr))
        regs = getattr(rr, "registers", None) or []
        if len(regs) != count:
            raise RuntimeError(f"bad len want={count} got={len(regs)}")
        return [int(x) & 0xFFFF for x in regs]

    def _refresh_blocks(
        self,
        blocks: list[tuple[int, int]],
        *,
        message_wait_s: float,
        prime: bool,
    ) -> tuple[dict[int, int], int, int]:
        """Return (values, retries, errors). Reconnects before soft-retry."""
        values: dict[int, int] = {}
        retries = 0
        errors = 0
        abort_rest = False

        if prime:
            try:
                self._read_block(14, 1)
            except Exception as exc:  # noqa: BLE001
                _LOGGER.debug("prime read failed: %s", exc)
                self.live_log.warn(f"prime read failed: {exc}")
                try:
                    self._connect_sync()
                except UpdateFailed:
                    abort_rest = True
            time.sleep(message_wait_s)

        for start, count in blocks:
            if abort_rest:
                errors += 1
                _LOGGER.warning("block %s+%s skipped after bus close", start, count)
                self.live_log.warn(f"block {start}+{count} skipped after bus close")
                continue
            regs: list[int] | None = None
            last_err = ""
            for attempt in range(MAX_BLOCK_RETRIES + 1):
                try:
                    regs = self._read_block(start, count)
                    break
                except Exception as exc:  # noqa: BLE001
                    last_err = str(exc)
                    regs = None
                    retries += 1
                    if attempt >= MAX_BLOCK_RETRIES:
                        break
                    try:
                        self._connect_sync()
                    except UpdateFailed as reconnect_exc:
                        last_err = str(reconnect_exc)
                        abort_rest = True
                        break
                    time.sleep(message_wait_s + 0.15 * attempt)
            if regs is None:
                errors += 1
                _LOGGER.warning("block %s+%s failed: %s", start, count, last_err)
                self.live_log.warn(f"block {start}+{count} failed: {last_err}")
                if _is_dead_bus_error(last_err):
                    abort_rest = True
                    try:
                        self._connect_sync()
                    except UpdateFailed:
                        pass
            else:
                for offset, raw in enumerate(regs):
                    values[start + offset] = raw
            time.sleep(message_wait_s)

        return values, retries, errors

    def _update_sync(self) -> dict[int, int]:
        if self._client is None or not getattr(self._client, "connected", True):
            self._connect_sync()
        assert self._client is not None

        now = time.monotonic()
        do_full = self._force_full or now >= self._next_full_at
        self._force_full = False
        kind = "full" if do_full else "light"
        blocks = self.blocks if do_full else self.light_blocks
        wait_s = self.full_wait_s if do_full else self.message_wait_s

        if do_full:
            time.sleep(0.75)  # bus settle before heavy sweep (PC panel FULL_SETTLE)

        t0 = time.perf_counter()
        values, retries, errors = self._refresh_blocks(
            blocks,
            message_wait_s=wait_s,
            prime=self._need_prime,
        )
        self._need_prime = False
        duration_ms = (time.perf_counter() - t0) * 1000.0

        self.last_refresh_ms = duration_ms
        self.last_retries = retries
        self.last_errors = errors
        self.last_kind = kind
        self.last_poll_kind = kind
        self.last_poll_at = datetime.now(timezone.utc)

        if values:
            self._cache.update(values)
            for addr in values:
                self.addr_polled_at[addr] = self.last_poll_at
            self._log_watch_edges(values)

        if do_full:
            self.last_full_ms = duration_ms
            self.last_full_regs = len(values)
            self.last_full_errors = errors
            self.last_full_at = time.monotonic()
            if errors == 0 and values:
                self._next_full_at = time.monotonic() + self.full_interval
                _LOGGER.info(
                    "SPRSUN full poll ok: %.0f ms regs=%s blocks=%s",
                    duration_ms,
                    len(values),
                    len(blocks),
                )
                self.live_log.info(
                    f"full ok {duration_ms:.0f}ms regs={len(values)} blocks={len(blocks)}"
                )
            else:
                # Retry sooner; keep forcing full until a clean sweep lands.
                self._next_full_at = time.monotonic() + min(10, self.full_interval)
                self._force_full = True
                _LOGGER.warning(
                    "SPRSUN full poll incomplete: %.0f ms regs=%s/%s errors=%s — will retry",
                    duration_ms,
                    len(values),
                    sum(c for _, c in blocks),
                    errors,
                )
                self.live_log.warn(
                    f"full incomplete {duration_ms:.0f}ms regs={len(values)}/"
                    f"{sum(c for _, c in blocks)} errors={errors} — retry"
                )
        elif not values and not self._cache:
            raise UpdateFailed(f"No registers read from EW11 ({kind})")

        if not do_full:
            if errors:
                _LOGGER.warning(
                    "SPRSUN light poll: %.0f ms regs=%s retries=%s errors=%s",
                    duration_ms,
                    len(values),
                    retries,
                    errors,
                )
                self.live_log.warn(
                    f"light {duration_ms:.0f}ms regs={len(values)} "
                    f"retries={retries} errors={errors}"
                )
            else:
                _LOGGER.debug(
                    "SPRSUN light poll: %.0f ms regs=%s blocks=%s",
                    duration_ms,
                    len(values),
                    len(blocks),
                )
                # Light polls are frequent — only log when retries happened.
                if retries:
                    self.live_log.info(
                        f"light {duration_ms:.0f}ms regs={len(values)} "
                        f"retries={retries} blocks={len(blocks)}"
                    )

        return dict(self._cache)

    async def async_refresh_full(self) -> dict[int, int]:
        """Force a full map sweep now (service / button)."""
        self.request_full_refresh()
        await self.async_request_refresh()
        return dict(self.data or {})

    async def async_write_register(self, address: int, value: int) -> None:
        await self.hass.async_add_executor_job(self._write_sync, address, value)
        await self.async_request_refresh()

    def _write_sync(self, address: int, value: int) -> None:
        if self._client is None:
            self._connect_sync()
        assert self._client is not None
        rr = self._client.write_register(address=address, value=value, device_id=self.slave)
        if rr.isError():
            # Soft reconnect once, then retry write.
            self._connect_sync()
            rr = self._client.write_register(
                address=address, value=value, device_id=self.slave
            )
            if rr.isError():
                self.live_log.error(f"write @{address}={value} failed: {rr}")
                raise UpdateFailed(f"Write @{address} failed: {rr}")
        self.live_log.info(f"write @{address}={value}")
        time.sleep(self.message_wait_s)
        # Force a light refresh path next; keep full schedule.

    async def async_close(self) -> None:
        def _close() -> None:
            if self._client:
                try:
                    self._client.close()
                except Exception:  # noqa: BLE001
                    pass
                self._client = None

        await self.hass.async_add_executor_job(_close)
        self.live_log.info("coordinator closed")
