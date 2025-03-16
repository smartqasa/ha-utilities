import aiofiles
import asyncio
from copy import deepcopy
from enum import Enum
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
import logging
import os
import tempfile
import voluptuous as vol
import yaml

"""
Home Assistant custom integration for recapturing the state and attributes of
the entities of a pre-existing scene.

This integration provides a service to capture the current states of entities
in a specified scene and persist them to scenes.yaml.

Usage example:
  # In a script or automation
  service: scene_capture.update
  target:
    entity_id: scene.living_room

Configuration example:
  # configuration.yaml
  scene_capture:
    enabled: true  # Optional, defaults to true
"""

DOMAIN = "scene_capture"
SERVICE_UPDATE = "update"

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

def make_serializable(data):
    """Convert data into YAML-safe formats."""
    if data is None:
        return None
    elif isinstance(data, dict):
        return {k: make_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [make_serializable(item) for item in data]
    elif isinstance(data, tuple):
        return [make_serializable(item) for item in data]
    elif isinstance(data, Enum):
        return data.value
    elif isinstance(data, (int, float, bool, str)):
        return data
    elif hasattr(data, 'value'):  # Handles HA enums like ColorMode, LightEntityFeature
        return data.value
    else:
        _LOGGER.warning(f"⚠️ Unexpected type {type(data)} with value {data}, converting to string.")
        return str(data)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Scene Capture integration.

    Args:
        hass: The HomeAssistant instance
        config: Configuration dictionary for the integration

    Returns:
        bool: True if setup was successful, False otherwise
    """
    conf = config.get(DOMAIN, {})
    if not conf.get("enabled", True):
        _LOGGER.info("Scene Capture: Integration disabled via configuration")
        return False

    async def handle_capture(call: ServiceCall) -> None:
        """Handle the scene capture service call.

        Args:
            call: The service call object containing the entity_id

        Captures the current states of entities in the specified scene
        and updates scenes.yaml accordingly.
        """
        entity_id = call.data.get("entity_id")

        if isinstance(entity_id, list):
            entity_id = entity_id[0]
        elif not isinstance(entity_id, str):
            _LOGGER.error(f"Scene Capture: Invalid entity_id type, expected string but got {type(entity_id)}")
            return
        
        if not entity_id.startswith("scene."):
            _LOGGER.error(f"Scene Capture: Invalid entity_id {entity_id}, must start with 'scene.'")
            return
        
        state = hass.states.get(entity_id)
        if not state or "id" not in state.attributes:
            _LOGGER.error(f"Scene Capture: No 'id' found in attributes for entity_id {entity_id}")
            return
        scene_id = state.attributes["id"]

        await capture_scene_states(hass, scene_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE,
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

        target_scene = next((scene for scene in scenes_config if scene["id"] == scene_id), None)
        if not target_scene:
            _LOGGER.error(f"Scene Capture: Scene {scene_id} not found in scenes.yaml")
            return

        updated_entities = target_scene.get("entities", {}).copy()

        for entity in target_scene.get("entities", {}):
            max_attempts = 3
            state = None

            for attempt in range(max_attempts):
                state = await hass.async_add_executor_job(hass.states.get, entity)
                if state and state.state is not None:
                    break
                
                delay = 0.25 * (2 ** attempt)
                if attempt == max_attempts - 1:
                    _LOGGER.warning(f"Scene Capture: Entity {entity} did not load after {max_attempts} attempts, skipping.")
                    break
                _LOGGER.warning(f"Scene Capture: Entity {entity} not available, retrying ({attempt + 1}/{max_attempts}) in {delay:.1f}s...")
                await asyncio.sleep(delay)

            if state:
                _LOGGER.debug(f"🔍 Processing entity `{entity}` with attributes: {state.attributes}")
                attributes = {
                    key: make_serializable(value)
                    for key, value in state.attributes.items()
                } if isinstance(state.attributes, dict) else {}
                attributes["state"] = str(state.state)
                updated_entities[entity] = attributes

        target_scene["entities"] = updated_entities

        temp_file = None  # Ensure temp_file is defined for cleanup
        try:
            yaml_content = yaml.safe_dump(scenes_config, default_flow_style=False, allow_unicode=True, sort_keys=False)
            if not yaml_content.strip():
                raise ValueError("Serialized YAML content is empty")
            
            # Create temp file in same directory as scenes.yaml
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', prefix='scenes_', suffix='.tmp', dir=hass.config.config_dir, delete=False) as temp_f:
                temp_file = temp_f.name  # Get the temp file path
            
            # Write asynchronously to temp file
            async with aiofiles.open(temp_file, "w", encoding="utf-8") as f:
                await f.write(yaml_content)
            
            # Atomic move to final location
            os.replace(temp_file, scenes_file)

            await hass.services.async_call("scene", "reload")
            _LOGGER.info(f"Scene Capture: Captured and persisted scene {scene_id} with {len(updated_entities)} entities")
        except Exception as e:
            _LOGGER.error(f"Scene Capture: Failed to update scenes.yaml: {str(e)}")
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
            return
