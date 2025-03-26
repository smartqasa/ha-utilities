import aiofiles
import asyncio
from copy import deepcopy
from datetime import datetime
from enum import Enum
import logging
from typing import Optional
import os
import tempfile
import voluptuous as vol
from ruamel.yaml import YAML, YAMLError

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.components.light import ColorMode, LightEntityFeature
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.components.fan import FanEntityFeature
import homeassistant.helpers.config_validation as cv

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

yaml = YAML()
yaml.allow_unicode = True
yaml.default_flow_style = False

def datetime_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:timestamp', data.isoformat())

def enum_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', str(data.value))

def colormode_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data.value)

def entityfeature_representer(dumper, data):
    return dumper.represent_int(data)

yaml.representer.add_representer(datetime, datetime_representer)
yaml.representer.add_representer(Enum, enum_representer)
yaml.representer.add_representer(ColorMode, colormode_representer)
yaml.representer.add_representer(CoverEntityFeature, entityfeature_representer)
yaml.representer.add_representer(FanEntityFeature, entityfeature_representer)
yaml.representer.add_representer(LightEntityFeature, entityfeature_representer)

async def retrieve_scene_id(hass: HomeAssistant, entity_id: str) -> Optional[str]:
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
    
    return state.attributes["id"]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    conf = config.get(DOMAIN, {})
    if not conf.get("enabled", True):
        _LOGGER.info("SmartQasa: Integration disabled via configuration")
        return False

    async def handle_scene_get(call: ServiceCall) -> dict:
        entity_id = call.data["entity_id"][0]
        scene_id = await retrieve_scene_id(hass, entity_id)
        if not scene_id:
            _LOGGER.error(f"SmartQasa: Failed to retrieve scene_id for entity {entity_id}")
            return {"error": f"Invalid or unrecognized scene entity: {entity_id}"}

        scenes_file = os.path.join(hass.config.config_dir, "scenes.yaml")
        async with CAPTURE_LOCK:
            try:
                async with aiofiles.open(scenes_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                    scenes_config = yaml.load(content) or []
                    if not isinstance(scenes_config, list):
                        return {"error": "scenes.yaml does not contain a list of scenes"}
                    
                    scene_config = next((scene for scene in scenes_config if scene.get("id") == scene_id), None)
                    if not scene_config:
                        return {"error": f"Scene ID {scene_id} not found in scenes.yaml"}
                    
                    entities = list(scene_config.get("entities", {}).keys())
                    if not entities:
                        _LOGGER.warning(f"SmartQasa: No entities found in scene {scene_id} for entity {entity_id}")
                        return {"warning": f"No entities found in scene {entity_id}"}
                    
                    return {"entities": entities}
            except FileNotFoundError:
                _LOGGER.warning("SmartQasa: scenes.yaml not found, returning empty scene list")
                return {"error": "scenes.yaml not found"}
            except Exception as e:
                _LOGGER.error(f"SmartQasa: Failed to load scenes.yaml: {str(e)}")
                return {"error": f"Failed to load scenes.yaml: {str(e)}"}

    async def handle_scene_update(call: ServiceCall) -> dict:
        entity_id = call.data["entity_id"][0]
        scene_id = await retrieve_scene_id(hass, entity_id)
        if not scene_id:
            _LOGGER.error(f"SmartQasa: Scene not found for entity {entity_id}")
            return {"success": False, "message": f"Scene not found for entity {entity_id}"}

        scenes_file = os.path.join(hass.config.config_dir, "scenes.yaml")
        async with CAPTURE_LOCK:
            try:
                async with aiofiles.open(scenes_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                    scenes_config = yaml.load(content) or []
                    if not isinstance(scenes_config, list):
                        return {"success": False, "message": "scenes.yaml does not contain a list of scenes"}
                    
                    scene_config = next((scene for scene in scenes_config if scene.get("id") == scene_id), None)
                    if not scene_config:
                        return {"success": False, "message": f"Scene ID {scene_id} not found"}
            except FileNotFoundError:
                _LOGGER.warning("SmartQasa: scenes.yaml not found, returning empty scene list")
                return {"success": False, "message": "scenes.yaml not found"}
            except Exception as e:
                _LOGGER.error(f"SmartQasa: Failed to load scenes.yaml: {str(e)}")
                return {"success": False, "message": f"Failed to load scenes.yaml: {str(e)}"}

            scene_entities = scene_config.get("entities", {}).copy()
            for entidade in scene_entities:
                max_attempts = 3
                state = None
                for attempt in range(max_attempts):
                    state = await hass.async_add_executor_job(hass.states.get, entidade)
                    if state and state.state is not None:
                        break
                    delay = 0.2 * (2 ** attempt)
                    if attempt == max_attempts - 1:
                        _LOGGER.warning(f"SmartQasa: Entity {entidade} did not load after {max_attempts} attempts, retaining existing data.")
                        break
                    _LOGGER.warning(f"SmartQasa: Entity {entidade} not available, retrying ({attempt + 1}/{max_attempts}) in {delay:.1f}s...")
                    await asyncio.sleep(delay)

                if state:
                    _LOGGER.debug(f"SmartQasa: Processing entity {entidade} with state {state.state}")
                    attributes = dict(state.attributes) if isinstance(state.attributes, dict) else {}
                    _LOGGER.debug(f"SmartQasa: Original attributes for {entidade}: {attributes}")
                    
                    # Log each attribute before adding to scene_entities
                    for key, value in attributes.items():
                        _LOGGER.debug(f"SmartQasa: Entity {entidade} attribute {key}: value={value}, type={type(value)}")
                    
                    attributes["state"] = str(state.state)
                    scene_entities[entidade] = attributes

            scene_config["entities"] = scene_entities

            _LOGGER.debug(f"SmartQasa: Final scene_config before YAML dump: {scene_config}")
            
            temp_file = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', prefix='scenes_', suffix='.tmp', dir=hass.config.config_dir, delete=False) as temp_f:
                    temp_file = temp_f.name
                    yaml.dump(scenes_config, temp_f)
                os.replace(temp_file, scenes_file)
                await hass.services.async_call("scene", "reload")
                return {"success": True, "message": f"Scene {entity_id} ({scene_id}) updated successfully"}
            except YAMLError as e:
                _LOGGER.error(f"SmartQasa: YAML serialization failed - {e}")
                _LOGGER.debug(f"SmartQasa: Failed scene_config: {scene_config}")
                return {"success": False, "message": f"YAML serialization failed: {str(e)}"}
            except Exception as e:
                _LOGGER.error(f"SmartQasa: Failed to update scenes.yaml: {str(e)}")
                return {"success": False, "message": f"Failed to update scenes.yaml: {str(e)}"}
            finally:
                if temp_file and os.path.exists(temp_file):
                    os.remove(temp_file)

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
        supports_response="only",
    )
    _LOGGER.info("SmartQasa: Services registered successfully")
    return True