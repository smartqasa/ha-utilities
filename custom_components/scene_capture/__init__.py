import logging
import os
import yaml
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

DOMAIN = "scene_capture"
SERVICE_CAPTURE = "capture"
SERVICE_SCHEMA = vol.Schema({
    vol.Required("scene_id"): cv.string
})

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Scene Capture integration."""
    _LOGGER.debug("Scene Capture: Starting async setup")

    async def handle_capture(call: ServiceCall) -> None:
        """Handle the capture service call."""
        scene_id = call.data["scene_id"]
        _LOGGER.debug(f"Scene Capture: Handling capture for {scene_id}")
        await capture_scene_states(hass, scene_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_CAPTURE,
        handle_capture,
        schema=SERVICE_SCHEMA,
    )
    _LOGGER.info("Scene Capture: Service registered successfully")
    return True

async def capture_scene_states(hass: HomeAssistant, scene_id: str) -> None:
    """Capture current entity states into the scene and persist to scenes.yaml."""
    _LOGGER.debug(f"Scene Capture: Capturing scene {scene_id}")
    scenes_file = os.path.join(hass.config.config_dir, "scenes.yaml")

    try:
        scenes_config = await hass.async_add_executor_job(
            lambda: yaml.safe_load(open(scenes_file, "r")) or []
        )
    except Exception as e:
        _LOGGER.error(f"Scene Capture: Failed to load scenes.yaml: {str(e)}")
        return

    target_scene = next((s for s in scenes_config if s.get("id") == scene_id), None)
    if not target_scene:
        _LOGGER.error(f"Scene Capture: Scene {scene_id} not found in scenes.yaml")
        return

    entities = target_scene.get("entities", {})
    if not entities:
        _LOGGER.error(f"Scene Capture: No entities in scene {scene_id}")
        return

    updated_entities = {}
    for entity_id in entities.keys():
        state = hass.states.get(entity_id)
        if state:
            updated_entities[entity_id] = {"state": state.state}
            for attr in state.attributes:
                if attr in ["brightness", "temperature", "rgb_color", "xy_color", "color_temp"]:
                    updated_entities[entity_id][attr] = state.attributes[attr]

    target_scene["entities"] = updated_entities

    try:
        await hass.async_add_executor_job(
            lambda: yaml.safe_dump(scenes_config, open(scenes_file, "w"), default_flow_style=False)
        )
        await hass.services.async_call("scene", "reload")
        _LOGGER.info(f"Scene Capture: Captured and persisted scene {scene_id}")
    except Exception as e:
        _LOGGER.error(f"Scene Capture: Failed to update scenes.yaml: {str(e)}")