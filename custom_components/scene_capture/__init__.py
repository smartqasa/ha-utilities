import logging
from homeassistant.core import HomeAssistant, ServiceCall

DOMAIN = "scene_capture"
ACTION_CAPTURE = "capture"

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    _LOGGER.error("Scene Capture: TEST ERROR LOG - If you see this, logging works!")
    
    """Initialize Scene Capture integration."""

    async def handle_capture(call: ServiceCall) -> None:
        """Log the full action call data."""
        _LOGGER.debug("Scene Capture: handle_capture called with data: %s", call.data)

    hass.services.async_register(DOMAIN, ACTION_CAPTURE, handle_capture)
    _LOGGER.info("Scene Capture: Action registered successfully")
    return True
