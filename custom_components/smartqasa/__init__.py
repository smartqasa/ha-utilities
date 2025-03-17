import aiofiles
import asyncio
import logging
import os
import tempfile
import voluptuous as vol
import yaml
from enum import Enum
from homeassistant.core import HomeAssistant, ServiceCall
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

def make_serializable(data, path="root"):
    """Ensure data is converted into YAML-safe formats while maintaining logging and validation."""
    try:
        if isinstance(data, Enum):
            _LOGGER.debug(f"🔄 Converting Enum at {path}: {data} -> {data.value}")
            return data.value  # Convert Enum to its raw value
        
        if isinstance(data, tuple):
            _LOGGER.debug(f"🔄 Converting tuple at {path}: {data} -> {list(data)}")
            return list(data)  # Convert tuples to lists for YAML
        
        if isinstance(data, dict):
            return {str(k): make_serializable(v, path=f"{path}.{k}") for k, v in data.items()}
        
        if isinstance(data, list):
            return [make_serializable(item, path=f"{path}[{i}]") for i, item in enumerate(data)]
        
        if isinstance(data, (int, float, str, bool, type(None))):
            _LOGGER.debug(f"✅ Keeping {type(data).__name__} at {path}: {data}")
            return data  # Standard YAML-safe types
        
        # **Catch-all for unsupported types**
        _LOGGER.error(f"❌ Serialization error at {path}: Unsupported type {type(data)} ({data})")
        return str(data)  # Convert unknown objects to string
    
    except Exception as e:
        _LOGGER.error(f"❌ Error processing {path}: {e}")
        return f"ERROR: {str(e)}"

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

    async def handle_scene_get(call: ServiceCall) -> list[str]:
        """Handle the scene_get service call."""
        entity_id = call.data["entity_id"][0]
        scene_id, target_scene = await retrieve_scene(hass, entity_id)
        if not target_scene:
            return {f"Scene not found for entity {entity_id}"}

        entities = list(target_scene.get("entities", {}).keys())
        _LOGGER.info(f"SmartQasa: Retrieved {len(entities)} entities for scene {entity_id} (ID: {scene_id}): {entities}")
        return {"entities": entities}

    async def handle_scene_update(call: ServiceCall) -> None:
        """Handle the scene_update service call."""
        entity_id = call.data["entity_id"][0]
        scene_id, target_scene = await retrieve_scene(hass, entity_id)
        if not target_scene:
            _LOGGER.error(f"SmartQasa: Scene not found for entity {entity_id}")
            return

        await update_scene_states(hass, scene_id, target_scene)

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
        except FileNotFoundError:
            _LOGGER.warning(f"SmartQasa: scenes.yaml not found, creating a new one.")
            scenes_config = []
        except Exception as e:
            _LOGGER.error(f"SmartQasa: Failed to load scenes.yaml: {str(e)}")
            return

        updated_entities = target_scene.get("entities", {}).copy()
        for entity, state in hass.states.async_all():
            _LOGGER.debug(f"🔍 Processing entity `{entity}` with attributes: {state.attributes}")
            updated_entities[entity] = make_serializable(state.attributes)

        target_scene["entities"] = updated_entities
        scene_data_serializable = make_serializable(scenes_config)

        _LOGGER.debug(f"📌 Serialized scene data before saving:\n{scene_data_serializable}")

        try:
            yaml_content = yaml.safe_dump(scene_data_serializable, default_flow_style=False, allow_unicode=True, sort_keys=False)
            async with aiofiles.open(scenes_file, "w", encoding="utf-8") as f:
                await f.write(yaml_content)
            await hass.services.async_call("scene", "reload")
            _LOGGER.info(f"✅ SmartQasa: Successfully updated and persisted scene {scene_id}")
        except Exception as e:
            _LOGGER.error(f"❌ SmartQasa: Failed to update scenes.yaml: {str(e)}")
