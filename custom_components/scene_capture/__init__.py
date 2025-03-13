import aiofiles
import asyncio
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
import logging
import os
import voluptuous as vol
import yaml

"""
Home Assistant custom integration to update a scene with current entity states.

Usage example:
  service: scene_capture.update
  target:
    entity_id: scene.living_room
"""

DOMAIN = "scene_capture"
SERVICE = "update"

_LOGGER = logging.getLogger(__name__)

def to_serializable(data):
    """Convert data to a YAML-serializable form."""
    if isinstance(data, dict):
        return {k: to_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [to_serializable(item) for item in data]
    elif hasattr(data, "value"):  # Handles enums like ColorMode
        return str(data.value)  # Gets 'brightness' from ColorMode.BRIGHTNESS
    elif isinstance(data, (int, float, str, bool)) or data is None:
        return data
    else:
        _LOGGER.debug(f"Unexpected type, converting to string: {data}")
        return str(data)  # Fallback, not repr(data)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Scene Capture integration."""
    async def handle_update(call: ServiceCall) -> None:
        """Handle the scene update service call."""
        entity_id = call.data.get("entity_id")
        if not isinstance(entity_id, str):
            _LOGGER.error(f"Invalid entity_id: {entity_id}")
            return
        if not entity_id.startswith("scene."):
            _LOGGER.error(f"Entity must be a scene: {entity_id}")
            return
        
        state = hass.states.get(entity_id)
        if not state or "id" not in state.attributes:
            _LOGGER.error(f"No scene ID found for {entity_id}")
            return
        scene_id = state.attributes["id"]

        scenes_file = os.path.join(hass.config.config_dir, "scenes.yaml")
        try:
            async with aiofiles.open(scenes_file, "r", encoding="utf-8") as f:
                scenes_config = yaml.safe_load(await f.read()) or []
            if not isinstance(scenes_config, list):
                _LOGGER.error("scenes.yaml is not a list")
                return
        except FileNotFoundError:
            scenes_config = []
            _LOGGER.warning("scenes.yaml not found, creating new")

        target_scene = next((s for s in scenes_config if s.get("id") == scene_id), None)
        if not target_scene:
            _LOGGER.error(f"Scene {scene_id} not found in scenes.yaml")
            return

        updated_entities = {}
        for entity in target_scene.get("entities", {}):
            state = hass.states.get(entity)
            if state:
                attributes = to_serializable(state.attributes)
                attributes["state"] = str(state.state)
                updated_entities[entity] = attributes

        target_scene["entities"] = updated_entities

        try:
            yaml_content = yaml.safe_dump(scenes_config, default_flow_style=False, allow_unicode=True, sort_keys=False)
            async with aiofiles.open(scenes_file, "w", encoding="utf-8") as f:
                await f.write(yaml_content)
            await hass.services.async_call("scene", "reload")
            _LOGGER.info(f"Updated scene {scene_id}")
        except Exception as e:
            _LOGGER.error(f"Failed to write scenes.yaml: {e}")

    hass.services.async_register(
        DOMAIN,
        SERVICE,
        handle_update,
        schema=vol.Schema({}, extra=vol.ALLOW_EXTRA),
    )
    _LOGGER.info("Scene Capture integration set up")
    return True