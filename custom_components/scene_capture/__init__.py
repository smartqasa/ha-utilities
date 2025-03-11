import aiofiles
import asyncio
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
import logging
import os
import voluptuous as vol
import yaml

DOMAIN = "scene_capture"
SERVICE = "capture"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional("enabled", default=True): cv.boolean
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    
    async def handle_capture(call: ServiceCall) -> None:
        entity_id = call.data.get("entity_id")

        _LOGGER.debug(f"Scene Capture: handle_capture was called with entity_id: {call.data}")      

        if isinstance(entity_id, list):
            entity_id = entity_id[0]
        elif not isinstance(entity_id, str):
            _LOGGER.error(f"Scene Capture: Invalid entity_id type, expected string but got {type(entity_id)}")
            return
        
        if not entity_id.startswith("scene."):
            _LOGGER.error(f"Scene Capture: Invalid entity_id {entity_id}, must start with 'scene.'")
            return
        
        _LOGGER.debug(f"Scene Capture: handle_capture was called with entity_id: {entity_id}")

    hass.services.async_register(DOMAIN, SERVICE, handle_capture)
    _LOGGER.info("Scene Capture: Service registered as scene_capture.capture")

    return True

