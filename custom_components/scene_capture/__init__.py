import aiofiles
import asyncio
from homeassistant.core import HomeAssistant, ServiceCall
import logging
import os
import voluptuous as vol
import yaml

DOMAIN = "scene_capture"
SERVICE = "capture"

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

SERVICE_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async def handle_capture(call: ServiceCall) -> None:
        entity_id = call.data.get("entity_id")

        if isinstance(entity_id, list):
            entity_id = entity_id[0]
        elif not isinstance(entity_id, str):
            _LOGGER.error(f"Scene Capture: Invalid entity_id type, expected string but got {type(entity_id)}")
            return
        
        if not entity_id.startswith("scene."):
            _LOGGER.error(f"Scene Capture: Invalid entity_id {entity_id}, must start with 'scene.'")
            return
        
        _LOGGER.debug(f"Scene Capture: handle_capture was called with entity_id: {entity_id}")

    hass.services.async_register(DOMAIN, SERVICE, handle_capture)
    _LOGGER.info("Scene Capture: Service registered as scene_capture.capture")

    return True

async def capture_scene_states(hass: HomeAssistant, entity_id: str) -> None:
    """Capture current entity states into the scene and persist to scenes.yaml."""
    _LOGGER.debug(f"Scene Capture: Capturing scene {entity_id}")
    scenes_file = os.path.join(hass.config.config_dir, "scenes.yaml")

    try:
        async with aiofiles.open(scenes_file, "r", encoding="utf-8") as f:
            content = await f.read()
            try:
                scenes_config = yaml.safe_load(content) or []
                # ✅ Validate scenes.yaml structure
                if not isinstance(scenes_config, list):
                    raise ValueError("scenes.yaml must contain a list of scenes")

                scene_ids = set()
                for scene in scenes_config:
                    if not isinstance(scene, dict) or "id" not in scene or "entities" not in scene:
                        raise ValueError("Each scene must be a dict with 'id' and 'entities' keys")
                    # ✅ Check for duplicate scene IDs
                    if scene["id"] in scene_ids:
                        raise ValueError(f"Duplicate scene ID detected: {scene['id']}")
                    scene_ids.add(scene["id"])
            except yaml.YAMLError as yaml_error:
                _LOGGER.error(f"Scene Capture: YAML parsing error in scenes.yaml: {yaml_error}")
                return
            except ValueError as ve:
                _LOGGER.error(f"Scene Capture: Invalid structure in scenes.yaml: {str(ve)}")
                return
    except FileNotFoundError:
        _LOGGER.warning(f"Scene Capture: scenes.yaml not found, creating a new one.")
        scenes_config = []
    except Exception as e:
        _LOGGER.error(f"Scene Capture: Failed to load scenes.yaml: {str(e)}")
        return

    scene_id = entity_id.split(".", 1)[1]

    # ✅ Only allow one scene per service call
    target_scene = next((s for s in scenes_config if s.get("id") == scene_id), None)
    if not target_scene:
        _LOGGER.error(f"Scene Capture: Scene {scene_id} not found in scenes.yaml")
        return

    updated_entities = {}
    for entity in target_scene.get("entities", {}):
        # ✅ Use async method for non-blocking state retrieval
        state = await hass.async_add_executor_job(hass.states.get, entity)
        if state:
            updated_entities[entity] = {"state": state.state}
            # ✅ Dynamically capture all relevant state attributes, excluding metadata
            excluded_attrs = {"last_updated", "last_changed", "context", "entity_id"}
            attributes = state.attributes if isinstance(state.attributes, dict) else {}
            updated_entities[entity].update({
                attr: value for attr, value in attributes.items()
                if value is not None and attr not in excluded_attrs
            })

    target_scene["entities"] = updated_entities

    try:
        async with aiofiles.open(scenes_file, "w", encoding="utf-8") as f:
            await f.write(yaml.safe_dump(scenes_config, default_flow_style=False, allow_unicode=True, sort_keys=False))
        await hass.services.async_call("scene", "reload")
        _LOGGER.info(f"Scene Capture: Captured and persisted scene {scene_id}")
    except Exception as e:
        _LOGGER.error(f"Scene Capture: Failed to update scenes.yaml: {str(e)}")