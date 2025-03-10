import logging
from homeassistant.core import HomeAssistant, ServiceCall, Config

DOMAIN = "scene_capture"
SERVICE_CAPTURE = "capture"

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up the Scene Capture integration."""
    _LOGGER.debug("Scene Capture: Starting async setup")

    async def handle_capture(call: ServiceCall) -> None:
        """Handle the capture service call and log the entity_id."""
        _LOGGER.debug(f"Scene Capture: Received service call data: {call.data}")
        _LOGGER.debug(f"Scene Capture: Received target: {call.target}")

        # Extract entity_id from call.target
        if not call.target or "entity_id" not in call.target:
            _LOGGER.error(f"Scene Capture: Missing entity_id in target, received: {call.target}")
            return

        entity_id = call.target["entity_id"]
        if not isinstance(entity_id, str):
            _LOGGER.error(f"Scene Capture: Invalid entity_id type, expected string but got {type(entity_id)}")
            return

        # Log the entity_id
        _LOGGER.info(f"Scene Capture: Logged entity_id: {entity_id}")

    # Register the service without a schema, letting services.yaml handle target
    hass.services.async_register(
        DOMAIN,
        SERVICE_CAPTURE,
        handle_capture,
    )
    _LOGGER.info("Scene Capture: Service registered successfully")
    return True