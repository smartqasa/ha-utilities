import voluptuous as vol
from typing import Any, cast

from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_CONFIG_READ,
    SERVICE_CONFIG_WRITE,
)
from .config import read_sqconfig, write_sqconfig

# Workaround for outdated HA type hints:
SupportsResponse = Any


def register_config_services(hass: HomeAssistant):
    """Register config-related SmartQasa services."""

    async def handle_read(call: ServiceCall):
        return await read_sqconfig()

    async def handle_write(call: ServiceCall):
        return await write_sqconfig(
            channel=call.data["channel"],
            auto_update=call.data["auto_update"],
        )

    # READ SERVICE
    hass.services.async_register(
        DOMAIN,
        SERVICE_CONFIG_READ,
        handle_read,
        schema=vol.Schema({}),
        supports_response=cast(SupportsResponse, "only"),
    )

    # WRITE SERVICE
    hass.services.async_register(
        DOMAIN,
        SERVICE_CONFIG_WRITE,
        handle_write,
        schema=vol.Schema({
            vol.Required("channel"): cv.string,
            vol.Required("auto_update"): cv.boolean,
        }),
        supports_response=cast(SupportsResponse, "only"),
    )
