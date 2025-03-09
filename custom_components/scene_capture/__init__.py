import logging
import os
import yaml
import aiofiles  # Non-blocking file I/O
import asyncio  # For non-blocking sleep
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

DOMAIN = "scene_capture"
SERVICE_CAPTURE = "capture"

# ✅ Allow Home Assistant to handle `target` at the root level
SERVICE_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)

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

        # ✅ Extract entity_id correctly from call.target, NOT call.data
        if not call.target or "entity_id" not in call.target:
            _LOGGER.error(f"Scene Capture: Missing entity_id in target, received: {call.data}")
            return

        entity_id = call.target["entity_id"]
        if not isinstance(entity_id, str):
            _LOGGER.error(f"Scene Capture: Invalid entity_id type, expected string but got {type(entity_id)}")
            return

        _LOGGER.debug(f"Scene Capture: Handling capture for {entity_id}")

        if not entity_id.startswith("scene."):
            _LOGGER.error(f"Scene Capture: Invalid entity_id {entity_id}, must start with 'scene.'")
            return

        # ✅ Use async method for non-blocking state retrieval with retry
        max_attempts = 3
        total_delay = 0
        delay = 0.5  # ✅ Constant delay of 0.5s per attempt
        state = None

        for attempt in range(max_attempts):
            state = await hass.async_add_executor_job(hass.states.get, entity_id)
            if state and state.state is not None:  # ✅ Validate state is usable
                break
            
            total_delay += delay
            if total_delay >= 3:  # ✅ Immediately stop retrying when 3s is reached
                _LOGGER.error(f"Scene Capture: Entity {entity_id} did not load within 3 seconds, stopping retries.")
                return
            
            _LOGGER.warning(f"Scene Capture: Entity {entity_id} not available, retrying ({attempt + 1}/{max_attempts}) in {delay:.1f}s...")
            await asyncio.sleep(delay)

        if not state:
            _LOGGER.error(f"Scene Capture: Entity {entity_id} does not exist or is not loaded after {max_attempts} attempts (total {total_delay:.1f}s)")
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
