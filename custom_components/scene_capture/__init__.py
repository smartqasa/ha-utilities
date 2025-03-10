import logging
from homeassistant.core import HomeAssistant, ServiceCall

DOMAIN = "scene_capture"
ACTION_CAPTURE = "capture"

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async def handle_capture(call: ServiceCall) -> None:
        entity_id = call.data.get("entity_id")

        if isinstance(entity_id, list):
            entity_id = entity_id[0]
        elif not isinstance(entity_id, str):
            _LOGGER.error("Scene Capture: Invalid entity_id provided: %s", entity_id)
            return

        _LOGGER.debug("Scene Capture: handle_capture was called with entity_id: %s", entity_id)

    hass.services.async_register(DOMAIN, ACTION_CAPTURE, handle_capture)
    _LOGGER.info("Scene Capture: Service registered as scene_capture.capture")

    return True
