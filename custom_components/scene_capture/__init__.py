import logging
from homeassistant.core import HomeAssistant, ServiceCall

DOMAIN = "scene_capture"
ACTION_CAPTURE = "capture"

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Initialize Scene Capture integration."""
    _LOGGER.info("Scene Capture: Initializing setup.")

    async def handle_capture(call: ServiceCall) -> None:
        """Handle action call and log data."""
        _LOGGER.info("Scene Capture: handle_capture was called with data: %s", call.data)

    hass.services.async_register(DOMAIN, ACTION_CAPTURE, handle_capture)
    _LOGGER.info("Scene Capture: Service registered as scene_capture.capture")

    return True

