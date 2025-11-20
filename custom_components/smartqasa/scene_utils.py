import aiofiles
import os
import tempfile
import asyncio
from ruamel.yaml import YAML
from homeassistant.core import HomeAssistant
import logging

from .const import SCENES_FILE
from .helpers import safe_item

yaml = YAML(typ="rt")
yaml.allow_unicode = True
yaml.default_flow_style = False

_LOGGER = logging.getLogger(__name__)

CAPTURE_LOCK = asyncio.Lock()


async def load_scenes_file(hass: HomeAssistant):
    """Load scenes.yaml"""
    path = os.path.join(hass.config.config_dir, SCENES_FILE)

    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        content = await f.read()

    return yaml.load(content) or []


async def get_scene_entities(hass: HomeAssistant, scene_id: str):
    """Return entity list from a scene ID."""
    scenes = await load_scenes_file(hass)

    for scene in scenes:
        if scene.get("id") == scene_id:
            return scene.get("entities", {})

    return None


async def update_scene_entities(hass: HomeAssistant, scene_id: str):
    """Update entities in scenes.yaml for given scene ID."""

    async with CAPTURE_LOCK:
        path = os.path.join(hass.config.config_dir, SCENES_FILE)

        scenes = await load_scenes_file(hass)

        # Find index
        index = next((i for i, s in enumerate(scenes) if s.get("id") == scene_id), None)
        if index is None:
            return {"success": False, "message": f"Scene {scene_id} not found"}

        scene = scenes[index]
        entities = scene.get("entities", {}).copy()

        # Update entity attributes
        for ent_id in list(entities.keys()):
            state = hass.states.get(ent_id)
            if not state:
                continue

            attributes = dict(state.attributes)
            attributes["state"] = str(state.state)
            attributes = {k: safe_item(v) for k, v in attributes.items() if v is not None}
            entities[ent_id] = attributes

        # Replace
        scene["entities"] = entities
        scenes[index] = scene

        # Write atomically
        try:
            tmp = tempfile.NamedTemporaryFile("w", delete=False, dir=hass.config.config_dir)
            yaml.dump(scenes, tmp)
            tmp.close()
            os.replace(tmp.name, path)
            return {"success": True, "message": f"Scene {scene_id} updated"}
        except Exception as e:
            return {"success": False, "message": str(e)}
