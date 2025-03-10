import logging
from homeassistant.core import HomeAssistant, ServiceCall

DOMAIN = "scene_capture"
SERVICE_CAPTURE = "capture"

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Scene Capture integration."""
    
    _LOGGER.info("Scene Capture: Initializing...")  # ✅ Log when integration starts

    async def handle_capture(call: ServiceCall) -> None:
        """Log the entity ID when service is called."""
        _LOGGER.info("Scene Capture: Service called")  # ✅ Log when service is triggered
        entity_id = call.data.get("entity_id")

        if entity_id:
            _LOGGER.info(f"Scene Capture: Received entity_id: {entity_id}")
        else:
            _LOGGER.error("Scene Capture: No entity_id provided in service call.")

    hass.services.async_register(DOMAIN, SERVICE_CAPTURE, handle_capture)
    _LOGGER.info("Scene Capture: Service registered successfully")
    return True
