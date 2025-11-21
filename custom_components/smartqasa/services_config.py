import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_CONFIG_READ,
    SERVICE_CONFIG_WRITE,
)
from .config import read_sqconfig, write_sqconfig


def register_config_services(hass: HomeAssistant):
    """Register config-related SmartQasa services."""

    async def handle_read(call: ServiceCall):
        return await read_sqconfig()

    async def handle_write(call: ServiceCall):
        return await write_sqconfig(
            channel=call.data["channel"],
            auto_update=call.data["auto_update"],
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CONFIG_READ,
        handle_read,
        schema=vol.Schema({}),
        supports_response="only",
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CONFIG_WRITE,
        handle_write,
        schema=vol.Schema({
            vol.Required("channel"): cv.string,
            vol.Required("auto_update"): cv.boolean,
        }),
        supports_response="only",
    )
