import logging
import os
import yaml
from homeassistant.core import HomeAssistant, ServiceCall, Config
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

DOMAIN = "scene_capture"
SERVICE_CAPTURE = "capture"

SERVICE_SCHEMA = vol.Schema({}, extra=vol.REMOVE_EXTRA)

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

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up the Scene Capture integration."""
    conf = config.get(DOMAIN, {})
    if not conf.get("enabled", True):
        _LOGGER.info("Scene Capture: Integration disabled via configuration")
        return False

    _LOGGER.debug("Scene Capture: Starting async setup")

    async def handle_capture(call: ServiceCall) -> None:
        """Handle the capture service call."""
        _LOGGER.debug(f"Scene Capture: Received service call data: {call.data}")

        # Extract entity_id from the new `target` format
        target_entities = call.target.get("entity_id", [])
        if not target_entities or not isinstance(target_entities, list):
            _LOGGER.error(f"Scene Capture: Invalid or missing entity_id in target, received: {call.data}")
            return

        entity_id = target_entities[0]  # Assuming only one scene is allowed
        _LOGGER.debug(f"Scene Capture: Handling capture for {entity_id}")

        if not entity_id.startswith("scene."):
            _LOGGER.error(f"Scene Capture: Invalid entity_id {entity_id}, must start with 'scene.'")
            return
        if not hass.states.get(entity_id):
            _LOGGER.error(f"Scene Capture: Entity {entity_id} does not exist or is not loaded")
            return

        await capture_scene_states(hass, entity_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_CAPTURE,
        handle_capture,
        schema=SERVICE_SCHEMA,
    )
    _LOGGER.info("Scene Capture: Service registered successfully")
    return True

async def capture_scene_states(hass: HomeAssistant, entity_id: str) -> None:
    """Capture current entity states into the scene and persist to scenes.yaml."""
    _LOGGER.debug(f"Scene Capture: Capturing scene {entity_id}")
    scenes_file = os.path.join(hass.config.config_dir, "scenes.yaml")

    try:
        with open(scenes_file, "r") as f:
            scenes_config = yaml.safe_load(f) or []
    except FileNotFoundError:
        _LOGGER.warning(f"Scene Capture: scenes.yaml not found, creating a new one.")
        scenes_config = []
    except Exception as e:
        _LOGGER.error(f"Scene Capture: Failed to load scenes.yaml: {str(e)}")
        return

    scene_id = entity_id.split(".", 1)[1]
    matching_scenes = [s for s in scenes_config if s.get("id") == scene_id]

    if not matching_scenes:
        _LOGGER.error(f"Scene Capture: Scene {scene_id} not found in scenes.yaml")
        return

    for target_scene in matching_scenes:
        updated_entities = {}
        for entity in target_scene.get("entities", {}):
            state = hass.states.get(entity)
            if state:
                updated_entities[entity] = {"state": state.state}
                for attr in ["brightness", "temperature", "rgb_color", "xy_color", "color_temp"]:
                    attr_value = state.attributes.get(attr)
                    if attr_value is not None:
                        updated_entities[entity][attr] = attr_value

        target_scene["entities"] = updated_entities

    try:
        with open(scenes_file, "w") as f:
            yaml.safe_dump(scenes_config, f, default_flow_style=False)

        await hass.async_block_till_done()  # Ensure file write completes
        await hass.services.async_call("scene", "reload")
        _LOGGER.info(f"Scene Capture: Captured and persisted scene {scene_id}")
    except Exception as e:
        _LOGGER.error(f"Scene Capture: Failed to update scenes.yaml: {str(e)}")
