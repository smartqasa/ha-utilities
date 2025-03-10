import logging
from homeassistant.core import HomeAssistant, ServiceCall

DOMAIN = "scene_capture"
ACTION_CAPTURE = "capture"

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async def handle_capture(call: ServiceCall) -> None:
        """Handle action call and ensure entity_id is always a string."""
        entity_id = call.data.get("entity_id")

        if isinstance(entity_id, list):  # If it's a list, take the first item
            entity_id = entity_id[0]
        elif not isinstance(entity_id, str):  # If it's not a string or list, it's invalid
            _LOGGER.error("Scene Capture: Invalid entity_id provided: %s", entity_id)
            return

        _LOGGER.info("Scene Capture: handle_capture was called with entity_id: %s", entity_id)

    hass.services.async_register(DOMAIN, ACTION_CAPTURE, handle_capture)
    _LOGGER.info("Scene Capture: Service registered as scene_capture.capture")

    return True
