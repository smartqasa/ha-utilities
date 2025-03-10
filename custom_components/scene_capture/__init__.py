import logging
from homeassistant.core import HomeAssistant, ServiceCall

DOMAIN = "scene_capture"
ACTION_CAPTURE = "capture"

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Initialize Scene Capture integration."""
    _LOGGER.debug("Scene Capture: async_setup called with config: %s", config)
    
    async def handle_capture(call: ServiceCall) -> None:
        """Log the full action call data, including entity_id."""
        _LOGGER.debug("Scene Capture: handle_capture called with data: %s, target: %s", call.data, call.target)
        _LOGGER.info("Scene Capture: Received call data: %s", call.data)

    hass.services.async_register(DOMAIN, ACTION_CAPTURE, handle_capture)
    _LOGGER.info("Scene Capture: Action registered successfully")
    return True