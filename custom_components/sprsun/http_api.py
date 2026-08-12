"""HTTP API for SPRSUN (browser download of the live log)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

from aiohttp import web
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.start import async_at_start

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_STATIC_URL = "/sprsun_static"
_JS_URL = f"{_STATIC_URL}/sprsun-download-log.js?v=0.2.7"
_API_PATH = "/api/sprsun/live_log"


class SprsunLiveLogView(HomeAssistantView):
    """Authenticated download of the in-memory live log."""

    url = _API_PATH
    name = "api:sprsun:live_log"
    requires_auth = True

    async def get(self, request: web.Request) -> web.StreamResponse:
        hass: HomeAssistant = request.app["hass"]
        data = hass.data.get(DOMAIN) or {}
        coordinator = data.get("coordinator")
        if coordinator is None:
            return web.Response(status=503, text="SPRSUN not ready")

        text = coordinator.live_log.dump()
        if text and not text.endswith("\n"):
            text += "\n"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sprsun_live_{stamp}.log"
        return web.Response(
            body=text.encode("utf-8"),
            headers={
                "Content-Type": "text/plain; charset=utf-8",
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )


async def async_prepare_download_link(hass: HomeAssistant) -> str:
    """Return a short-lived signed URL for the live-log download API."""
    from homeassistant.components.http.auth import async_sign_path

    return async_sign_path(hass, _API_PATH, timedelta(minutes=10))


async def async_handle_download_live_log(hass: HomeAssistant, call: ServiceCall) -> None:
    """Create a notification with a signed link that triggers a browser save."""
    data = hass.data.get(DOMAIN) or {}
    coordinator = data.get("coordinator")
    signed = await async_prepare_download_link(hass)
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": "SPRSUN live log",
            "message": (
                f"[Save log to your PC]({signed}) — link valid ~10 minutes."
            ),
            "notification_id": "sprsun_live_log_download",
        },
        blocking=False,
    )
    if coordinator is not None:
        coordinator.live_log.info("download link ready (see notification)")
        await coordinator.async_request_refresh()


async def async_setup_http(hass: HomeAssistant) -> None:
    """Register download API, static JS, and Lovelace module URL.

    Failures here must not prevent Modbus polling from starting.
    """
    www = Path(__file__).parent / "www"
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(_STATIC_URL, str(www), False)]
        )
    except RuntimeError:
        # Path already registered (reload / duplicate setup).
        _LOGGER.debug("SPRSUN static path already registered")
    except Exception:  # noqa: BLE001
        _LOGGER.exception("SPRSUN static path registration failed")

    try:
        hass.http.register_view(SprsunLiveLogView())
    except Exception:  # noqa: BLE001
        _LOGGER.exception("SPRSUN live log download API failed to register")
        return

    async def _register_frontend(_hass: HomeAssistant) -> None:
        try:
            from homeassistant.components.frontend import add_extra_js_url

            add_extra_js_url(hass, _JS_URL)
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "SPRSUN download card JS not registered (Save-to-PC custom card may be unavailable)"
            )

    async_at_start(hass, _register_frontend)
