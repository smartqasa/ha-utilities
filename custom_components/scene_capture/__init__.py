import logging
from homeassistant.core import HomeAssistant, ServiceCall

DOMAIN = "scene_capture"
ACTION_CAPTURE = "capture"

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async def handle_capture(call: ServiceCall) -> None:
        entity_id = call.target["entity_id"][0]
        _LOGGER.error("Scene Capture: handle_capture was called with data: %s", entity_id)

    hass.services.async_register(DOMAIN, ACTION_CAPTURE, handle_capture)
    _LOGGER.info("Scene Capture: Service registered as scene_capture.capture")

    return True

