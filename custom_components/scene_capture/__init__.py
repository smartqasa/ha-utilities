import logging
from homeassistant.core import HomeAssistant, ServiceCall

DOMAIN = "scene_capture"
ACTION_CAPTURE = "capture"

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Initialize Scene Capture integration."""

    async def handle_capture(call: ServiceCall) -> None:
        """Handle action call and log entity_id using the new target standard."""
        _LOGGER.info("Scene Capture: Action called")

        if not call.target:
            _LOGGER.error("Scene Capture: No target provided in action call.")
            return

        entity_ids = call.target.get("entity_id", [])

        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]  # Ensure it's a list

        if not entity_ids:
            _LOGGER.error("Scene Capture: No valid entity_id provided in target.")
            return

        for entity_id in entity_ids:
            _LOGGER.info(f"Scene Capture: Received entity_id: {entity_id}")

    hass.services.async_register(DOMAIN, ACTION_CAPTURE, handle_capture)
    _LOGGER.info("Scene Capture: Action registered successfully")
    return True
