import aiofiles
import asyncio
from copy import deepcopy
from datetime import datetime
from enum import Enum
import logging
import os
import tempfile
import voluptuous as vol
from ruamel.yaml import YAML

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
SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): vol.All(cv.ensure_list, vol.Length(min=1, max=1), [cv.entity_id])
    },
)
_LOGGER = logging.getLogger(__name__)

# Configure ruamel.yaml
yaml = YAML()
yaml.allow_unicode = True
yaml.default_flow_style = False

# Custom representers for HA-specific types
def datetime_representer(dumper, data):
    """Serialize datetime objects as YAML timestamps."""
    return dumper.represent_scalar('tag:yaml.org,2002:timestamp', data.isoformat())

def enum_representer(dumper, data):
    """Serialize Enum objects as their string values."""
    return dumper.represent_scalar('tag:yaml.org,2002:str', str(data.value))

# Register representers
yaml.representer.add_representer(datetime, datetime_representer)
yaml.representer.add_representer(Enum, enum_representer)

async def retrieve_scene_id(hass: HomeAssistant, entity_id: str) -> str:
    """Retrieve the scene_id from an entity_id."""
    if not isinstance(entity_id, str):
        _LOGGER.error(f"SmartQasa: Invalid entity_id type, expected string but got {type(entity_id)}")
        return None
    
    if not entity_id.startswith("scene."):
        _LOGGER.error(f"SmartQasa: Invalid entity_id {entity_id}, must start with 'scene.'")
        return None

    state = hass.states.get(entity_id)
    if not state or "id" not in state.attributes:
        _LOGGER.error(f"SmartQasa: No 'id' found in attributes for entity_id {entity_id}")
        return None
    
    scene_id = state.attributes["id"]
    return scene_id

async def retrieve_scene_config(hass: HomeAssistant, scene_id: str) -> dict:
    """Retrieve the scene config from the scenes.yaml file."""
    scenes_file = os.path.join(hass.config.config_dir, "scenes.yaml")
    try:
        async with aiofiles.open(scenes_file, "r", encoding="utf-8") as f:
            content = await f.read()
            scenes_config = yaml.load(content) or []
            if not isinstance(scenes_config, list):
                raise ValueError("scenes.yaml does not contain a list of scenes")
    except FileNotFoundError:
        _LOGGER.error(f"SmartQasa: scenes.yaml not found")
        return None
    except Exception as e:
        _LOGGER.error(f"SmartQasa: Failed to load scenes.yaml: {str(e)}")
        return None

    scene_config = next((scene for scene in scenes_config if scene.get("id") == scene_id), None)
    if not scene_config:
        _LOGGER.error(f"SmartQasa: Scene ID {scene_id} not found in scenes.yaml")
        return None
    return scene_config

async def update_scene_states(hass: HomeAssistant, scene_id: str) -> None:
    """Update current entity states into the scene and persist to scenes.yaml."""
    _LOGGER.debug(f"SmartQasa: Updating scene with scene_id {scene_id}")

    scenes_file = os.path.join(hass.config.config_dir, "scenes.yaml")
    async with CAPTURE_LOCK:
        scene_config = await retrieve_scene_config(hass, scene_id)
        if not scene_config:
            _LOGGER.error(f"SmartQasa: Scene ID {scene_id} not found in scenes.yaml")
            return
        
        _LOGGER.debug(f"scenes_config contents: {scene_config}")
        return

        scene_entities = scene_config.get("entities", {}).copy()
        for entity in scene_config.get("entities", {}):
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
                # Directly use attributes, relying on ruamel.yaml to serialize
                attributes = dict(state.attributes) if isinstance(state.attributes, dict) else {}
                attributes["state"] = str(state.state)
                scene_entities[entity] = attributes

        scene_config["entities"] = scene_entities

        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', prefix='scenes_', suffix='.tmp', dir=hass.config.config_dir, delete=False) as temp_f:
                temp_file = temp_f.name
                yaml.dump(scene_config, temp_f)  # Dump directly to file
            os.replace(temp_file, scenes_file)
            await hass.services.async_call("scene", "reload")
            _LOGGER.info(f"SmartQasa: Updated and persisted scene {scene_id} with {len(scene_entities)} entities")
        except Exception as e:
            _LOGGER.error(f"SmartQasa: Failed to update scenes.yaml: {str(e)}")
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
            return

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the SmartQasa integration."""
    conf = config.get(DOMAIN, {})
    if not conf.get("enabled", True):
        _LOGGER.info("SmartQasa: Integration disabled via configuration")
        return False

    async def handle_scene_get(call: ServiceCall) -> dict:
        """Handle the scene_get service call to retrieve entity IDs for a given scene entity."""
        entity_id = call.data["entity_id"][0]
        scene_id = await retrieve_scene_id(hass, entity_id)
        if not scene_id:
            _LOGGER.error(f"SmartQasa: Failed to retrieve scene_id for entity {entity_id}")
            return {"error": f"Invalid or unrecognized scene entity: {entity_id}"}

        async with CAPTURE_LOCK:
            scene_config = await retrieve_scene_config(hass, scene_id)
            if not scene_config:
                _LOGGER.error(f"SmartQasa: Scene ID {scene_id} not found in scenes.yaml for entity {entity_id}")
                return {"error": f"Scene not found for entity {entity_id}"}

            entities = list(scene_config.get("entities", {}).keys())
            if not entities:
                _LOGGER.warning(f"SmartQasa: No entities found in scene {scene_id} for entity {entity_id}")
                return {"warning": f"No entities found in scene {entity_id}"}  
            
            return {"entities": entities}

    async def handle_scene_update(call: ServiceCall) -> None:
        """Handle the scene_update service call."""
        entity_id = call.data["entity_id"][0]
        scene_id = await retrieve_scene_id(hass, entity_id)
        if not scene_id:
            _LOGGER.error(f"SmartQasa: Scene not found for entity {entity_id}")
            return

        await update_scene_states(hass, scene_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCENE_GET,
        handle_scene_get,
        schema=SERVICE_SCHEMA,
        supports_response="only",
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SCENE_UPDATE,
        handle_scene_update,
        schema=SERVICE_SCHEMA,
    )
    _LOGGER.info("SmartQasa: Services registered successfully")
    return True