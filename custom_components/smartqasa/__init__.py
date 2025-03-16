import aiofiles
import asyncio
from copy import deepcopy
from enum import Enum
import logging
import os
import tempfile
import voluptuous as vol
import yaml

from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

"""
Home Assistant custom integration providing various smart home utilities.

This integration provides services to manage scenes:
- scene_update: Updates the states and attributes of a scene's entities in scenes.yaml.
- scene_get: Retrieves a list of entity IDs for a given scene entity.

Usage examples:
  # Get scene entity IDs
  service: smartqasa.scene_get
  target:
    entity_id: scene.living_room
  # OR
  service: smartqasa.scene_get
  data:
    entity_id: scene.living_room

  # Update scene states
  service: smartqasa.scene_update
  target:
    entity_id: scene.living_room
  # OR
  service: smartqasa.scene_update
  data:
    entity_id: scene.living_room

Configuration example:
  # configuration.yaml
  smartqasa:
    enabled: true  # Optional, defaults to true

Repository: https://github.com/smartqasa/ha-utilities
"""

DOMAIN = "smartqasa"
SERVICE_SCENE_GET = "scene_get"
SERVICE_SCENE_UPDATE = "scene_update"

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

SCENE_GET_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)
SCENE_UPDATE_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)

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
    elif hasattr(data, 'value'):
        return data.value
    else:
        _LOGGER.warning(f"⚠️ Unexpected type {type(data)} with value {data}, converting to string.")
        return str(data)

async def retrieve_scene(hass: HomeAssistant, entity_id: str) -> tuple[str | None, dict | None]:
    """Retrieve the scene_id and target scene from an entity_id."""
    if not isinstance(entity_id, str):
        _LOGGER.error(f"SmartQasa: Invalid entity_id type, expected string but got {type(entity_id)}")
        return None, None
    if not entity_id.startswith("scene."):
        _LOGGER.error(f"SmartQasa: Invalid entity_id {entity_id}, must start with 'scene.'")
        return None, None

    state = hass.states.get(entity_id)
    if not state or "id" not in state.attributes:
        _LOGGER.error(f"SmartQasa: No 'id' found in attributes for entity_id {entity_id}")
        return None, None
    scene_id = state.attributes["id"]

    scenes_file = os.path.join(hass.config.config_dir, "scenes.yaml")
    async with CAPTURE_LOCK:
        try:
            async with aiofiles.open(scenes_file, "r", encoding="utf-8") as f:
                content = await f.read()
                scenes_config = yaml.safe_load(content) or []
                if not isinstance(scenes_config, list):
                    raise ValueError("scenes.yaml does not contain a list of scenes")
        except FileNotFoundError:
            _LOGGER.error(f"SmartQasa: scenes.yaml not found")
            return scene_id, None
        except Exception as e:
            _LOGGER.error(f"SmartQasa: Failed to load scenes.yaml: {str(e)}")
            return scene_id, None

        target_scene = next((scene for scene in scenes_config if scene.get("id") == scene_id), None)
        if not target_scene:
            _LOGGER.error(f"SmartQasa: Scene ID {scene_id} not found in scenes.yaml for entity {entity_id}")
            return scene_id, None

        return scene_id, target_scene

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the SmartQasa integration."""
    conf = config.get(DOMAIN, {})
    if not conf.get("enabled", True):
        _LOGGER.info("SmartQasa: Integration disabled via configuration")
        return False

    async def handle_scene_get(call: ServiceCall) -> None:
        """Handle the scene_get service call."""
        _LOGGER.debug(f"SmartQasa: scene_get call.data: {call.data}")
        entity_id = call.data.get("entity_id")
        scene_id, target_scene = await retrieve_scene(hass, entity_id)
        if not target_scene:
            hass.bus.async_fire("smartqasa_scene_entities", {"scene_id": scene_id or "unknown", "entity_id": entity_id, "entities": [], "error": "Scene retrieval failed"})
            return

        entities = list(target_scene.get("entities", {}).keys())
        _LOGGER.info(f"SmartQasa: Retrieved {len(entities)} entities for scene {entity_id} (ID: {scene_id}): {entities}")
        hass.bus.async_fire("smartqasa_scene_entities", {"scene_id": scene_id, "entity_id": entity_id, "entities": entities})

    async def handle_scene_update(call: ServiceCall) -> None:
        """Handle the scene_update service call."""
        entity_id = call.data["entity_id"]
        scene_id, target_scene = await retrieve_scene(hass, entity_id)
        if not target_scene:
            return

        await update_scene_states(hass, scene_id, target_scene)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCENE_GET,
        handle_scene_get,
        schema=SCENE_GET_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SCENE_UPDATE,
        handle_scene_update,
        schema=SCENE_UPDATE_SCHEMA,
    )
    _LOGGER.info("SmartQasa: Services registered successfully")
    return True

async def update_scene_states(hass: HomeAssistant, scene_id: str, target_scene: dict) -> None:
    """Update current entity states into the scene and persist to scenes.yaml."""
    _LOGGER.debug(f"SmartQasa: Updating scene with scene_id {scene_id}")
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
            _LOGGER.warning(f"SmartQasa: scenes.yaml not found, creating a new one.")
            scenes_config = []
        except Exception as e:
            _LOGGER.error(f"SmartQasa: Failed to load scenes.yaml: {str(e)}")
            return

        # Update the target scene in the config
        for i, scene in enumerate(scenes_config):
            if scene["id"] == scene_id:
                scenes_config[i] = target_scene
                break

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
                    _LOGGER.warning(f"SmartQasa: Entity {entity} did not load after {max_attempts} attempts, skipping.")
                    break
                _LOGGER.warning(f"SmartQasa: Entity {entity} not available, retrying ({attempt + 1}/{max_attempts}) in {delay:.1f}s...")
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

        temp_file = None
        try:
            yaml_content = yaml.safe_dump(scenes_config, default_flow_style=False, allow_unicode=True, sort_keys=False)
            if not yaml_content.strip():
                raise ValueError("Serialized YAML content is empty")
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', prefix='scenes_', suffix='.tmp', dir=hass.config.config_dir, delete=False) as temp_f:
                temp_file = temp_f.name
            async with aiofiles.open(temp_file, "w", encoding="utf-8") as f:
                await f.write(yaml_content)
            os.replace(temp_file, scenes_file)
            await hass.services.async_call("scene", "reload")
            _LOGGER.info(f"SmartQasa: Updated and persisted scene {scene_id} with {len(updated_entities)} entities")
        except Exception as e:
            _LOGGER.error(f"SmartQasa: Failed to update scenes.yaml: {str(e)}")
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
            return