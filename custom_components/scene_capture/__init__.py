import aiofiles
import asyncio
from enum import Enum
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from asyncio import Lock
import logging
import os
import voluptuous as vol
import yaml

DOMAIN = "scene_capture"
SERVICE = "capture"

CAPTURE_LOCK = asyncio.Lock()

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

def convert_enums_to_strings(data):
    """Recursively convert Enum objects to their string values."""
    if isinstance(data, dict):
        return {k: convert_enums_to_strings(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_enums_to_strings(item) for item in data]
    elif isinstance(data, Enum):
        return data.value
    return data

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    conf = config.get(DOMAIN, {})
    if not conf.get("enabled", True):
        _LOGGER.info("Scene Capture: Integration disabled via configuration")
        return False

    _LOGGER.debug("Scene Capture: Starting async setup")

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
        
        # Get the scene_id from the entity attributes
        state = hass.states.get(entity_id)
        if not state or "id" not in state.attributes:
            _LOGGER.error(f"Scene Capture: No 'id' found in attributes for entity_id {entity_id}")
            return
        scene_id = state.attributes["id"]

        _LOGGER.debug(f"Scene Capture: handle_capture was called with entity_id: {entity_id}, scene_id: {scene_id}")

        await capture_scene_states(hass, scene_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE,
        handle_capture,
        schema=SERVICE_SCHEMA,
    )
    _LOGGER.info("Scene Capture: Service registered successfully")
    return True

async def capture_scene_states(hass: HomeAssistant, scene_id: str) -> None:
    """Capture current entity states into the scene and persist to scenes.yaml."""
    _LOGGER.debug(f"Scene Capture: Capturing scene with scene_id {scene_id}")

    scenes_file = os.path.join(hass.config.config_dir, "scenes.yaml")

    async with CAPTURE_LOCK:
        try:
            async with aiofiles.open(scenes_file, "r", encoding="utf-8") as f:
                content = await f.read()
                scenes_config = yaml.safe_load(content) or []
                if not isinstance(scenes_config, list):
                    raise ValueError("scenes.yaml does not contain a list of scenes")

                for scene in scenes_config:
                    if not isinstance(scene, dict) or "id" not in scene or "entities" not in scene:
                        raise ValueError("Each scene must be a dict with 'id' and 'entities' keys")
        except FileNotFoundError:
            _LOGGER.warning(f"Scene Capture: scenes.yaml not found, creating a new one.")
            scenes_config = []
        except Exception as e:
            _LOGGER.error(f"Scene Capture: Failed to load scenes.yaml: {str(e)}")
            return

        # Direct lookup using next with generator expression
        target_scene = next((scene for scene in scenes_config if scene["id"] == scene_id), None)
        if not target_scene:
            _LOGGER.error(f"Scene Capture: Scene {scene_id} not found in scenes.yaml")
            return

        updated_entities = {}
        for entity in target_scene.get("entities", {}):
            # Retry logic for each entity in the scene
            max_attempts = 3
            total_delay = 0
            delay = 0.5
            state = None

            for attempt in range(max_attempts):
                state = await hass.async_add_executor_job(hass.states.get, entity)
                if state and state.state is not None:
                    break
                total_delay += delay
                if total_delay >= 3:
                    _LOGGER.warning(f"Scene Capture: Entity {entity} did not load within 3 seconds, skipping.")
                    break
                _LOGGER.warning(f"Scene Capture: Entity {entity} not available, retrying ({attempt + 1}/{max_attempts}) in {delay:.1f}s...")
                await asyncio.sleep(delay)

            if state:
                # Copy the entire attributes block and add state
                attributes = state.attributes if isinstance(state.attributes, dict) else {}
                # Convert all Enum objects to strings recursively
                entity_data = convert_enums_to_strings(attributes)
                entity_data["state"] = state.state  # Add state at the same level
                updated_entities[entity] = entity_data

        target_scene["entities"] = updated_entities

        # Serialize and validate before writing
        try:
            yaml_content = yaml.safe_dump(scenes_config, default_flow_style=False, allow_unicode=True, sort_keys=False)
            if not yaml_content.strip():
                raise ValueError("Serialized YAML content is empty")
            async with aiofiles.open(scenes_file, "w", encoding="utf-8") as f:
                await f.write(yaml_content)
            await hass.services.async_call("scene", "reload")
            _LOGGER.info(f"Scene Capture: Captured and persisted scene {scene_id}")
        except Exception as e:
            _LOGGER.error(f"Scene Capture: Failed to update scenes.yaml: {str(e)}")
            return