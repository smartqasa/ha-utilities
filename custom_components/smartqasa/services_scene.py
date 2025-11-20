from homeassistant.core import HomeAssistant, ServiceCall
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_SCENE_GET,
    SERVICE_SCENE_UPDATE,
    SERVICE_SCENE_RELOAD,
)
from .scene_utils import (
    get_scene_entities,
    update_scene_entities,
)
from .helpers import retrieve_scene_id


def register_scene_services(hass: HomeAssistant):
    """Register scene-related SmartQasa services."""

    async def handle_get(call: ServiceCall):
        entity_id = call.data["entity_id"][0]
        scene_id = await retrieve_scene_id(hass, entity_id)
        entities = await get_scene_entities(hass, scene_id)
        return {
            "entities": list(entities.keys()) if entities else [],
            "scene_id": scene_id,
        }

    async def handle_update(call: ServiceCall):
        entity_id = call.data["entity_id"][0]
        scene_id = await retrieve_scene_id(hass, entity_id)
        return await update_scene_entities(hass, scene_id)

    async def handle_reload(call: ServiceCall):
        await hass.services.async_call("scene", "reload")
        return {"success": True}

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCENE_GET,
        handle_get,
        schema=vol.Schema({
            vol.Required("entity_id"): vol.All(cv.ensure_list, [cv.entity_id]),
        }),
        supports_response="only",
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCENE_UPDATE,
        handle_update,
        schema=vol.Schema({
            vol.Required("entity_id"): vol.All(cv.ensure_list, [cv.entity_id]),
        }),
        supports_response="only",
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCENE_RELOAD,
        handle_reload,
        schema=vol.Schema({}),
    )
