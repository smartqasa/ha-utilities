import aiofiles
import asyncio
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
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

        # Retry logic for state retrieval
        max_attempts = 3
        total_delay = 0
        delay = 0.5
        state = None

        for attempt in range(max_attempts):
            state = await hass.async_add_executor_job(hass.states.get, entity_id)
            if state and state.state is not None:
                break
            total_delay += delay
            if total_delay >= 3:
                _LOGGER.error(f"Scene Capture: Entity {entity_id} did not load within 3 seconds, stopping retries.")
                return
            _LOGGER.warning(f"Scene Capture: Entity {entity_id} not available, retrying ({attempt + 1}/{max_attempts}) in {delay:.1f}s...")
            await asyncio.sleep(delay)

        if not state:
            _LOGGER.error(f"Scene Capture: Entity {entity_id} does not exist or is not loaded after {max_attempts} attempts (total {total_delay:.1f}s)")
            return

        await capture_scene_states(hass, entity_id, scene_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE,
        handle_capture,
        schema=SERVICE_SCHEMA,
    )
    _LOGGER.info("Scene Capture: Service registered successfully")
    return True

async def capture_scene_states(hass: HomeAssistant, entity_id: str, scene_id: str) -> None:
    """Capture current entity states into the scene and persist to scenes.yaml."""
    _LOGGER.debug(f"Scene Capture: Capturing scene {entity_id} with scene_id {scene_id}")

    scenes_file = os.path.join(hass.config.config_dir, "scenes.yaml")

    # Load scenes.yaml
    try:
        async with aiofiles.open(scenes_file, "r", encoding="utf-8") as f:
            content = await f.read()
            scenes_config = yaml.safe_load(content) or []
            if not isinstance(scenes_config, list):
                raise ValueError("scenes.yaml does not contain a list of scenes")

            scene_ids = set()
            for scene in scenes_config:
                if not isinstance(scene, dict) or "id" not in scene or "entities" not in scene:
                    raise ValueError("Each scene must be a dict with 'id' and 'entities' keys")
                if scene["id"] in scene_ids:
                    raise ValueError(f"Duplicate scene ID detected: {scene['id']}")
                scene_ids.add(scene["id"])
    except FileNotFoundError:
        _LOGGER.warning(f"Scene Capture: scenes.yaml not found, creating a new one.")
        scenes_config = []
    except Exception as e:
        _LOGGER.error(f"Scene Capture: Failed to load scenes.yaml: {str(e)}")
        return

    # Find the target scene by scene_id
    target_scene = next((s for s in scenes_config if s.get("id") == scene_id), None)
    if not target_scene:
        _LOGGER.error(f"Scene Capture: Scene {scene_id} not found in scenes.yaml")
        return

    updated_entities = {}
    for entity in target_scene.get("entities", {}):
        state = await hass.async_add_executor_job(hass.states.get, entity)
        if state:
            updated_entities[entity] = {"state": state.state}
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